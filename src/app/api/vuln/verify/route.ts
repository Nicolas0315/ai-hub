import { NextRequest, NextResponse } from "next/server";
import { z } from "zod";
import { VulnFindingSchema, VulnVerificationPipeline } from "@/lib/vuln";

// ============================================================
// POST /api/vuln/verify
//
// Issue #43: Vulnerability Verification Pipeline API
// VulnFindingを受け取り、TrustScorer + ConsensusEngineで自動検証する。
//
// 単一finding:
//   POST /api/vuln/verify
//   Body: VulnFinding
//
// バッチfinding:
//   POST /api/vuln/verify
//   Body: { findings: VulnFinding[] }
// ============================================================

const SingleRequestSchema = VulnFindingSchema;

const BatchRequestSchema = z.object({
  findings: z.array(VulnFindingSchema).min(1).max(20),
});

const pipeline = new VulnVerificationPipeline();

export async function POST(req: NextRequest) {
  try {
    const body = await req.json();

    // バッチリクエスト判定
    if ("findings" in body && Array.isArray(body.findings)) {
      const parsed = BatchRequestSchema.safeParse(body);
      if (!parsed.success) {
        return NextResponse.json(
          { error: "Validation failed", details: parsed.error.issues },
          { status: 400 },
        );
      }

      const results = await pipeline.verifyBatch(parsed.data.findings);
      return NextResponse.json({
        results,
        total: results.length,
        status: "success",
      });
    }

    // 単一リクエスト
    const parsed = SingleRequestSchema.safeParse(body);
    if (!parsed.success) {
      return NextResponse.json(
        { error: "Validation failed", details: parsed.error.issues },
        { status: 400 },
      );
    }

    const result = await pipeline.verify(parsed.data);
    return NextResponse.json({ result, status: "success" });
  } catch (error) {
    console.error("[VulnVerify API Error]", error);
    return NextResponse.json({ error: "Internal Server Error" }, { status: 500 });
  }
}

/**
 * GET /api/vuln/verify — ヘルスチェック & スキーマ情報
 */
export async function GET() {
  return NextResponse.json({
    endpoint: "POST /api/vuln/verify",
    description: "脆弱性報告をTrustScorer + ConsensusEngineで自動検証",
    version: "1.0.0",
    accepts: {
      single: "VulnFinding",
      batch: "{ findings: VulnFinding[] }",
    },
    severity_levels: ["Critical", "High", "Medium", "Low"],
    confidence_levels: ["High", "Medium", "Low"],
    axes: ["freshness", "provenance", "verification", "attackEase"],
  });
}
