import { z } from "zod";
import { TrustScorer, Claim, TrustResult, TrustAxes } from "./TrustScorer";

// ============================================================
// Consensus Engine — マルチエージェント合議による信頼性検証
//
// 設計思想:
//   格付け機関が銀行の中にあったら意味がない。
//   1つのエージェントの判断も同じ。複数の独立した視点で
//   クロスバリデーションし、乖離があればタイブレーカーを呼ぶ。
//
// アーキテクチャ:
//   Agent A ──→ TrustResult ──┐
//                              ├──→ Consensus Engine ──→ Final Result
//   Agent B ──→ TrustResult ──┘
//                                        ↓ (乖離大)
//                              Agent C (Tiebreaker)
// ============================================================

// --- Types ---

export const AgentVerdictSchema = z.object({
  agentId: z.string(),
  model: z.string(), // e.g. "claude-sonnet-4", "gemini-3-pro"
  result: z.custom<TrustResult>(),
  confidence: z.number().min(0).max(1),
  reasoning: z.string(),
  completedAt: z.string().datetime(),
});

export type AgentVerdict = z.infer<typeof AgentVerdictSchema>;

export const DissentSchema = z.object({
  agentId: z.string(),
  score: z.number(),
  reasoning: z.string(),
});

export type Dissent = z.infer<typeof DissentSchema>;

export const ConsensusResultSchema = z.object({
  claimId: z.string(),
  finalScore: z.number().min(0).max(1),
  finalGrade: z.enum(["S", "A", "B", "C", "D", "F"]),
  finalAxes: z.custom<TrustAxes>(),
  consensus: z.enum(["unanimous", "majority", "tiebreaker", "deadlock"]),
  divergence: z.number().min(0).max(1), // 最大乖離幅
  verdicts: z.array(AgentVerdictSchema),
  /**
   * マイノリティ意見: 多数派と大きく異なる見解を持つエージェントの記録
   * 「数字があるから正解ではない。マイノリティが間違っているというルールは合理的ではない」
   * — 少数意見を消さない。判断材料として常に保持する
   */
  dissent: z.array(DissentSchema).default([]),
  /**
   * スコアの限界を明示: このスコアが捉えられていない外的要因
   * 数字は道具であって真実ではない
   */
  caveats: z.array(z.string()).default([]),
  reasoning: z.string(),
  completedAt: z.string().datetime(),
});

export type ConsensusResult = z.infer<typeof ConsensusResultSchema>;

// --- Agent Interface ---

/**
 * TrustAgent: 独立した信頼性評価エージェント
 * 各エージェントは異なるLLMモデルまたは異なる評価戦略を持つ
 */
export interface TrustAgent {
  id: string;
  model: string;
  evaluate(claim: Claim, context?: Claim[]): Promise<AgentVerdict>;
}

// --- Configuration ---

export interface ConsensusConfig {
  /** 乖離がこの閾値を超えたらタイブレーカーを呼ぶ (0-1) */
  divergenceThreshold: number;
  /** 最低エージェント数 */
  minAgents: number;
  /** タイムアウト（ms） */
  timeoutMs: number;
  /** 重み付け: confidence-weighted average を使うか */
  useConfidenceWeighting: boolean;
}

const DEFAULT_CONFIG: ConsensusConfig = {
  divergenceThreshold: 0.15,
  minAgents: 2,
  timeoutMs: 30000,
  useConfidenceWeighting: true,
};

// --- Core Engine ---

export class ConsensusEngine {
  private agents: TrustAgent[];
  private tiebreaker: TrustAgent | null;
  private config: ConsensusConfig;

  constructor(agents: TrustAgent[], tiebreaker?: TrustAgent, config?: Partial<ConsensusConfig>) {
    this.agents = agents;
    this.tiebreaker = tiebreaker ?? null;
    this.config = { ...DEFAULT_CONFIG, ...config };

    if (agents.length < this.config.minAgents) {
      throw new Error(
        `ConsensusEngine requires at least ${this.config.minAgents} agents, got ${agents.length}`,
      );
    }
  }

  /**
   * 単一Claimに対するマルチエージェント合議
   */
  async evaluate(claim: Claim, context?: Claim[]): Promise<ConsensusResult> {
    // Phase 1: 全エージェントが独立に評価（並列実行）
    const verdicts = await this.collectVerdicts(claim, context);

    // Phase 2: 乖離を計算
    const divergence = this.calculateDivergence(verdicts);

    // Phase 3: 乖離が大きければタイブレーカー
    let allVerdicts = verdicts;
    let consensusType: ConsensusResult["consensus"];

    if (divergence > this.config.divergenceThreshold && this.tiebreaker) {
      const tiebreakerVerdict = await this.tiebreaker.evaluate(claim, context);
      allVerdicts = [...verdicts, tiebreakerVerdict];
      consensusType = "tiebreaker";
    } else if (divergence <= 0.05) {
      consensusType = "unanimous";
    } else if (divergence <= this.config.divergenceThreshold) {
      consensusType = "majority";
    } else {
      // 乖離大きいがタイブレーカーなし
      consensusType = "deadlock";
    }

    // Phase 4: 最終スコア算出
    const { finalScore, finalAxes } = this.aggregateVerdicts(allVerdicts);
    const finalGrade = this.toGrade(finalScore);

    // Phase 5: マイノリティ意見の抽出（少数意見を消さない）
    const dissent = this.extractDissent(allVerdicts, finalScore);

    // Phase 6: スコアの限界を明示（数字は道具であって真実ではない）
    const caveats = this.generateCaveats(claim, allVerdicts, consensusType);

    return {
      claimId: claim.id,
      finalScore,
      finalGrade,
      finalAxes,
      consensus: consensusType,
      divergence,
      verdicts: allVerdicts,
      dissent,
      caveats,
      reasoning: this.generateConsensusReasoning(allVerdicts, consensusType, divergence),
      completedAt: new Date().toISOString(),
    };
  }

  /**
   * バッチ評価: 複数Claimを合議で検証
   */
  async evaluateBatch(claims: Claim[]): Promise<ConsensusResult[]> {
    // 直列実行（API rate limit考慮）
    // TODO: 並列度制御付きの並列実行に変更
    const results: ConsensusResult[] = [];
    for (const claim of claims) {
      const otherClaims = claims.filter((c) => c.id !== claim.id);
      results.push(await this.evaluate(claim, otherClaims));
    }
    return results;
  }

  // --- Internal ---

  private async collectVerdicts(claim: Claim, context?: Claim[]): Promise<AgentVerdict[]> {
    const promises = this.agents.map((agent) =>
      Promise.race([agent.evaluate(claim, context), this.timeout(agent.id)]),
    );

    const results = await Promise.allSettled(promises);
    const verdicts: AgentVerdict[] = [];

    for (const result of results) {
      if (result.status === "fulfilled" && result.value) {
        verdicts.push(result.value);
      }
      // 失敗したエージェントは無視（最低数チェックは後で）
    }

    if (verdicts.length < this.config.minAgents) {
      throw new Error(
        `Only ${verdicts.length}/${this.agents.length} agents responded. Minimum: ${this.config.minAgents}`,
      );
    }

    return verdicts;
  }

  private calculateDivergence(verdicts: AgentVerdict[]): number {
    if (verdicts.length < 2) return 0;

    const scores = verdicts.map((v) => v.result.compositeScore);
    const max = Math.max(...scores);
    const min = Math.min(...scores);
    return max - min;
  }

  private aggregateVerdicts(verdicts: AgentVerdict[]): {
    finalScore: number;
    finalAxes: TrustAxes;
  } {
    if (this.config.useConfidenceWeighting) {
      return this.confidenceWeightedAverage(verdicts);
    }
    return this.simpleAverage(verdicts);
  }

  private confidenceWeightedAverage(verdicts: AgentVerdict[]): {
    finalScore: number;
    finalAxes: TrustAxes;
  } {
    let totalWeight = 0;
    let weightedScore = 0;
    const weightedAxes = { freshness: 0, provenance: 0, verification: 0, accessibility: 0 };

    for (const v of verdicts) {
      const w = v.confidence;
      totalWeight += w;
      weightedScore += v.result.compositeScore * w;
      weightedAxes.freshness += v.result.axes.freshness * w;
      weightedAxes.provenance += v.result.axes.provenance * w;
      weightedAxes.verification += v.result.axes.verification * w;
      weightedAxes.accessibility += v.result.axes.accessibility * w;
    }

    if (totalWeight === 0) return this.simpleAverage(verdicts);

    return {
      finalScore: weightedScore / totalWeight,
      finalAxes: {
        freshness: weightedAxes.freshness / totalWeight,
        provenance: weightedAxes.provenance / totalWeight,
        verification: weightedAxes.verification / totalWeight,
        accessibility: weightedAxes.accessibility / totalWeight,
      },
    };
  }

  private simpleAverage(verdicts: AgentVerdict[]): { finalScore: number; finalAxes: TrustAxes } {
    const n = verdicts.length;
    const axes = { freshness: 0, provenance: 0, verification: 0, accessibility: 0 };
    let totalScore = 0;

    for (const v of verdicts) {
      totalScore += v.result.compositeScore;
      axes.freshness += v.result.axes.freshness;
      axes.provenance += v.result.axes.provenance;
      axes.verification += v.result.axes.verification;
      axes.accessibility += v.result.axes.accessibility;
    }

    return {
      finalScore: totalScore / n,
      finalAxes: {
        freshness: axes.freshness / n,
        provenance: axes.provenance / n,
        verification: axes.verification / n,
        accessibility: axes.accessibility / n,
      },
    };
  }

  private generateConsensusReasoning(
    verdicts: AgentVerdict[],
    consensusType: ConsensusResult["consensus"],
    divergence: number,
  ): string {
    const parts: string[] = [];

    // Consensus type
    switch (consensusType) {
      case "unanimous":
        parts.push(
          `${verdicts.length}エージェント全員が一致（乖離${(divergence * 100).toFixed(1)}%）`,
        );
        break;
      case "majority":
        parts.push(
          `${verdicts.length}エージェントの多数決（乖離${(divergence * 100).toFixed(1)}%）`,
        );
        break;
      case "tiebreaker":
        parts.push(`タイブレーカー介入（初期乖離${(divergence * 100).toFixed(1)}%）`);
        break;
      case "deadlock":
        parts.push(
          `⚠️ デッドロック — エージェント間の見解が大きく分かれた（乖離${(divergence * 100).toFixed(1)}%）`,
        );
        break;
    }

    // Per-agent summary
    for (const v of verdicts) {
      parts.push(
        `[${v.agentId}/${v.model}] スコア${(v.result.compositeScore * 100).toFixed(0)} (信頼度${(v.confidence * 100).toFixed(0)}%)`,
      );
    }

    return parts.join("。") + "。";
  }

  /**
   * マイノリティ意見を抽出
   * 多数派と0.15以上乖離しているエージェントの見解を保存する
   * マイノリティが間違っているというルールは合理的ではない
   */
  private extractDissent(verdicts: AgentVerdict[], finalScore: number): Dissent[] {
    const dissents: Dissent[] = [];
    for (const v of verdicts) {
      const gap = Math.abs(v.result.compositeScore - finalScore);
      if (gap > 0.15) {
        dissents.push({
          agentId: v.agentId,
          score: v.result.compositeScore,
          reasoning: v.reasoning,
        });
      }
    }
    return dissents;
  }

  /**
   * スコアが捉えられていない外的要因を明示
   * 数字は判断材料を整理するためのもの。最終判断は人間がする
   */
  private generateCaveats(
    claim: Claim,
    verdicts: AgentVerdict[],
    consensusType: ConsensusResult["consensus"],
  ): string[] {
    const caveats: string[] = [];

    // 常に付与: スコアの本質的な限界
    caveats.push("スコアは判断材料の整理であり、真実の保証ではない");

    // 発信者の利害関係が不明な場合
    if (!claim.source.author) {
      caveats.push("発信者不明 — 利害関係の評価不可");
    }

    // 単一ドメインの情報（政治的・経済的文脈が考慮されていない可能性）
    if (claim.domain === "crypto" || claim.domain === "finance") {
      caveats.push("金融情報 — 発信者の経済的インセンティブを個別に確認すべき");
    }
    if (claim.domain === "politics") {
      caveats.push("政治情報 — 発信者の政治的立場・利害関係を個別に確認すべき");
    }

    // AI生成コンテンツ
    if (claim.source.type === "generated") {
      caveats.push("AI生成情報 — ハルシネーションの可能性を考慮すべき");
    }

    // デッドロック時
    if (consensusType === "deadlock") {
      caveats.push("エージェント間で見解が大きく分裂 — 人間による最終判断を強く推奨");
    }

    // マイノリティがいる場合
    const hasMinority = verdicts.some((v) => {
      const median = verdicts.map((x) => x.result.compositeScore).sort()[
        Math.floor(verdicts.length / 2)
      ];
      return Math.abs(v.result.compositeScore - median) > 0.15;
    });
    if (hasMinority) {
      caveats.push("少数意見あり — dissent欄を確認し、多数派が正しいと仮定しないこと");
    }

    return caveats;
  }

  private toGrade(score: number): ConsensusResult["finalGrade"] {
    if (score >= 0.9) return "S";
    if (score >= 0.8) return "A";
    if (score >= 0.65) return "B";
    if (score >= 0.5) return "C";
    if (score >= 0.35) return "D";
    return "F";
  }

  private timeout(agentId: string): Promise<never> {
    return new Promise((_, reject) =>
      setTimeout(
        () => reject(new Error(`Agent ${agentId} timed out after ${this.config.timeoutMs}ms`)),
        this.config.timeoutMs,
      ),
    );
  }
}

// --- Built-in Agent: Rule-based (TrustScorer wrapper) ---

/**
 * ルールベースエージェント: TrustScorerをラップ
 * LLMなしで動くベースライン評価
 */
export class RuleBasedTrustAgent implements TrustAgent {
  id: string;
  model: string;
  private scorer: TrustScorer;

  constructor(id?: string) {
    this.id = id ?? "rule-based";
    this.model = "rule-based-v1";
    this.scorer = new TrustScorer();
  }

  async evaluate(claim: Claim, context?: Claim[]): Promise<AgentVerdict> {
    const corroborating = (context ?? []).filter(
      (c) => c.domain === claim.domain && c.source.author !== claim.source.author,
    );

    const result = this.scorer.score(claim, corroborating, []);

    return {
      agentId: this.id,
      model: this.model,
      result,
      confidence: 0.7, // ルールベースは中程度の自信
      reasoning: result.reasoning,
      completedAt: new Date().toISOString(),
    };
  }
}

// --- Built-in Agent: LLM-based ---

/**
 * LLMエージェント: ClaudeやGeminiで信頼性を評価
 */
export interface LLMTrustAdapter {
  assessTrust(
    claim: Claim,
    context?: Claim[],
  ): Promise<{
    axes: TrustAxes;
    confidence: number;
    reasoning: string;
  }>;
}

export class LLMTrustAgent implements TrustAgent {
  id: string;
  model: string;
  private adapter: LLMTrustAdapter;
  private scorer: TrustScorer; // compositeScore計算用

  constructor(id: string, model: string, adapter: LLMTrustAdapter) {
    this.id = id;
    this.model = model;
    this.adapter = adapter;
    this.scorer = new TrustScorer();
  }

  async evaluate(claim: Claim, context?: Claim[]): Promise<AgentVerdict> {
    const assessment = await this.adapter.assessTrust(claim, context);

    // LLMが返した軸スコアからcompositeを計算
    const compositeScore =
      assessment.axes.freshness * 0.2 +
      assessment.axes.provenance * 0.35 +
      assessment.axes.verification * 0.35 +
      assessment.axes.accessibility * 0.1;

    const grade =
      compositeScore >= 0.9
        ? "S"
        : compositeScore >= 0.8
          ? "A"
          : compositeScore >= 0.65
            ? "B"
            : compositeScore >= 0.5
              ? "C"
              : compositeScore >= 0.35
                ? "D"
                : "F";

    const result: import("./TrustScorer").TrustResult = {
      claimId: claim.id,
      axes: assessment.axes,
      compositeScore,
      grade,
      reasoning: assessment.reasoning,
      corroboratingClaims: [],
      contradictingClaims: [],
      scoredAt: new Date().toISOString(),
    };

    return {
      agentId: this.id,
      model: this.model,
      result,
      confidence: assessment.confidence,
      reasoning: assessment.reasoning,
      completedAt: new Date().toISOString(),
    };
  }
}

// --- Mock Agent for Testing ---

export class MockTrustAgent implements TrustAgent {
  id: string;
  model: string;
  private fixedScore: number;
  private fixedConfidence: number;
  public callCount = 0;

  constructor(id: string, score: number, confidence: number = 0.8) {
    this.id = id;
    this.model = "mock";
    this.fixedScore = score;
    this.fixedConfidence = confidence;
  }

  async evaluate(claim: Claim): Promise<AgentVerdict> {
    this.callCount++;
    const axes: TrustAxes = {
      freshness: this.fixedScore,
      provenance: this.fixedScore,
      verification: this.fixedScore,
      accessibility: this.fixedScore,
    };

    return {
      agentId: this.id,
      model: this.model,
      result: {
        claimId: claim.id,
        axes,
        compositeScore: this.fixedScore,
        grade: this.fixedScore >= 0.8 ? "A" : this.fixedScore >= 0.5 ? "C" : "F",
        reasoning: `Mock verdict: ${this.fixedScore}`,
        corroboratingClaims: [],
        contradictingClaims: [],
        scoredAt: new Date().toISOString(),
      },
      confidence: this.fixedConfidence,
      reasoning: `Mock agent ${this.id}: score=${this.fixedScore}`,
      completedAt: new Date().toISOString(),
    };
  }
}
