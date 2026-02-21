export type VisibilityLevel = "L0" | "L1" | "L2";

export interface OpenThresholdInput {
  domain?: "general" | "medical" | "finance" | "minor" | "identity";
  containsBiometric?: boolean;
  containsGovId?: boolean;
  containsContact?: boolean;
  containsRawText?: boolean;
  containsMinor?: boolean;
  kAnonymity?: number;
  dpEpsilon?: number;
}

export interface OpenThresholdDecision {
  level: VisibilityLevel;
  collect: boolean;
  open: boolean;
  reasons: string[];
}

export function classifyOpenThreshold(input: OpenThresholdInput): OpenThresholdDecision {
  const reasons: string[] = [];
  const domain = input.domain ?? "general";

  const highRisk =
    domain === "medical" ||
    domain === "finance" ||
    domain === "minor" ||
    domain === "identity" ||
    input.containsBiometric ||
    input.containsGovId ||
    input.containsMinor;

  if (highRisk) {
    reasons.push("high_risk_domain_or_identifier");
    return { level: "L2", collect: false, open: false, reasons };
  }

  const mediumRisk = input.containsContact || input.containsRawText;
  if (mediumRisk) {
    reasons.push("raw_or_contact_data_detected");
    const k = input.kAnonymity ?? 0;
    const eps = input.dpEpsilon ?? Number.POSITIVE_INFINITY;
    const open = k >= 20 && eps <= 1;
    if (!open) reasons.push("anonymization_threshold_not_met");
    return { level: "L1", collect: true, open, reasons };
  }

  reasons.push("safe_distilled_signal");
  return { level: "L0", collect: true, open: true, reasons };
}

export function classifyReason(reason?: string): string | null {
  if (!reason) return null;
  if (/(金|費用|price|cost)/i.test(reason)) return "pricing";
  if (/(期限|日程|schedule|deadline)/i.test(reason)) return "schedule";
  if (/(品質|quality|仕様|spec)/i.test(reason)) return "quality_or_spec";
  if (/(権限|permission|承認|approve)/i.test(reason)) return "permission";
  return "other";
}
