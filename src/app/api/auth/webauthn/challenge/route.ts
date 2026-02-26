import { NextRequest, NextResponse } from "next/server";
import { generateAuthOptions } from "@/lib/auth/webauthn";

/**
 * POST /api/auth/webauthn/challenge
 * Generate and store a server-side WebAuthn challenge (TTL: 5 minutes)
 */
export async function POST(request: NextRequest) {
  try {
    const body = await request.json();
    const { userID } = body as { userID?: string };

    if (!userID) {
      return NextResponse.json(
        {
          success: false,
          error: "Missing required parameter: userID",
        },
        { status: 400 }
      );
    }

    const options = await generateAuthOptions(userID);

    return NextResponse.json({
      success: true,
      data: options,
    });
  } catch (error) {
    console.error("WebAuthn challenge generation failed:", error);
    return NextResponse.json(
      {
        success: false,
        error: "Failed to generate challenge",
        details: error instanceof Error ? error.message : "Unknown error",
      },
      { status: 500 }
    );
  }
}
