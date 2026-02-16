import { NextRequest, NextResponse } from 'next/server';
import { SynergyEngine, IdentityDimensions, XAlgorithmParams } from '../../../lib/synergy/engine';

const engine = new SynergyEngine();

export async function POST(req: NextRequest) {
  try {
    const body = await req.json();
    const { identityA, identityB, xParams } = body as {
      identityA: IdentityDimensions;
      identityB: IdentityDimensions;
      xParams: XAlgorithmParams;
    };

    if (!identityA || !identityB || !xParams) {
      return NextResponse.json(
        { error: 'Missing required parameters: identityA, identityB, or xParams' },
        { status: 400 }
      );
    }

    const score = engine.getCombinedSynergy(identityA, identityB, xParams);

    return NextResponse.json({
      synergyScore: score,
      status: 'success',
      timestamp: new Date().toISOString()
    });
  } catch (error) {
    console.error('[Synergy API Error]', error);
    return NextResponse.json(
      { error: 'Internal Server Error' },
      { status: 500 }
    );
  }
}
