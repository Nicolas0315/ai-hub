import { NextResponse } from "next/server";
import { z } from "zod";
import { detoxText } from "@/lib/mediation/detox";

const ProposeSchema = z.object({
  fromAgentId: z.string().min(1),
  toAgentId: z.string().min(1),
  intent: z.string().min(1),
  constraints: z.array(z.string()).default([]),
});

export async function POST(req: Request) {
  try {
    const body = await req.json();
    const parsed = ProposeSchema.safeParse(body);

    if (!parsed.success) {
      return NextResponse.json(
        { error: "Validation failed", details: parsed.error.issues },
        { status: 400 },
      );
    }

    const proposalId = `prop_${Date.now()}`;
    const proposal = {
      proposalId,
      fromAgentId: parsed.data.fromAgentId,
      toAgentId: parsed.data.toAgentId,
      intent: detoxText(parsed.data.intent),
      constraints: parsed.data.constraints,
      status: "proposed" as const,
      createdAt: new Date().toISOString(),
    };

    return NextResponse.json({ status: "success", proposal }, { status: 201 });
  } catch (error) {
    console.error("[Mediation Propose API Error]", error);
    return NextResponse.json({ error: "Internal Server Error" }, { status: 500 });
  }
}
