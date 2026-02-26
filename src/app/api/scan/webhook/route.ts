import { NextRequest, NextResponse } from "next/server";
import { z } from "zod";
import { VulnerabilityScanner } from "../../../../../packages/katala/core/VulnerabilityScanner";

// ============================================================
// POST /api/scan/webhook — CI/CD Integration Webhook
// Handles GitHub Actions push event payloads.
// Call this from your workflow to auto-scan on push.
//
// Usage in .github/workflows/security-scan.yml:
//   - name: Katala Security Scan
//     run: |
//       curl -X POST $KATALA_WEBHOOK_URL \
//         -H "Content-Type: application/json" \
//         -H "X-Hub-Signature-256: ${{ secrets.KATALA_WEBHOOK_SECRET }}" \
//         -d '{"repository":{"clone_url":"${{ github.server_url }}/${{ github.repository }}"}}'
// ============================================================

// GitHub push event (minimal subset we care about)
const GitHubPushPayloadSchema = z.object({
  repository: z.object({
    clone_url: z.string().url(),
    full_name: z.string(),
    default_branch: z.string().optional(),
  }),
  ref: z.string().optional(),
  sender: z.object({ login: z.string() }).optional(),
});

// Generic webhook payload
const GenericWebhookSchema = z.object({
  repoUrl: z.string().url(),
  ref: z.string().optional(),
  minSeverity: z.enum(["Critical", "High", "Medium", "Low", "Info"]).optional(),
});

export async function POST(request: NextRequest) {
  let body: unknown;
  try {
    body = await request.json();
  } catch {
    return NextResponse.json({ error: "Invalid JSON in request body" }, { status: 400 });
  }

  // Detect payload format: GitHub push event vs generic
  let repoUrl: string;
  let triggeredBy = "webhook";

  const githubParsed = GitHubPushPayloadSchema.safeParse(body);
  if (githubParsed.success) {
    repoUrl = githubParsed.data.repository.clone_url;
    triggeredBy = `github-push:${githubParsed.data.repository.full_name}`;
  } else {
    const genericParsed = GenericWebhookSchema.safeParse(body);
    if (!genericParsed.success) {
      return NextResponse.json(
        {
          error: "Unrecognized webhook payload",
          hint: "Expected GitHub push event or { repoUrl: string }",
        },
        { status: 400 }
      );
    }
    repoUrl = genericParsed.data.repoUrl;
  }

  // Validate GitHub/GitLab URL
  if (!repoUrl.startsWith("https://github.com/") && !repoUrl.startsWith("https://gitlab.com/")) {
    return NextResponse.json(
      { error: "Only GitHub and GitLab URLs are supported" },
      { status: 400 }
    );
  }

  const scanner = new VulnerabilityScanner();
  const startedAt = new Date().toISOString();

  try {
    const report = await scanner.scan(repoUrl, {
      minSeverity: "Medium", // Webhooks report Medium+ by default to reduce noise
      maxFiles: 150,
    });

    // Return a condensed response suitable for CI/CD logging
    return NextResponse.json({
      status: "completed",
      triggeredBy,
      startedAt,
      completedAt: new Date().toISOString(),
      repoUrl: report.repoUrl,
      filesScanned: report.filesScanned,
      totalFindings: report.totalFindings,
      findingsBySeverity: report.findingsBySeverity,
      summary: report.summary,
      // Surface only Critical + High findings in webhook response for CI/CD gate decisions
      criticalAndHighFindings: report.findings
        .filter((f) => f.severity === "Critical" || f.severity === "High")
        .map((f) => ({
          id: f.id,
          severity: f.severity,
          title: f.title,
          filePath: f.filePath,
          lineNumber: f.lineNumber,
          cwe: f.cwe,
          remediation: f.remediation,
        })),
    });
  } catch (err) {
    const message = err instanceof Error ? err.message : "Unknown scan error";
    console.error("[scan/webhook] Error:", message);
    return NextResponse.json(
      {
        status: "error",
        triggeredBy,
        startedAt,
        error: message,
      },
      { status: 500 }
    );
  }
}
