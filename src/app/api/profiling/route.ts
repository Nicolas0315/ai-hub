import { NextRequest, NextResponse } from "next/server";
import { z } from "zod";
import { IdentityVectorSchema } from "../../../../packages/katala/core/IdentityVector";
import { ProfilingEngine } from "../../../../packages/katala/core/ProfilingEngine";

const ChatMessageSchema = z.object({
  role: z.enum(["user", "assistant"]),
  content: z.string(),
  timestamp: z.string(),
});

const ProfileRequestSchema = z.object({
  currentVector: IdentityVectorSchema,
  history: z.array(ChatMessageSchema).min(1),
});

const TuneRequestSchema = z.object({
  currentVector: IdentityVectorSchema,
  instruction: z.string().min(1),
});

const engine = new ProfilingEngine();

export async function POST(req: NextRequest) {
  try {
    const body = await req.json();
    const { searchParams } = new URL(req.url);
    const mode = searchParams.get("mode");

    if (mode === "tune") {
      const parsed = TuneRequestSchema.safeParse(body);
      if (!parsed.success) {
        return NextResponse.json(
          { error: "Validation failed", details: parsed.error.issues },
          { status: 400 },
        );
      }
      const result = await engine.tuneProfile(parsed.data.currentVector, parsed.data.instruction);
      return NextResponse.json({ vector: result, status: "success" });
    }

    const parsed = ProfileRequestSchema.safeParse(body);
    if (!parsed.success) {
      return NextResponse.json(
        { error: "Validation failed", details: parsed.error.issues },
        { status: 400 },
      );
    }

    const result = await engine.updateProfile(parsed.data.currentVector, parsed.data.history);
    return NextResponse.json({ vector: result, status: "success" });
  } catch (error) {
    console.error("[Profiling API Error]", error);
    return NextResponse.json({ error: "Internal Server Error" }, { status: 500 });
  }
}
