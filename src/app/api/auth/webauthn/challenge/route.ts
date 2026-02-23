import { NextRequest, NextResponse } from "next/server";
import { generateAuthOptions } from "@/lib/auth/webauthn";

/**
 * POST /api/auth/webauthn/challenge
 * Generate a WebAuthn authentication challenge
 */
export async function POST(request: NextRequest) {
  try {
    const body = await request.json();
    const { userID, credentialIDs } = body;

    const options = await generateAuthOptions(userID, credentialIDs);

    // Store challenge in session/cache for later verification
    // TODO: Implement challenge storage (Redis/session)
    
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
