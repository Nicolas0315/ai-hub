import { NextResponse } from "next/server";
import { MediationService } from "../../../../packages/katala/core/MediationService";
import { SynergyRequestSchema, ErrorResponse } from "../../../../packages/katala/core/types";

const mediationService = new MediationService();

function errorResponse(error: string, code: number): NextResponse<ErrorResponse> {
  return NextResponse.json({ error, code }, { status: code });
}

export async function POST(request: Request) {
  try {
    let body: unknown;
    try {
      body = await request.json();
    } catch {
      return errorResponse("Invalid JSON body", 400);
    }

    const parsed = SynergyRequestSchema.safeParse(body);
    if (!parsed.success) {
      const message = parsed.error.issues
        .map((i) => `${i.path.join(".")}: ${i.message}`)
        .join("; ");
      return errorResponse(message, 400);
    }

    const result = await mediationService.calculateSynergy(parsed.data);
    return NextResponse.json(result);
  } catch {
    return errorResponse("Internal server error", 500);
  }
}
