import { NextRequest, NextResponse } from "next/server";
import { z } from "zod";
import { importCsv } from "../../../../packages/katala/core/CsvImporter";

const ImportRequestSchema = z.object({
  csv: z.string().min(1),
  batchSize: z.number().int().positive().optional(),
});

export async function POST(req: NextRequest) {
  try {
    const body = await req.json();
    const parsed = ImportRequestSchema.safeParse(body);
    if (!parsed.success) {
      return NextResponse.json(
        { error: "Validation failed", details: parsed.error.issues },
        { status: 400 },
      );
    }

    const result = await importCsv(parsed.data.csv, {
      batchSize: parsed.data.batchSize,
    });

    return NextResponse.json({
      imported: result.success.length,
      errors: result.errors,
      totalRows: result.totalRows,
      vectors: result.success,
      status: "success",
    });
  } catch (error) {
    console.error("[Import API Error]", error);
    return NextResponse.json({ error: "Internal Server Error" }, { status: 500 });
  }
}
