// ============================================================
// Vulnerability Verification Pipeline — Public API
// Issue #43: TrustScorer + ConsensusEngine による脆弱性自動検証
// ============================================================

export { VulnVerificationPipeline, calcAttackEase, classifySeverity, classifyConfidence } from "./VulnVerificationPipeline";

// ============================================================
// ZK-lite Secure Disclosure — Public API
// Issue #45: ZK-lite による安全な脆弱性開示
// ============================================================

export { SecureDisclosureManager } from "./ZkLiteDisclosure";
export type {
  VulnCategory,
  ProofStatus,
  ZkLiteProof,
  VulnFullReport,
  ZkRevocation,
  DisclosureInput,
} from "./ZkLiteDisclosure";

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
