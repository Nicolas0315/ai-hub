import { NextRequest, NextResponse } from "next/server";
import { z } from "zod";
import { IdentityVectorSchema } from "../../../../packages/katala/core/IdentityVector";
import { MatchmakingEngine } from "../../../../packages/katala/core/MatchmakingEngine";

const MatchRequestSchema = z.object({
  source: IdentityVectorSchema,
  candidates: z.array(IdentityVectorSchema).min(1),
  threshold: z.number().min(0).max(1).optional(),
});

const engine = new MatchmakingEngine();

export async function POST(req: NextRequest) {
  try {
    const body = await req.json();
    const parsed = MatchRequestSchema.safeParse(body);
    if (!parsed.success) {
      return NextResponse.json(
        { error: "Validation failed", details: parsed.error.issues },
        { status: 400 },
      );
    }

    const { source, candidates, threshold } = parsed.data;
    const matches = engine.findMatches(source, candidates, threshold);

    return NextResponse.json({
      matches: matches.map((m) => ({ vector: m.vector, score: m.score })),
      total: matches.length,
      status: "success",
    });
  } catch (error) {
    console.error("[Matchmaking API Error]", error);
    return NextResponse.json({ error: "Internal Server Error" }, { status: 500 });
  }
}
