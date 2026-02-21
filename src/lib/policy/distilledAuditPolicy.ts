export type Purpose = "safety" | "reliability" | "compliance";

export interface DistilledAuditInput {
  purpose: Purpose;
  actorOverride?: boolean;
  eventType: string;
  containsRawContent?: boolean;
}

export interface DistilledAuditDecision {
  allowCollect: boolean;
  allowPersist: boolean;
  ttlHours: number;
  auditRequired: boolean;
  reasons: string[];
}

const PURPOSE_TTL: Record<Purpose, number> = {
  safety: 24 * 30,
  reliability: 24 * 14,
  compliance: 24 * 90,
};

export function evaluateDistilledAudit(input: DistilledAuditInput): DistilledAuditDecision {
  const reasons: string[] = [];

  if (input.actorOverride) {
    reasons.push("human_override_opt_out");
    return {
      allowCollect: false,
      allowPersist: false,
      ttlHours: 0,
      auditRequired: true,
      reasons,
    };
  }

  if (input.containsRawContent) {
    reasons.push("raw_content_not_allowed");
    return {
      allowCollect: false,
      allowPersist: false,
      ttlHours: 0,
      auditRequired: true,
      reasons,
    };
  }

  reasons.push(`purpose:${input.purpose}`);
  return {
    allowCollect: true,
    allowPersist: true,
    ttlHours: PURPOSE_TTL[input.purpose],
    auditRequired: true,
    reasons,
  };
}
