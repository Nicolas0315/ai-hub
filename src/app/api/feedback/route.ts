import { existsSync } from "fs";
import { writeFile, mkdir } from "fs/promises";
import { NextRequest, NextResponse } from "next/server";
import path from "path";

interface FeedbackData {
  mediationScore: number;
  userRating: number;
  comment: string;
  timestamp: string;
}

export async function POST(request: NextRequest) {
  try {
    const body = await request.json();
    const feedback: FeedbackData = body;

    // Validate feedback data
    if (
      typeof feedback.mediationScore !== "number" ||
      typeof feedback.userRating !== "number" ||
      feedback.userRating < 1 ||
      feedback.userRating > 5
    ) {
      return NextResponse.json({ error: "Invalid feedback data" }, { status: 400 });
    }

    // Store feedback in memory directory (JSON file)
    const memoryDir = path.join(process.cwd(), "memory");
    if (!existsSync(memoryDir)) {
      await mkdir(memoryDir, { recursive: true });
    }

    const feedbackFile = path.join(memoryDir, "feedback.jsonl");
    const feedbackLine =
      JSON.stringify({
        ...feedback,
        id: `feedback_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`,
        receivedAt: new Date().toISOString(),
      }) + "\n";

    // Append to JSONL file
    await writeFile(feedbackFile, feedbackLine, { flag: "a" });

    console.log("[Feedback API] ✓ Feedback stored:", {
      rating: feedback.userRating,
      mediationScore: feedback.mediationScore,
    });

    return NextResponse.json({
      success: true,
      message: "Feedback received",
    });
  } catch (error) {
    console.error("[Feedback API Error]", error);
    return NextResponse.json({ error: "Failed to process feedback" }, { status: 500 });
  }
}

export async function GET() {
  return NextResponse.json({
    status: "ready",
    endpoint: "/api/feedback",
    methods: ["POST"],
  });
}
