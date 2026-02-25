import {
  TrustScorer,
  Claim,
  TrustAxes,
  TrustResult,
} from "../../../packages/katala/core/TrustScorer";
import {
  ConsensusEngine,
  TrustAgent,
  AgentVerdict,
} from "../../../packages/katala/core/ConsensusEngine";
import {
  VulnFinding,
  VulnVerificationResult,
  VulnSeverity,
  ConfidenceLevel,
} from "./types";

// ============================================================
// Vulnerability Verification Pipeline
//
// Issue #43: TrustScorer + ConsensusEngineで脆弱性報告を自動検証。
//
// TrustScorerの4軸を脆弱性ドメインに適応:
//   freshness     → 発見からの経過時間（古いほど攻撃リスクが累積）
//   provenance    → 発見エージェント/報告者の信頼性
//   verification  → 再現性 + 他エージェントの確認状況
//   accessibility → 【拡張】攻撃の容易さ（CVSS準拠）
//
// ConsensusEngineで複数の独立した評価を合議:
//   Agent A (vuln-scorer-alpha) → 標準重み
//   Agent B (vuln-scorer-beta)  → verification重み増加（再現性重視）
//   Tiebreaker (vuln-scorer-gamma) → 乖離時に介入
//
// 出力: Critical/High/Medium/Low + confidence (H/M/L)
// ============================================================

// --- 脆弱性ドメイン用の重み設定 ---

/** 標準評価: freshness/provenanceを重視 */
const VULN_WEIGHTS_ALPHA = {
  freshness: 0.25,
  provenance: 0.35,
  verification: 0.30,
  accessibility: 0.10,
};

/** 再現性重視評価: verificationを最重視 */
const VULN_WEIGHTS_BETA = {
  freshness: 0.15,
  provenance: 0.25,
  verification: 0.50,
  accessibility: 0.10,
};

/** タイブレーカー: バランス型 */
const VULN_WEIGHTS_GAMMA = {
  freshness: 0.20,
  provenance: 0.30,
  verification: 0.40,
  accessibility: 0.10,
};

// --- 攻撃容易度スコア計算 ---

/**
 * VulnFindingの攻撃特性からattackEaseスコアを計算 (0-1)
 * CVSS基本スコアの簡略版。スコアが高いほど攻撃が容易（危険）。
 */
export function calcAttackEase(finding: VulnFinding): number {
  let score = 0.3; // ベースライン: 攻撃特性不明の場合は中程度

  // 攻撃ベクトル (network = 最も危険)
  const vectorScore: Record<string, number> = {
    network: 0.35,
    adjacent: 0.25,
    local: 0.15,
    physical: 0.05,
  };
  if (finding.attackVector) {
    score = vectorScore[finding.attackVector] ?? score;
  }

  // 攻撃複雑度 (low = 容易 = +0.15)
  if (finding.attackComplexity === "low") {
    score += 0.15;
  } else if (finding.attackComplexity === "high") {
    score -= 0.05;
  }

  // 必要権限 (none = 権限不要 = +0.15)
  if (finding.privilegesRequired === "none") {
    score += 0.15;
  } else if (finding.privilegesRequired === "low") {
    score += 0.05;
  }

  // ユーザー操作要否 (none = 操作不要 = +0.1)
  if (finding.userInteraction === "none") {
    score += 0.10;
  }

  // PoCあり = 誰でも攻撃可能 = 大幅加算 (+0.2)
  if (finding.pocAvailable) {
    score += 0.20;
  }

  return Math.min(1, Math.max(0, score));
}

// --- VulnFinding → Claim 変換 ---

/**
 * VulnFindingをTrustScorerが処理できるClaim形式に変換する。
 *
 * ポイント:
 * - source.type: reporterTypeに基づいてマッピング
 *   researcher → primary, red-agent → generated,
 *   community → tertiary, automated-scan → secondary
 * - domain: "security" (セキュリティ専用ドメイン)
 * - accessibility軸は後でattackEaseで上書き
 */
function findingToClaim(finding: VulnFinding): Claim {
  const sourceTypeMap: Record<string, "primary" | "secondary" | "tertiary" | "generated"> = {
    researcher: "primary",
    "automated-scan": "secondary",
    community: "tertiary",
    "red-agent": "generated",
  };

  return {
    id: finding.id,
    content: `[${finding.cve ?? "NO-CVE"}] ${finding.title}: ${finding.description}`,
    source: {
      type: sourceTypeMap[finding.reporterType] ?? "tertiary",
      author: finding.reporterId,
      url: finding.targetRepo,
      publishedAt: finding.discoveredAt,
      platform: finding.reporterType,
    },
    domain: "security",
    retrievedAt: finding.retrievedAt ?? new Date().toISOString(),
    language: "ja",
  };
}

// --- VulnTrustScorerAgent: 脆弱性専用スコアリングエージェント ---

/**
 * TrustScorerをラップし、accessibility軸をattackEaseで置換する
 * 内部TrustAgent実装。ConsensusEngineに注入する。
 */
class VulnTrustScorerAgent implements TrustAgent {
  id: string;
  model: string;
  private scorer: TrustScorer;
  private weights: typeof VULN_WEIGHTS_ALPHA;
  private attackEase: number;

  constructor(
    id: string,
    weights: typeof VULN_WEIGHTS_ALPHA,
    attackEase: number,
  ) {
    this.id = id;
    this.model = "vuln-rule-based-v1";
    this.weights = weights;
    this.attackEase = attackEase;
    // TrustScorerはfreshness/provenance/verificationの計算に使用
    // accessibilityはattackEaseで上書きするため、accessibilityの重みを0にする
    this.scorer = new TrustScorer({
      freshness: weights.freshness,
      provenance: weights.provenance,
      verification: weights.verification,
      accessibility: 0, // 後でattackEaseで置換するので0に設定
    });
  }

  async evaluate(claim: Claim, context?: Claim[]): Promise<AgentVerdict> {
    const corroborating = (context ?? []).filter(
      (c) => c.domain === claim.domain && c.source.author !== claim.source.author,
    );

    // TrustScorerで3軸スコアを計算
    const baseResult = this.scorer.score(claim, corroborating, []);

    // accessibility軸をattackEaseで上書き
    const axes: TrustAxes = {
      ...baseResult.axes,
      accessibility: this.attackEase,
    };

    // 重みを使って composite score を再計算
    const total =
      this.weights.freshness +
      this.weights.provenance +
      this.weights.verification +
      this.weights.accessibility;

    const compositeScore =
      (axes.freshness * this.weights.freshness +
        axes.provenance * this.weights.provenance +
        axes.verification * this.weights.verification +
        axes.accessibility * this.weights.accessibility) /
      total;

    const grade = toGrade(compositeScore);

    const result: TrustResult = {
      ...baseResult,
      axes,
      compositeScore,
      grade,
      reasoning: buildVulnReasoning(axes, this.attackEase, compositeScore),
      scoredAt: new Date().toISOString(),
    };

    // 信頼度: verificationスコアとprovenanceスコアで決定
    const confidence = Math.min(1, (axes.verification * 0.6 + axes.provenance * 0.4));

    return {
      agentId: this.id,
      model: this.model,
      result,
      confidence,
      reasoning: result.reasoning,
      completedAt: new Date().toISOString(),
    };
  }
}

// --- 重大度分類 ---

/**
 * trustScoreとattackEaseから重大度を決定する。
 *
 * Critical: trustScore >= 0.7 AND attackEase >= 0.7
 * High:     (trustScore >= 0.7 AND attackEase >= 0.4) OR (trustScore >= 0.5 AND attackEase >= 0.7)
 * Medium:   trustScore >= 0.4 AND attackEase >= 0.3
 * Low:      それ以外
 */
export function classifySeverity(trustScore: number, attackEase: number): VulnSeverity {
  if (trustScore >= 0.7 && attackEase >= 0.7) return "Critical";
  if ((trustScore >= 0.7 && attackEase >= 0.4) || (trustScore >= 0.5 && attackEase >= 0.7)) {
    return "High";
  }
  if (trustScore >= 0.4 && attackEase >= 0.3) return "Medium";
  return "Low";
}

/**
 * ConsensusEngineの合議結果からConfidenceLevelを決定する。
 * High:   unanimous または divergence <= 0.05
 * Medium: majority または divergence <= 0.15
 * Low:    tiebreaker / deadlock
 */
export function classifyConfidence(
  consensus: "unanimous" | "majority" | "tiebreaker" | "deadlock",
  divergence: number,
): ConfidenceLevel {
  if (consensus === "unanimous" || divergence <= 0.05) return "High";
  if (consensus === "majority" || divergence <= 0.15) return "Medium";
  return "Low";
}

// --- Helpers ---

function toGrade(score: number): TrustResult["grade"] {
  if (score >= 0.9) return "S";
  if (score >= 0.8) return "A";
  if (score >= 0.65) return "B";
  if (score >= 0.5) return "C";
  if (score >= 0.35) return "D";
  return "F";
}

function buildVulnReasoning(axes: TrustAxes, attackEase: number, composite: number): string {
  const parts: string[] = [];

  // Freshness
  if (axes.freshness >= 0.8) {
    parts.push("発見直後（高鮮度）");
  } else if (axes.freshness >= 0.5) {
    parts.push("発見から時間が経過");
  } else {
    parts.push("古い発見 — 放置期間中に悪用された可能性あり");
  }

  // Provenance
  if (axes.provenance >= 0.8) {
    parts.push("高信頼報告者（一次情報）");
  } else if (axes.provenance >= 0.5) {
    parts.push("中程度の信頼性");
  } else {
    parts.push("⚠️ 低信頼報告源 — 追加検証を推奨");
  }

  // Verification
  if (axes.verification >= 0.7) {
    parts.push("検証済み（再現性確認 + 複数エージェント確認）");
  } else if (axes.verification >= 0.4) {
    parts.push("部分的に検証済み");
  } else {
    parts.push("⚠️ 未検証 — 再現確認が必要");
  }

  // Attack ease
  if (attackEase >= 0.7) {
    parts.push("🔴 攻撃容易度: 高（即時対応が必要）");
  } else if (attackEase >= 0.4) {
    parts.push("🟡 攻撃容易度: 中");
  } else {
    parts.push("🟢 攻撃容易度: 低");
  }

  parts.push(`総合スコア: ${(composite * 100).toFixed(0)}/100`);

  return parts.join("。") + "。";
}

// --- Main Pipeline ---

/**
 * VulnVerificationPipeline
 *
 * 使い方:
 * ```typescript
 * const pipeline = new VulnVerificationPipeline();
 * const result = await pipeline.verify(finding);
 * // result.severity: "Critical" | "High" | "Medium" | "Low"
 * // result.confidence: "High" | "Medium" | "Low"
 * // result.dissent: [...] // 少数意見
 * ```
 */
export class VulnVerificationPipeline {
  private engine: ConsensusEngine;
  private attackEaseForAgents: Map<string, number> = new Map();

  constructor() {
    // ConsensusEngineはagent生成時にattackEaseが必要なので、
    // verify()内でエンジンを動的に構築する
    // ここではプレースホルダーとして初期化
    const placeholder = new VulnTrustScorerAgent("placeholder", VULN_WEIGHTS_ALPHA, 0.5);
    const placeholder2 = new VulnTrustScorerAgent("placeholder2", VULN_WEIGHTS_BETA, 0.5);
    this.engine = new ConsensusEngine([placeholder, placeholder2]);
  }

  /**
   * 単一VulnFindingを検証する。
   */
  async verify(finding: VulnFinding): Promise<VulnVerificationResult> {
    // Step 1: 攻撃容易度を計算
    const attackEase = calcAttackEase(finding);

    // Step 2: 独立した評価エージェントを生成 (finding固有のattackEaseを注入)
    const agentAlpha = new VulnTrustScorerAgent("vuln-scorer-alpha", VULN_WEIGHTS_ALPHA, attackEase);
    const agentBeta = new VulnTrustScorerAgent("vuln-scorer-beta", VULN_WEIGHTS_BETA, attackEase);
    const agentGamma = new VulnTrustScorerAgent("vuln-scorer-gamma", VULN_WEIGHTS_GAMMA, attackEase);

    // Step 3: ConsensusEngine を構築
    const engine = new ConsensusEngine([agentAlpha, agentBeta], agentGamma, {
      divergenceThreshold: 0.12, // 脆弱性評価は厳格に
      minAgents: 2,
      timeoutMs: 10000,
      useConfidenceWeighting: true,
    });

    // Step 4: VulnFinding → Claim 変換 → 合議評価
    const claim = findingToClaim(finding);
    const consensusResult = await engine.evaluate(claim);

    // Step 5: trustScore と attackEase から重大度を分類
    const severity = classifySeverity(consensusResult.finalScore, attackEase);
    const confidence = classifyConfidence(consensusResult.consensus, consensusResult.divergence);

    // Step 6: 少数意見を dissent 形式に変換
    const dissent = consensusResult.dissent.map((d) => ({
      agentId: d.agentId,
      trustScore: d.score,
      reasoning: d.reasoning,
    }));

    // Step 7: 4軸スコアをvuln用に変換 (accessibility → attackEase)
    const axes = {
      freshness: consensusResult.finalAxes.freshness,
      provenance: consensusResult.finalAxes.provenance,
      verification: consensusResult.finalAxes.verification,
      attackEase: consensusResult.finalAxes.accessibility,
    };

    // Step 8: CVEやPoCなど脆弱性固有のcaveatsを追加
    const caveats = [...consensusResult.caveats];
    if (finding.pocAvailable) {
      caveats.push("⚠️ PoCコードが公開されている — 攻撃者が即座に利用可能な状態");
    }
    if (!finding.reproducible) {
      caveats.push("再現性未確認 — 環境依存の可能性あり");
    }
    if (finding.confirmedBy.length === 0) {
      caveats.push("他エージェントによる確認なし — 誤検出リスクあり");
    }
    if (severity === "Critical" || severity === "High") {
      caveats.push("高重大度: 人間のセキュリティエンジニアによる最終判断を推奨");
    }

    return {
      findingId: finding.id,
      severity,
      confidence,
      trustScore: consensusResult.finalScore,
      attackEaseScore: attackEase,
      axes,
      consensus: consensusResult.consensus,
      divergence: consensusResult.divergence,
      dissent,
      caveats,
      reasoning: consensusResult.reasoning,
      verifiedAt: new Date().toISOString(),
    };
  }

  /**
   * 複数のVulnFindingをバッチ検証する。
   * 直列実行（API rate limit考慮）。
   */
  async verifyBatch(findings: VulnFinding[]): Promise<VulnVerificationResult[]> {
    const results: VulnVerificationResult[] = [];
    for (const finding of findings) {
      results.push(await this.verify(finding));
    }
    return results;
  }
}
