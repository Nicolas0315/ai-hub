import { z } from "zod";

// ============================================================
// Vulnerability Verification Pipeline — Types
//
// Issue #43: Verification Pipeline (TrustScorer + ConsensusEngine)
// 脆弱性報告をTrustScorer + ConsensusEngineで自動検証するパイプライン。
// ============================================================

/**
 * 脆弱性報告者の種別
 * - red-agent: 自律REDエージェントによる自動検出
 * - researcher: セキュリティ研究者（人間または監督付きエージェント）
 * - community: コミュニティ報告（未検証）
 * - automated-scan: 自動スキャンツール（SAST/DAST等）
 */
export const ReporterTypeSchema = z.enum([
  "red-agent",
  "researcher",
  "community",
  "automated-scan",
]);
export type ReporterType = z.infer<typeof ReporterTypeSchema>;

/**
 * CVSS準拠の攻撃ベクトル
 * network > adjacent > local > physical の順に攻撃が容易
 */
export const AttackVectorSchema = z.enum(["network", "adjacent", "local", "physical"]);
export type AttackVector = z.infer<typeof AttackVectorSchema>;

/**
 * 攻撃複雑度 (CVSS)
 * low = 特別な条件不要 = より危険
 */
export const AttackComplexitySchema = z.enum(["low", "high"]);
export type AttackComplexity = z.infer<typeof AttackComplexitySchema>;

/**
 * 必要権限レベル (CVSS)
 * none = 権限不要 = より危険
 */
export const PrivilegesRequiredSchema = z.enum(["none", "low", "high"]);
export type PrivilegesRequired = z.infer<typeof PrivilegesRequiredSchema>;

/**
 * ユーザー操作要否 (CVSS)
 */
export const UserInteractionSchema = z.enum(["none", "required"]);
export type UserInteraction = z.infer<typeof UserInteractionSchema>;

// --- VulnFinding: 脆弱性報告の入力型 ---

export const VulnFindingSchema = z.object({
  /** 一意識別子 */
  id: z.string(),

  /** 脆弱性タイトル */
  title: z.string(),

  /** 脆弱性の詳細説明 */
  description: z.string(),

  /** CVE識別子（任意） */
  cve: z.string().optional(),

  /** 発見日時 (ISO 8601) */
  discoveredAt: z.string().datetime(),

  /** 報告者ID (agentId or researcher name) */
  reporterId: z.string(),

  /** 報告者の種別 */
  reporterType: ReporterTypeSchema,

  /** 対象リポジトリURL (任意) */
  targetRepo: z.string().url().optional(),

  /** 影響を受けるコンポーネント (任意) */
  affectedComponent: z.string().optional(),

  // --- 攻撃特性 (CVSS準拠、任意): accessibility軸のスコアリングに使用 ---

  /** 攻撃ベクトル (network が最も危険) */
  attackVector: AttackVectorSchema.optional(),

  /** 攻撃複雑度 (low が最も危険) */
  attackComplexity: AttackComplexitySchema.optional(),

  /** 必要権限 (none が最も危険) */
  privilegesRequired: PrivilegesRequiredSchema.optional(),

  /** ユーザー操作要否 (none が最も危険) */
  userInteraction: UserInteractionSchema.optional(),

  /** PoC(Proof of Concept)コードの有無 */
  pocAvailable: z.boolean().optional(),

  // --- 検証特性: verification軸のスコアリングに使用 ---

  /** 再現性 (true = 再現可能) */
  reproducible: z.boolean().optional(),

  /** 確認済みエージェント/研究者IDリスト */
  confirmedBy: z.array(z.string()).default([]),

  /** このレコードの取得日時 (デフォルト: 現在時刻) */
  retrievedAt: z.string().datetime().optional(),
});

export type VulnFinding = z.infer<typeof VulnFindingSchema>;

// --- VulnSeverity: 重大度分類 ---

/**
 * 脆弱性の重大度
 * Critical > High > Medium > Low
 *
 * 分類基準:
 * - trustScore: この発見が本物の脆弱性である信頼性 (0-1)
 * - attackEase: 攻撃の容易さ = 実際の脅威レベル (0-1)
 *
 * Critical: trustScore >= 0.7 AND attackEase >= 0.7
 * High:     trustScore >= 0.7 AND attackEase >= 0.4
 *        OR trustScore >= 0.5 AND attackEase >= 0.7
 * Medium:   trustScore >= 0.4 AND attackEase >= 0.3
 * Low:      それ以外
 */
export const VulnSeveritySchema = z.enum(["Critical", "High", "Medium", "Low"]);
export type VulnSeverity = z.infer<typeof VulnSeveritySchema>;

/**
 * Confidence: ConsensusEngineの合議信頼度
 * - High:   unanimous (全エージェント一致) または divergence <= 0.05
 * - Medium: majority (多数決) divergence <= 0.15
 * - Low:    tiebreaker / deadlock
 */
export const ConfidenceLevelSchema = z.enum(["High", "Medium", "Low"]);
export type ConfidenceLevel = z.infer<typeof ConfidenceLevelSchema>;

// --- VulnVerificationResult: 検証結果の出力型 ---

export const VulnVerificationResultSchema = z.object({
  /** 対応するfindingのID */
  findingId: z.string(),

  /** 重大度 (Critical/High/Medium/Low) */
  severity: VulnSeveritySchema,

  /** 合議信頼度 (High/Medium/Low) */
  confidence: ConfidenceLevelSchema,

  /** TrustScorerによる総合スコア (0-1) */
  trustScore: z.number().min(0).max(1),

  /** 攻撃容易度スコア (0-1) */
  attackEaseScore: z.number().min(0).max(1),

  /** 4軸スコア */
  axes: z.object({
    freshness: z.number().min(0).max(1),
    provenance: z.number().min(0).max(1),
    verification: z.number().min(0).max(1),
    attackEase: z.number().min(0).max(1),
  }),

  /** 合議タイプ */
  consensus: z.enum(["unanimous", "majority", "tiebreaker", "deadlock"]),

  /** エージェント間の最大乖離幅 */
  divergence: z.number().min(0).max(1),

  /** 少数意見 (マイノリティの見解を常に保存) */
  dissent: z.array(
    z.object({
      agentId: z.string(),
      trustScore: z.number(),
      reasoning: z.string(),
    }),
  ),

  /** スコアの限界・注意事項 */
  caveats: z.array(z.string()),

  /** 検証理由の説明 */
  reasoning: z.string(),

  /** 検証完了日時 */
  verifiedAt: z.string().datetime(),
});

export type VulnVerificationResult = z.infer<typeof VulnVerificationResultSchema>;
