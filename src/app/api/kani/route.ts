import { NextRequest, NextResponse } from 'next/server';
import { kaniClient } from '@/lib/kani';
import type { KaniMediationRequest } from '@/lib/kani';

export async function POST(request: NextRequest) {
  try {
    const body = await request.json();
    const mediationRequest = body as KaniMediationRequest;

    // Validate request structure
    if (!mediationRequest.identityA || !mediationRequest.identityB || !mediationRequest.xParams) {
      return NextResponse.json(
        { error: 'Missing required parameters: identityA, identityB, or xParams' },
        { status: 400 }
      );
    }

    // Use Kani client with retry logic and fallback
    const response = await kaniClient.mediate(mediationRequest);

    return NextResponse.json(response);
  } catch (error) {
    console.error('[Kani API Route Error]', error);
    return NextResponse.json(
      { error: 'Failed to process mediation request' },
      { status: 500 }
    );
  }
}

export async function GET() {
  try {
    const isHealthy = await kaniClient.healthCheck();
    return NextResponse.json({
      status: isHealthy ? 'healthy' : 'degraded',
      timestamp: new Date().toISOString(),
    });
  } catch (error) {
    console.error('[Kani Health Check Error]', error);
    return NextResponse.json(
      { status: 'unhealthy', timestamp: new Date().toISOString() },
      { status: 503 }
    );
  }
}
