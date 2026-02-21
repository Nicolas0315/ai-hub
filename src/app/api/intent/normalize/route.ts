import { NextResponse } from "next/server";
import { z } from "zod";
import { detoxText, inferPriority } from "@/lib/mediation/detox";

const NormalizeSchema = z.object({
  text: z.string().min(1),
  counterparty: z.string().optional(),
  deadline: z.string().datetime().nullable().optional(),
  constraints: z.array(z.string()).optional(),
});

export async function POST(req: Request) {
  try {
    const body = await req.json();
    const parsed = NormalizeSchema.safeParse(body);

    if (!parsed.success) {
      return NextResponse.json(
        { error: "Validation failed", details: parsed.error.issues },
        { status: 400 },
      );
    }

    const text = parsed.data.text;
    const normalized = {
      intent: detoxText(text),
      goal: detoxText(text),
      constraints: parsed.data.constraints ?? [],
      deadline: parsed.data.deadline ?? null,
      priority: inferPriority(text),
      counterparty: parsed.data.counterparty ?? "unknown",
    };

    return NextResponse.json({ status: "success", normalized });
  } catch (error) {
    console.error("[Intent Normalize API Error]", error);
    return NextResponse.json({ error: "Internal Server Error" }, { status: 500 });
  }
}
