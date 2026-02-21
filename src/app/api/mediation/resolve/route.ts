import { NextResponse } from "next/server";
import { z } from "zod";

const ResolveSchema = z.object({
  proposalId: z.string().min(1),
  accepted: z.boolean(),
  reason: z.string().optional(),
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

    const resolution = {
      proposalId: parsed.data.proposalId,
      status: parsed.data.accepted ? "agreed" : "rejected",
      reason: parsed.data.reason ?? null,
      resolvedAt: new Date().toISOString(),
    };

    return NextResponse.json({ status: "success", resolution });
  } catch (error) {
    console.error("[Mediation Resolve API Error]", error);
    return NextResponse.json({ error: "Internal Server Error" }, { status: 500 });
  }
}
