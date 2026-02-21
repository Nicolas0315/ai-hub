export type IdentityTier = "T0" | "T1" | "T2" | "T3";
export type ActionRisk = "low" | "medium" | "high";

export interface InclusionContext {
  tier: IdentityTier;
  actionRisk: ActionRisk;
  hasDuressFlag?: boolean;
  replayDetected?: boolean;
  suspiciousResetPattern?: boolean;
}

export interface InclusionDecision {
  allow: boolean;
  requireDelayedExecution: boolean;
  freezePrivileges: boolean;
  reasonCodes: string[];
}

const TIER_SCORE: Record<IdentityTier, number> = {
  T0: 0,
  T1: 1,
  T2: 2,
  T3: 3,
};

const RISK_REQUIRED_TIER: Record<ActionRisk, number> = {
  low: 0,
  medium: 1,
  high: 2,
};

export function evaluateInclusionGuard(ctx: InclusionContext): InclusionDecision {
  const reasonCodes: string[] = [];

  if (ctx.replayDetected) {
    reasonCodes.push("replay_detected");
    return {
      allow: false,
      requireDelayedExecution: false,
      freezePrivileges: true,
      reasonCodes,
    };
  }

  if (ctx.suspiciousResetPattern) {
    reasonCodes.push("suspicious_reset_pattern");
    return {
      allow: false,
      requireDelayedExecution: false,
      freezePrivileges: true,
      reasonCodes,
    };
  }

  const tierScore = TIER_SCORE[ctx.tier];
  const needed = RISK_REQUIRED_TIER[ctx.actionRisk];

  if (tierScore < needed) {
    reasonCodes.push("tier_insufficient");
    return {
      allow: false,
      requireDelayedExecution: false,
      freezePrivileges: false,
      reasonCodes,
    };
  }

  if (ctx.hasDuressFlag && ctx.actionRisk !== "low") {
    reasonCodes.push("duress_protection");
    return {
      allow: true,
      requireDelayedExecution: true,
      freezePrivileges: false,
      reasonCodes,
    };
  }

  reasonCodes.push("allowed");
  return {
    allow: true,
    requireDelayedExecution: false,
    freezePrivileges: false,
    reasonCodes,
  };
}
