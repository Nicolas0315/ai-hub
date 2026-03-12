import { NextResponse } from "next/server";
import { z } from "zod";
import { distillSceneText } from "@/lib/multimodal/sceneChannels";

const DistillSchema = z.object({
  text: z.string().min(1),
});

export async function POST(req: Request) {
  try {
    const body = await req.json();
    const parsed = DistillSchema.safeParse(body);

    if (!parsed.success) {
      return NextResponse.json(
        { error: "Validation failed", details: parsed.error.issues },
        { status: 400 },
      );
    }

    const result = distillSceneText(parsed.data.text);
    return NextResponse.json({ status: "success", result }, { status: 201 });
  } catch (error) {
    console.error("[Multimodal Distill API Error]", error);
    return NextResponse.json({ error: "Internal Server Error" }, { status: 500 });
  }
}
