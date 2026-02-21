import { NextResponse } from "next/server";
import { z } from "zod";
import { sharedLedger } from "@/lib/ledger/store";
import { verifyHumanIntentSignature } from "@/lib/auth/humanSignature";
import { classifyOpenThreshold, classifyReason } from "@/lib/policy/openThreshold";

const ResolveSchema = z.object({
  proposalId: z.string().min(1),
  accepted: z.boolean(),
  reason: z.string().optional(),
  actorId: z.string().min(1),
  nonce: z.string().min(1),
  signature: z.string().min(1),
});

export async function POST(req: Request) {
  try {
    const body = await req.json();
    const parsed = ResolveSchema.safeParse(body);

    if (!parsed.success) {
      return NextResponse.json(
        { error: "Validation failed", details: parsed.error.issues },
        { status: 400 },
      );
    }

    const signingMessage = `${parsed.data.actorId}:${parsed.data.proposalId}:${parsed.data.accepted}:${parsed.data.nonce}`;
    const signatureValid = verifyHumanIntentSignature(signingMessage, parsed.data.signature);

    if (!signatureValid) {
      return NextResponse.json({ error: "Invalid human-layer signature" }, { status: 401 });
    }

    const policy = classifyOpenThreshold({
      domain: "general",
      containsRawText: Boolean(parsed.data.reason),
      containsContact: /(@|\d{2,4}-\d{2,4}-\d{3,4}|https?:\/\/)/.test(parsed.data.reason ?? ""),
      kAnonymity: 20,
      dpEpsilon: 1,
    });

    const reasonCategory = classifyReason(parsed.data.reason);

    const resolution = {
      proposalId: parsed.data.proposalId,
      status: parsed.data.accepted ? "agreed" : "rejected",
      reasonCategory,
      actorId: parsed.data.actorId,
      resolvedAt: new Date().toISOString(),
      policy,
    };

    if (policy.collect) {
      await sharedLedger.append("mediation.resolved", {
        proposalId: parsed.data.proposalId,
        actorId: parsed.data.actorId,
        accepted: parsed.data.accepted,
        reasonCategory,
        nonce: parsed.data.nonce,
        visibility: policy.level,
        openAllowed: policy.open,
      });
    }

    return NextResponse.json({ status: "success", resolution });
  } catch (error) {
    console.error("[Mediation Resolve API Error]", error);
    return NextResponse.json({ error: "Internal Server Error" }, { status: 500 });
  }
}
