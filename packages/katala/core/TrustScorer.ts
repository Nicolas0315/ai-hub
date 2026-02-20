import { z } from "zod";

// ============================================================
// Trust Scorer — Katalaの心臓部
// 情報の信頼性を4軸でスコアリングする
// ============================================================

/**
 * 信頼性の4軸（Katala Trust Axes）
 *
 * 1. Freshness（鮮度）    — いつの情報か
 * 2. Provenance（出所）   — 誰が言ったか、一次か二次か
 * 3. Verification（検証）  — 確認済みか推測か
 * 4. Accessibility（引き出しやすさ） — 必要な時に見つかるか
 */

// --- Schemas ---

export const TrustAxesSchema = z.object({
  freshness: z.number().min(0).max(1),
  provenance: z.number().min(0).max(1),
  verification: z.number().min(0).max(1),
  accessibility: z.number().min(0).max(1),
});

export type TrustAxes = z.infer<typeof TrustAxesSchema>;

export const SourceTypeSchema = z.enum([
  "primary",       // 一次情報（本人発言、公式発表、論文）
  "secondary",     // 二次情報（報道、まとめ、引用）
  "tertiary",      // 三次情報（伝聞、噂、未確認）
  "generated",     // AI生成（LLM出力）
]);

export type SourceType = z.infer<typeof SourceTypeSchema>;

export const ClaimSchema = z.object({
  id: z.string(),
  content: z.string(),
  source: z.object({
    type: SourceTypeSchema,
    author: z.string().optional(),
    url: z.string().url().optional(),
    publishedAt: z.string().datetime().optional(),
    platform: z.string().optional(),
  }),
  domain: z.string().optional(),          // 分野（政治、技術、金融など）
  retrievedAt: z.string().datetime(),     // 取得日時
  language: z.string().default("ja"),
});

export type Claim = z.infer<typeof ClaimSchema>;

export const TrustResultSchema = z.object({
  claimId: z.string(),
  axes: TrustAxesSchema,
  compositeScore: z.number().min(0).max(1),
  grade: z.enum(["S", "A", "B", "C", "D", "F"]),
  reasoning: z.string(),
  corroboratingClaims: z.array(z.string()).default([]),  // 裏付けるclaimのID
  contradictingClaims: z.array(z.string()).default([]),   // 矛盾するclaimのID
  scoredAt: z.string().datetime(),
});

export type TrustResult = z.infer<typeof TrustResultSchema>;

// --- Scoring Weights ---

export interface TrustWeights {
  freshness: number;
  provenance: number;
  verification: number;
  accessibility: number;
}

export const DEFAULT_WEIGHTS: TrustWeights = {
  freshness: 0.20,
  provenance: 0.35,
  verification: 0.35,
  accessibility: 0.10,
};

// --- Core Engine ---

export class TrustScorer {
  private weights: TrustWeights;

  constructor(weights?: Partial<TrustWeights>) {
    this.weights = { ...DEFAULT_WEIGHTS, ...weights };
    // Normalize weights to sum to 1
    const sum = Object.values(this.weights).reduce((a, b) => a + b, 0);
    if (Math.abs(sum - 1.0) > 0.001) {
      const keys = Object.keys(this.weights) as (keyof TrustWeights)[];
      for (const k of keys) {
        this.weights[k] /= sum;
      }
    }
  }

  /**
   * Score a single claim
   */
  score(claim: Claim, corroborating: Claim[] = [], contradicting: Claim[] = []): TrustResult {
    const axes: TrustAxes = {
      freshness: this.scoreFreshness(claim),
      provenance: this.scoreProvenance(claim),
      verification: this.scoreVerification(claim, corroborating, contradicting),
      accessibility: this.scoreAccessibility(claim),
    };

    const compositeScore =
      axes.freshness * this.weights.freshness +
      axes.provenance * this.weights.provenance +
      axes.verification * this.weights.verification +
      axes.accessibility * this.weights.accessibility;

    return {
      claimId: claim.id,
      axes,
      compositeScore,
      grade: this.toGrade(compositeScore),
      reasoning: this.generateReasoning(claim, axes, corroborating, contradicting),
      corroboratingClaims: corroborating.map((c) => c.id),
      contradictingClaims: contradicting.map((c) => c.id),
      scoredAt: new Date().toISOString(),
    };
  }

  /**
   * Score multiple claims and cross-validate
   */
  scoreBatch(claims: Claim[]): TrustResult[] {
    // Build cross-reference map: group by domain
    const byDomain = new Map<string, Claim[]>();
    for (const c of claims) {
      const domain = c.domain ?? "general";
      if (!byDomain.has(domain)) byDomain.set(domain, []);
      byDomain.get(domain)!.push(c);
    }

    return claims.map((claim) => {
      const domain = claim.domain ?? "general";
      const siblings = (byDomain.get(domain) ?? []).filter((c) => c.id !== claim.id);
      // Simple heuristic: same-domain claims from different sources = corroborating
      // TODO: Replace with semantic similarity + contradiction detection
      const corroborating = siblings.filter(
        (s) => s.source.author !== claim.source.author
      );
      return this.score(claim, corroborating, []);
    });
  }

  // --- Axis Scorers ---

  private scoreFreshness(claim: Claim): number {
    const now = Date.now();
    const published = claim.source.publishedAt
      ? new Date(claim.source.publishedAt).getTime()
      : new Date(claim.retrievedAt).getTime();

    const ageHours = (now - published) / (1000 * 60 * 60);

    // Domain-aware decay curves
    const domain = claim.domain ?? "general";
    const halfLife = DOMAIN_HALF_LIFE[domain] ?? DOMAIN_HALF_LIFE["general"];

    // Exponential decay: score = e^(-age/halfLife)
    return Math.exp(-ageHours / halfLife);
  }

  private scoreProvenance(claim: Claim): number {
    let score = 0;

    // Source type baseline
    switch (claim.source.type) {
      case "primary":
        score = 0.9;
        break;
      case "secondary":
        score = 0.6;
        break;
      case "tertiary":
        score = 0.3;
        break;
      case "generated":
        score = 0.2;
        break;
    }

    // Has identifiable author? +0.05
    if (claim.source.author) score = Math.min(1, score + 0.05);

    // Has URL (traceable)? +0.05
    if (claim.source.url) score = Math.min(1, score + 0.05);

    return score;
  }

  private scoreVerification(
    claim: Claim,
    corroborating: Claim[],
    contradicting: Claim[]
  ): number {
    // Base: unverified = 0.3
    let score = 0.3;

    // Each corroborating source adds diminishing returns
    for (let i = 0; i < corroborating.length; i++) {
      const boost = 0.15 / (i + 1); // diminishing: 0.15, 0.075, 0.05...
      score = Math.min(1, score + boost);
    }

    // Each contradicting source penalizes
    for (let i = 0; i < contradicting.length; i++) {
      const penalty = 0.2 / (i + 1);
      score = Math.max(0, score - penalty);
    }

    return score;
  }

  private scoreAccessibility(claim: Claim): number {
    let score = 0.5; // baseline

    // Has URL = accessible
    if (claim.source.url) score += 0.3;

    // Has specific published date = more findable
    if (claim.source.publishedAt) score += 0.1;

    // Primary source = easier to verify
    if (claim.source.type === "primary") score += 0.1;

    return Math.min(1, score);
  }

  // --- Helpers ---

  private toGrade(score: number): "S" | "A" | "B" | "C" | "D" | "F" {
    if (score >= 0.9) return "S";
    if (score >= 0.8) return "A";
    if (score >= 0.65) return "B";
    if (score >= 0.5) return "C";
    if (score >= 0.35) return "D";
    return "F";
  }

  private generateReasoning(
    claim: Claim,
    axes: TrustAxes,
    corroborating: Claim[],
    contradicting: Claim[]
  ): string {
    const parts: string[] = [];

    // Freshness
    if (axes.freshness >= 0.8) {
      parts.push("情報は新鮮");
    } else if (axes.freshness >= 0.5) {
      parts.push("情報はやや古い");
    } else {
      parts.push("情報の鮮度が低い — 最新情報の確認を推奨");
    }

    // Provenance
    if (axes.provenance >= 0.8) {
      parts.push(`一次情報（${claim.source.author ?? "特定済み"}）`);
    } else if (axes.provenance >= 0.5) {
      parts.push("二次情報源");
    } else {
      parts.push("出所の信頼性が低い");
    }

    // Verification
    if (corroborating.length > 0) {
      parts.push(`${corroborating.length}件の裏付けあり`);
    }
    if (contradicting.length > 0) {
      parts.push(`⚠️ ${contradicting.length}件の矛盾情報あり`);
    }
    if (corroborating.length === 0 && contradicting.length === 0) {
      parts.push("クロスバリデーション未実施");
    }

    return parts.join("。") + "。";
  }
}

// --- Domain-specific half-lives (in hours) ---
// After one half-life, freshness score drops to ~37% (1/e)

const DOMAIN_HALF_LIFE: Record<string, number> = {
  crypto: 6,          // 暗号通貨: 6時間で急速に古くなる
  politics: 24,       // 政治: 1日
  tech: 72,           // テクノロジー: 3日
  science: 720,       // 科学: 30日
  finance: 12,        // 金融: 12時間
  entertainment: 48,  // エンタメ: 2日
  general: 168,       // 一般: 1週間
};

export { DOMAIN_HALF_LIFE };
