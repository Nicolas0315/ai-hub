import { NextRequest, NextResponse } from "next/server";
import { z } from "zod";
import { ImmutableLedger } from "../../../../packages/katala/core/ImmutableLedger";

// Shared ledger instance (prototype; replace with persistent store in production)
const ledger = new ImmutableLedger();

const AppendSchema = z.object({
  eventType: z.string().min(1),
  payload: z.record(z.string(), z.unknown()),
});

export async function GET(req: NextRequest) {
  try {
    const { searchParams } = new URL(req.url);
    const limitParam = searchParams.get("limit");
    const limit = limitParam ? parseInt(limitParam, 10) : undefined;

    if (limitParam && (isNaN(limit!) || limit! < 1)) {
      return NextResponse.json({ error: "Invalid limit parameter" }, { status: 400 });
    }

    const history = ledger.getHistory(limit);
    const valid = await ledger.verify();

    return NextResponse.json({ entries: history, count: history.length, chainValid: valid });
  } catch (error) {
    console.error("[Ledger API Error]", error);
    return NextResponse.json({ error: "Internal Server Error" }, { status: 500 });
  }
}

export async function POST(req: NextRequest) {
  try {
    const body = await req.json();
    const parsed = AppendSchema.safeParse(body);
    if (!parsed.success) {
      return NextResponse.json(
        { error: "Validation failed", details: parsed.error.issues },
        { status: 400 }
      );
    }

    const entry = await ledger.append(parsed.data.eventType, parsed.data.payload as Record<string, unknown>);
    return NextResponse.json({ entry, status: "success" }, { status: 201 });
  } catch (error) {
    console.error("[Ledger API Error]", error);
    return NextResponse.json({ error: "Internal Server Error" }, { status: 500 });
  }
}
