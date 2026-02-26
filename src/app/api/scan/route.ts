import { NextRequest, NextResponse } from "next/server";
import { z } from "zod";
import { VulnerabilityScanner, ScanConfig } from "../../../../packages/katala/core/VulnerabilityScanner";

// ============================================================
// POST /api/scan — GitHub リポジトリのセキュリティスキャン
// CI/CD webhook でも利用可能
// Issue #42: Vulnerability Mesh - Discovery Layer
// ============================================================

const ScanRequestSchema = z.object({
  /** GitHub repository URL (e.g. https://github.com/org/repo) */
  repoUrl: z.string().url(),
  /** Optional scan configuration overrides */
  config: z
    .object({
      includePatterns: z.array(z.string()).optional(),
      excludePatterns: z.array(z.string()).optional(),
      maxFiles: z.number().min(1).max(1000).optional(),
      maxFileSizeBytes: z.number().optional(),
      minSeverity: z
        .enum(["Critical", "High", "Medium", "Low", "Info"])
        .optional(),
      domain: z.string().optional(),
    })
    .optional(),
  /** If true, return only the summary and finding counts (faster response) */
  summaryOnly: z.boolean().optional().default(false),
});

export async function POST(request: NextRequest) {
  let body: unknown;
  try {
    body = await request.json();
  } catch {
    return NextResponse.json({ error: "Invalid JSON in request body" }, { status: 400 });
  }

  const parsed = ScanRequestSchema.safeParse(body);
  if (!parsed.success) {
    return NextResponse.json(
      { error: "Invalid request", details: parsed.error.format() },
      { status: 400 }
    );
  }

  const { repoUrl, config, summaryOnly } = parsed.data;

  // Validate that the URL is a GitHub repository
  if (!repoUrl.startsWith("https://github.com/") && !repoUrl.startsWith("https://gitlab.com/")) {
    return NextResponse.json(
      { error: "Only GitHub and GitLab repository URLs are supported" },
      { status: 400 }
    );
  }

  const scanner = new VulnerabilityScanner();

  try {
    const report = await scanner.scan(repoUrl, (config as Partial<ScanConfig>) ?? {});

    if (summaryOnly) {
      return NextResponse.json({
        repoUrl: report.repoUrl,
        scannedAt: report.scannedAt,
        filesScanned: report.filesScanned,
        totalFindings: report.totalFindings,
        findingsBySeverity: report.findingsBySeverity,
        summary: report.summary,
      });
    }

    return NextResponse.json(report);
  } catch (err) {
    const message = err instanceof Error ? err.message : "Unknown scan error";
    console.error("[scan] Error:", message);
    return NextResponse.json({ error: message }, { status: 500 });
  }
}

// ============================================================
// POST /api/scan (webhook variant) — CI/CD Integration
// Handles GitHub Actions / GitLab CI webhook payloads
// Triggered by push events to scan the changed repository
// ============================================================

/**
 * GET /api/scan — health check for webhook configuration
 */
export async function GET() {
  return NextResponse.json({
    status: "ok",
    description: "Katala Vulnerability Scanner — Discovery Layer (Issue #42)",
    endpoints: {
      "POST /api/scan": {
        description: "Scan a GitHub/GitLab repository for vulnerabilities",
        body: {
          repoUrl: "string (required) — repository URL",
          config: "object (optional) — scan configuration overrides",
          summaryOnly: "boolean (optional) — return summary only",
        },
      },
      "POST /api/scan/webhook": {
        description: "CI/CD webhook endpoint (GitHub Actions / GitLab CI)",
        body: "GitHub push event payload or { repoUrl, ref }",
      },
    },
    supportedRules: [
      "SEC-001: Hardcoded API Key",
      "SEC-002: Hardcoded Password",
      "SEC-003: Private Key in Source",
      "INJ-001: SQL Injection",
      "INJ-002: eval() Usage",
      "INJ-003: Command Injection",
      "XSS-001: Dangerous innerHTML",
      "XSS-002: dangerouslySetInnerHTML",
      "CRYPTO-001: Insecure Random",
      "CRYPTO-002: MD5 Hash",
      "CFG-001: Debug Mode Enabled",
      "CFG-002: Prototype Pollution",
      "CFG-003: CORS Wildcard",
    ],
  });
}
