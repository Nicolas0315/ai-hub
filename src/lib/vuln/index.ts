// ============================================================
// Vulnerability Verification Pipeline — Public API
// Issue #43: TrustScorer + ConsensusEngine による脆弱性自動検証
// ============================================================

export { VulnVerificationPipeline, calcAttackEase, classifySeverity, classifyConfidence } from "./VulnVerificationPipeline";

export type {
  VulnFinding,
  VulnVerificationResult,
  VulnSeverity,
  ConfidenceLevel,
  ReporterType,
  AttackVector,
  AttackComplexity,
  PrivilegesRequired,
  UserInteraction,
} from "./types";

export {
  VulnFindingSchema,
  VulnVerificationResultSchema,
  VulnSeveritySchema,
  ConfidenceLevelSchema,
} from "./types";

// Issue #44: BLUE Agent Patcher
export { RemediationEngine } from "./RemediationEngine";
export type {
  PatchCandidate,
  PatchStrategy,
  PatchQualityAxes,
  RemediationResult,
  RemediationEvent,
} from "./RemediationEngine";
