import { createHash } from "crypto";
import { z } from "zod";
import { VulnFinding, VulnVerificationResult, VulnSeverity } from "./types";

// ============================================================
// Remediation Engine — BLUE Agent Patcher
//
// Issue #44: 検証済み脆弱性に対してBLUEエージェントが自動で
// パッチ提案を生成し、品質をTrustScorerで評価するエンジン。
//
// パイプライン:
//   1. VulnVerificationResultを入力として受け取る
//   2. 脆弱性カテゴリに応じたパッチ戦略を選択
//   3. パッチ候補を生成（static + heuristic）
//   4. TrustScorerでパッチ品質を評価（新たな脆弱性を生まないか）
//   5. PRサブミット記録をImmutableLedger互換形式で出力
//   6. 成功率・品質メトリクスを記録
//
// ============================================================

// --- パッチ品質の軸 ---

/**
 * パッチ品質の4軸
 * - correctness: パッチが脆弱性を適切に修正しているか
 * - safety: パッチ自体が新たなリスクを生まないか
 * - testability: パッチの動作を検証できるテストケースが提案されているか
 * - invasiveness: 既存コードへの影響範囲（低いほど良い）
 */
export const PatchQualityAxesSchema = z.object({
  correctness: z.number().min(0).max(1),
  safety: z.number().min(0).max(1),
  testability: z.number().min(0).max(1),
  invasiveness: z.number().min(0).max(1), // 1 = 非侵襲的（良い）
});
export type PatchQualityAxes = z.infer<typeof PatchQualityAxesSchema>;

/**
 * パッチ戦略の種別
 */
export const PatchStrategySchema = z.enum([
  "input-validation",  // 入力バリデーション強化
  "sanitization",      // 出力のサニタイズ
  "parameterization",  // パラメータ化クエリ
  "access-control",    // アクセス制御強化
  "crypto-upgrade",    // 暗号化アルゴリズム更新
  "dependency-update", // 依存パッケージ更新
  "config-hardening",  // 設定のハードニング
  "code-removal",      // 危険なコードの削除
  "generic",           // 汎用的な改善提案
]);
export type PatchStrategy = z.infer<typeof PatchStrategySchema>;

/**
 * パッチ候補
 */
export const PatchCandidateSchema = z.object({
  id: z.string(),
  findingId: z.string(),
  strategy: PatchStrategySchema,
  title: z.string(),
  description: z.string(),
  /** 推奨修正コード（サンプル）*/
  codeExample: z.string().optional(),
  /** テストケース提案 */
  testSuggestion: z.string().optional(),
  /** 関連するCWE/OWASP参照 */
  references: z.array(z.string()),
  /** 修正の信頼スコア (0-1) */
  qualityScore: z.number().min(0).max(1),
  /** 品質軸の詳細 */
  qualityAxes: PatchQualityAxesSchema,
  generatedAt: z.string().datetime(),
});
export type PatchCandidate = z.infer<typeof PatchCandidateSchema>;

/**
 * Remediationの最終結果
 */
export const RemediationResultSchema = z.object({
  findingId: z.string(),
  verificationResult: z.object({
    severity: z.enum(["Critical", "High", "Medium", "Low"]),
    confidence: z.enum(["High", "Medium", "Low"]),
    trustScore: z.number(),
  }),
  /** 選択されたベストパッチ候補 */
  selectedPatch: PatchCandidateSchema,
  /** 全候補（評価用） */
  allCandidates: z.array(PatchCandidateSchema),
  /** PRサブミット記録（ImmutableLedger互換） */
  prRecord: z.object({
    patchId: z.string(),
    targetRepo: z.string().optional(),
    branchName: z.string(),
    prTitle: z.string(),
    prBody: z.string(),
    submittedAt: z.string().datetime(),
    status: z.enum(["draft", "submitted", "rejected", "merged"]),
  }),
  /** 成功率メトリクス */
  metrics: z.object({
    candidatesGenerated: z.number(),
    avgQualityScore: z.number(),
    selectedQualityScore: z.number(),
    generationTimeMs: z.number(),
  }),
  remediatedAt: z.string().datetime(),
});
export type RemediationResult = z.infer<typeof RemediationResultSchema>;

// --- Immutable Ledgerイベント型 ---
export type RemediationEvent =
  | { type: "FINDING_RECEIVED"; findingId: string; severity: VulnSeverity; ts: string }
  | { type: "PATCH_GENERATED"; findingId: string; patchId: string; strategy: PatchStrategy; qualityScore: number; ts: string }
  | { type: "PATCH_SELECTED"; findingId: string; patchId: string; qualityScore: number; ts: string }
  | { type: "PR_SUBMITTED"; findingId: string; patchId: string; prTitle: string; targetRepo: string | undefined; ts: string }
  | { type: "REMEDIATION_COMPLETE"; findingId: string; patchId: string; metricsAvgQuality: number; ts: string };

// ============================================================
// RemediationEngine
// ============================================================

export class RemediationEngine {
  // ImmutableLedger互換のイベントログ
  private readonly eventLog: RemediationEvent[] = [];
  // メトリクス蓄積（成功率などの集計用）
  private readonly metrics: {
    totalAttempts: number;
    successCount: number;
    totalQualityScore: number;
    totalTimeMs: number;
  } = { totalAttempts: 0, successCount: 0, totalQualityScore: 0, totalTimeMs: 0 };

  /**
   * メインエントリ: VulnFinding + VulnVerificationResultを受け取り
   * パッチを生成・評価し、PRレコードを返す。
   */
  async remediate(
    finding: VulnFinding,
    verificationResult: Pick<VulnVerificationResult, "severity" | "confidence" | "trustScore">,
  ): Promise<RemediationResult> {
    const startTs = Date.now();
    this.metrics.totalAttempts++;

    this.logEvent({
      type: "FINDING_RECEIVED",
      findingId: finding.id,
      severity: verificationResult.severity,
      ts: new Date().toISOString(),
    });

    // 1. パッチ候補を生成
    const candidates = this.generateCandidates(finding);

    // 2. 各候補の品質をTrustScorer基準で評価
    const evaluated = candidates.map((c) => this.evaluateCandidate(c, finding));

    // 3. 最高品質のパッチを選択
    const selected = evaluated.reduce((best, c) => (c.qualityScore > best.qualityScore ? c : best));

    this.logEvent({
      type: "PATCH_GENERATED",
      findingId: finding.id,
      patchId: selected.id,
      strategy: selected.strategy,
      qualityScore: selected.qualityScore,
      ts: new Date().toISOString(),
    });

    this.logEvent({
      type: "PATCH_SELECTED",
      findingId: finding.id,
      patchId: selected.id,
      qualityScore: selected.qualityScore,
      ts: new Date().toISOString(),
    });

    // 4. PRレコード生成
    const prRecord = this.buildPrRecord(finding, selected, verificationResult.severity);

    this.logEvent({
      type: "PR_SUBMITTED",
      findingId: finding.id,
      patchId: selected.id,
      prTitle: prRecord.prTitle,
      targetRepo: finding.targetRepo,
      ts: new Date().toISOString(),
    });

    const endTs = Date.now();
    const generationTimeMs = endTs - startTs;

    const avgQuality = evaluated.reduce((s, c) => s + c.qualityScore, 0) / evaluated.length;

    this.metrics.successCount++;
    this.metrics.totalQualityScore += selected.qualityScore;
    this.metrics.totalTimeMs += generationTimeMs;

    this.logEvent({
      type: "REMEDIATION_COMPLETE",
      findingId: finding.id,
      patchId: selected.id,
      metricsAvgQuality: avgQuality,
      ts: new Date().toISOString(),
    });

    const result: RemediationResult = {
      findingId: finding.id,
      verificationResult: {
        severity: verificationResult.severity,
        confidence: verificationResult.confidence,
        trustScore: verificationResult.trustScore,
      },
      selectedPatch: selected,
      allCandidates: evaluated,
      prRecord,
      metrics: {
        candidatesGenerated: evaluated.length,
        avgQualityScore: avgQuality,
        selectedQualityScore: selected.qualityScore,
        generationTimeMs,
      },
      remediatedAt: new Date().toISOString(),
    };

    return result;
  }

  /**
   * 複数findingをバッチ処理
   */
  async remediateAll(
    findings: VulnFinding[],
    verificationResults: Map<string, Pick<VulnVerificationResult, "severity" | "confidence" | "trustScore">>,
  ): Promise<RemediationResult[]> {
    const results: RemediationResult[] = [];
    for (const finding of findings) {
      const vr = verificationResults.get(finding.id);
      if (!vr) continue;
      const result = await this.remediate(finding, vr);
      results.push(result);
    }
    return results;
  }

  /**
   * イベントログを取得（ImmutableLedger互換）
   */
  getEventLog(): readonly RemediationEvent[] {
    return this.eventLog;
  }

  /**
   * 集計メトリクスを取得
   */
  getAggregateMetrics() {
    const { totalAttempts, successCount, totalQualityScore, totalTimeMs } = this.metrics;
    return {
      totalAttempts,
      successCount,
      successRate: totalAttempts > 0 ? successCount / totalAttempts : 0,
      avgQualityScore: successCount > 0 ? totalQualityScore / successCount : 0,
      avgGenerationTimeMs: successCount > 0 ? totalTimeMs / successCount : 0,
    };
  }

  // ============================================================
  // PRIVATE: パッチ候補の生成
  // ============================================================

  /**
   * VulnFindingの内容から、適切なパッチ候補を生成する。
   * heuristicベース: descriptionとcweからルールを適用。
   */
  private generateCandidates(finding: VulnFinding): PatchCandidate[] {
    const strategies = this.selectStrategies(finding);
    return strategies.map((strategy) => this.buildCandidate(finding, strategy));
  }

  /**
   * 脆弱性の内容から適切な修正戦略を選択する
   */
  /**
   * CWE番号の完全一致マッチ（サブストリング誤検知を防ぐ）
   * "CWE-79" が "CWE-798" にマッチしないようにする
   */
  private matchesCwe(cwe: string, ...ids: string[]): boolean {
    if (!cwe) return false;
    const normalized = cwe.toUpperCase().replace(/\s+/g, "");
    return ids.some((id) => {
      const pattern = id.toUpperCase();
      // exact match or comma/semicolon separated list
      return (
        normalized === pattern ||
        normalized.startsWith(pattern + ",") ||
        normalized.endsWith("," + pattern) ||
        normalized.includes("," + pattern + ",")
      );
    });
  }

  private selectStrategies(finding: VulnFinding): PatchStrategy[] {
    const desc = (finding.description + " " + finding.title).toLowerCase();
    const cwe = finding.cwe ?? "";

    const strategies = new Set<PatchStrategy>();

    // SQL Injection (CWE-89)
    if (this.matchesCwe(cwe, "CWE-89", "CWE-564") || desc.includes("sql") || desc.includes("sql injection")) {
      strategies.add("parameterization");
      strategies.add("input-validation");
    }

    // XSS (CWE-79, CWE-80)
    if (this.matchesCwe(cwe, "CWE-79", "CWE-80") || desc.includes("xss") || desc.includes("cross-site scripting") || desc.includes("innerhtml")) {
      strategies.add("sanitization");
      strategies.add("input-validation");
    }

    // Command Injection (CWE-78, CWE-77, CWE-95)
    if (this.matchesCwe(cwe, "CWE-78", "CWE-77", "CWE-95") || desc.includes("command injection") || desc.includes("eval(") || desc.includes("code injection")) {
      strategies.add("input-validation");
      strategies.add("code-removal");
    }

    // Hardcoded secrets (CWE-798, CWE-259, CWE-321)
    if (this.matchesCwe(cwe, "CWE-798", "CWE-259", "CWE-321") ||
        desc.includes("hardcoded") || desc.includes("hardcode") || desc.includes("api key")) {
      strategies.add("config-hardening");
    }

    // Weak crypto (CWE-338, CWE-327, CWE-328)
    if (this.matchesCwe(cwe, "CWE-338", "CWE-327", "CWE-328") || desc.includes("md5") ||
        desc.includes("math.random") || desc.includes("weak crypto") || desc.includes("weak hash")) {
      strategies.add("crypto-upgrade");
    }

    // Prototype pollution (CWE-1321)
    if (this.matchesCwe(cwe, "CWE-1321") || desc.includes("prototype pollution")) {
      strategies.add("input-validation");
      strategies.add("config-hardening");
    }

    // CORS wildcard (CWE-942)
    if (this.matchesCwe(cwe, "CWE-942") || desc.includes("cors")) {
      strategies.add("access-control");
      strategies.add("config-hardening");
    }

    // Debug mode / information disclosure (CWE-489)
    if (this.matchesCwe(cwe, "CWE-489") || desc.includes("debug mode") || desc.includes("information disclosure")) {
      strategies.add("config-hardening");
    }

    // Access control issues (CWE-284, CWE-285, CWE-306)
    if (this.matchesCwe(cwe, "CWE-284", "CWE-285", "CWE-306") ||
        desc.includes("access control") || desc.includes("broken auth") || desc.includes("privilege escalation")) {
      strategies.add("access-control");
    }

    // Dependency vulnerabilities (CWE-1104)
    if (this.matchesCwe(cwe, "CWE-1104") || desc.includes("vulnerable dependency") || desc.includes("outdated package")) {
      strategies.add("dependency-update");
    }

    // Default: generic if nothing matched
    if (strategies.size === 0) {
      strategies.add("generic");
    }

    // Return top 3 strategies max (avoid noise)
    return Array.from(strategies).slice(0, 3);
  }

  /**
   * 戦略に応じたパッチ候補を構築する
   */
  private buildCandidate(finding: VulnFinding, strategy: PatchStrategy): PatchCandidate {
    const id = createHash("sha256")
      .update(`${finding.id}:${strategy}`)
      .digest("hex")
      .slice(0, 16);

    const now = new Date().toISOString();

    switch (strategy) {
      case "input-validation":
        return {
          id,
          findingId: finding.id,
          strategy,
          title: "入力バリデーション強化",
          description: "ユーザー入力をZodスキーマで厳密にバリデーションし、不正な入力を早期に拒否する。",
          codeExample: `// Before (vulnerable)
const value = req.body.input;

// After (safe)
import { z } from "zod";
const schema = z.string().max(255).regex(/^[a-zA-Z0-9_-]+$/);
const result = schema.safeParse(req.body.input);
if (!result.success) {
  return res.status(400).json({ error: "Invalid input" });
}
const value = result.data;`,
          testSuggestion: `it("should reject invalid input", () => {
  const res = handler({ body: { input: "' OR 1=1--" } });
  expect(res.status).toBe(400);
});`,
          references: ["CWE-20", "OWASP A03:2021 Injection"],
          qualityScore: 0,
          qualityAxes: { correctness: 0, safety: 0, testability: 0, invasiveness: 0 },
          generatedAt: now,
        };

      case "sanitization":
        return {
          id,
          findingId: finding.id,
          strategy,
          title: "出力サニタイズ",
          description: "HTMLコンテキストへの出力時にエスケープ処理を適用し、XSSを防ぐ。",
          codeExample: `// Before (vulnerable)
element.innerHTML = userInput;

// After (safe)
import { escapeHtml } from "@/lib/utils/escape";
element.textContent = userInput; // DOM APIを使う（最善）
// OR
element.innerHTML = escapeHtml(userInput); // 必要な場合のみ

// escapeHtml実装例
function escapeHtml(str: string): string {
  return str
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}`,
          testSuggestion: `it("should escape XSS payload", () => {
  const input = '<script>alert("xss")</script>';
  const safe = escapeHtml(input);
  expect(safe).not.toContain("<script>");
  expect(safe).toBe('&lt;script&gt;alert(&quot;xss&quot;)&lt;/script&gt;');
});`,
          references: ["CWE-79", "OWASP A03:2021 XSS"],
          qualityScore: 0,
          qualityAxes: { correctness: 0, safety: 0, testability: 0, invasiveness: 0 },
          generatedAt: now,
        };

      case "parameterization":
        return {
          id,
          findingId: finding.id,
          strategy,
          title: "パラメータ化クエリの使用",
          description: "SQLクエリへのユーザー入力を直接文字列結合するのではなく、プリペアドステートメントを使用する。",
          codeExample: `// Before (vulnerable - SQL Injection)
const query = \`SELECT * FROM users WHERE id = '\${userId}'\`;

// After (safe - Parameterized)
const query = "SELECT * FROM users WHERE id = $1";
const result = await db.query(query, [userId]);

// ORMを使う場合 (Prisma例)
const user = await prisma.user.findUnique({
  where: { id: userId } // 自動的にサニタイズ
});`,
          testSuggestion: `it("should prevent SQL injection", async () => {
  const maliciousId = "' OR '1'='1";
  const result = await getUser(maliciousId);
  expect(result).toBeNull(); // 正当なIDでないので結果なし
});`,
          references: ["CWE-89", "OWASP A03:2021 SQLi", "https://cheatsheetseries.owasp.org/cheatsheets/SQL_Injection_Prevention_Cheat_Sheet.html"],
          qualityScore: 0,
          qualityAxes: { correctness: 0, safety: 0, testability: 0, invasiveness: 0 },
          generatedAt: now,
        };

      case "crypto-upgrade":
        return {
          id,
          findingId: finding.id,
          strategy,
          title: "安全な暗号化アルゴリズムへの移行",
          description: "MD5/SHA-1やMath.random()など脆弱な暗号プリミティブをセキュアな代替に置き換える。",
          codeExample: `// Before (vulnerable - weak hash)
import { createHash } from "crypto";
const hash = createHash("md5").update(data).digest("hex");

// After (safe - SHA-256)
const hash = createHash("sha256").update(data).digest("hex");

// Before (vulnerable - weak random)
const token = Math.random().toString(36);

// After (safe - cryptographically secure)
import { randomBytes } from "crypto";
const token = randomBytes(32).toString("hex");`,
          testSuggestion: `it("should use cryptographically secure random", () => {
  const token1 = generateToken();
  const token2 = generateToken();
  expect(token1).not.toBe(token2); // ランダム性
  expect(token1).toHaveLength(64); // 32 bytes hex = 64 chars
});`,
          references: ["CWE-338", "CWE-327", "OWASP A02:2021 Cryptographic Failures"],
          qualityScore: 0,
          qualityAxes: { correctness: 0, safety: 0, testability: 0, invasiveness: 0 },
          generatedAt: now,
        };

      case "config-hardening":
        return {
          id,
          findingId: finding.id,
          strategy,
          title: "設定のハードニング",
          description: "ハードコードされたシークレットを環境変数に移行し、デバッグモードをproductionで無効化する。",
          codeExample: `// Before (vulnerable - hardcoded secret)
const apiKey = "sk-1234567890abcdef";
const dbUrl = "postgresql://admin:password@localhost/prod";

// After (safe - environment variables)
const apiKey = process.env.API_KEY;
if (!apiKey) throw new Error("API_KEY env var is required");

// .env.example (コミットOK)
// API_KEY=your-api-key-here

// .env.local (絶対コミット禁止、.gitignoreに追加)
// API_KEY=sk-actual-key

// CORS設定
// Before (too permissive)
headers["Access-Control-Allow-Origin"] = "*";

// After (allowlist)
const allowed = process.env.ALLOWED_ORIGINS?.split(",") ?? [];
const origin = req.headers.origin;
if (origin && allowed.includes(origin)) {
  headers["Access-Control-Allow-Origin"] = origin;
}`,
          testSuggestion: `it("should load API key from env", () => {
  process.env.API_KEY = "test-key";
  const config = loadConfig();
  expect(config.apiKey).toBe("test-key");
  delete process.env.API_KEY;
});`,
          references: ["CWE-798", "CWE-489", "CWE-942", "OWASP A05:2021 Security Misconfiguration"],
          qualityScore: 0,
          qualityAxes: { correctness: 0, safety: 0, testability: 0, invasiveness: 0 },
          generatedAt: now,
        };

      case "access-control":
        return {
          id,
          findingId: finding.id,
          strategy,
          title: "アクセス制御の強化",
          description: "認証・認可チェックをすべてのエンドポイントに適用し、最小権限原則に従う。",
          codeExample: `// Before (no auth check)
export async function GET(req: Request) {
  const data = await db.getSecretData();
  return Response.json(data);
}

// After (with auth)
import { getServerSession } from "next-auth";
import { authOptions } from "@/lib/auth";

export async function GET(req: Request) {
  const session = await getServerSession(authOptions);
  if (!session) {
    return new Response("Unauthorized", { status: 401 });
  }
  if (!session.user.roles.includes("admin")) {
    return new Response("Forbidden", { status: 403 });
  }
  const data = await db.getSecretData();
  return Response.json(data);
}`,
          testSuggestion: `it("should reject unauthenticated requests", async () => {
  const res = await handler(new Request("/api/secret"));
  expect(res.status).toBe(401);
});

it("should reject unauthorized users", async () => {
  mockSession({ roles: ["user"] }); // non-admin
  const res = await handler(new Request("/api/secret"));
  expect(res.status).toBe(403);
});`,
          references: ["OWASP A01:2021 Broken Access Control", "CWE-284"],
          qualityScore: 0,
          qualityAxes: { correctness: 0, safety: 0, testability: 0, invasiveness: 0 },
          generatedAt: now,
        };

      case "code-removal":
        return {
          id,
          findingId: finding.id,
          strategy,
          title: "危険なコードパターンの削除・置換",
          description: "eval()やFunction()コンストラクタなど、コードインジェクションリスクのある構文を安全な代替に置換する。",
          codeExample: `// Before (dangerous - allows code injection)
const result = eval(userExpression);

// After (safe - use a parser/sandbox)
// Option 1: 数値計算のみなら専用パーサを使用
import { Parser } from "expr-eval";
const parser = new Parser();
const result = parser.evaluate(sanitizedExpression);

// Option 2: 許可リストによる制限
const ALLOWED_OPERATIONS = { "add": (a: number, b: number) => a + b };
const result = ALLOWED_OPERATIONS[operation]?.(arg1, arg2);`,
          testSuggestion: `it("should not execute injected code", () => {
  let executed = false;
  const payload = "executed = true";
  evaluate(payload); // safe evaluator
  expect(executed).toBe(false); // コードは実行されていない
});`,
          references: ["CWE-95", "CWE-78", "OWASP A03:2021 Injection"],
          qualityScore: 0,
          qualityAxes: { correctness: 0, safety: 0, testability: 0, invasiveness: 0 },
          generatedAt: now,
        };

      case "dependency-update":
        return {
          id,
          findingId: finding.id,
          strategy,
          title: "依存パッケージの更新",
          description: "脆弱性を含む依存パッケージをpatched versionに更新する。",
          codeExample: `# 脆弱性のある依存を確認
npm audit

# 自動修正可能なものを修正
npm audit fix

# 手動でバージョン指定が必要な場合
npm install package-name@^X.Y.Z

# package.json でバージョンを固定
{
  "dependencies": {
    "vulnerable-package": ">=X.Y.Z"  // patched version以上を要求
  }
}`,
          testSuggestion: `# CI/CDでの継続的チェック
# .github/workflows/security.yml
- name: Run security audit
  run: npm audit --audit-level=high`,
          references: ["OWASP A06:2021 Vulnerable and Outdated Components"],
          qualityScore: 0,
          qualityAxes: { correctness: 0, safety: 0, testability: 0, invasiveness: 0 },
          generatedAt: now,
        };

      case "generic":
      default:
        return {
          id,
          findingId: finding.id,
          strategy: "generic",
          title: "セキュリティ強化の一般的な推奨事項",
          description: `「${finding.title}」に対する一般的なセキュリティ改善提案。`,
          codeExample: undefined,
          testSuggestion: `it("should handle edge cases securely", () => {
  // 境界値、不正入力、エラーケースのテストを追加してください
});`,
          references: ["OWASP Top 10", "https://cheatsheetseries.owasp.org/"],
          qualityScore: 0,
          qualityAxes: { correctness: 0, safety: 0, testability: 0, invasiveness: 0 },
          generatedAt: now,
        };
    }
  }

  // ============================================================
  // PRIVATE: パッチ候補の品質評価
  // ============================================================

  /**
   * パッチ候補の品質を4軸で評価し、qualityScoreを付与する
   */
  private evaluateCandidate(
    candidate: PatchCandidate,
    finding: VulnFinding,
  ): PatchCandidate {
    const axes = this.scoreAxes(candidate, finding);

    // 重み付き平均: correctness > safety > testability > invasiveness
    const qualityScore =
      axes.correctness * 0.40 +
      axes.safety * 0.30 +
      axes.testability * 0.20 +
      axes.invasiveness * 0.10;

    return { ...candidate, qualityScore: Math.round(qualityScore * 100) / 100, qualityAxes: axes };
  }

  /**
   * 4軸スコアリング
   */
  private scoreAxes(candidate: PatchCandidate, finding: VulnFinding): PatchQualityAxes {
    // correctness: CWEとstrategyの対応度
    const correctness = this.scoreCorrectness(candidate.strategy, finding);

    // safety: codeExampleに既知の危険パターンがないか
    const safety = this.scoreSafety(candidate);

    // testability: testSuggestionの品質
    const testability = candidate.testSuggestion ? 0.8 : 0.3;

    // invasiveness: generic以外は非侵襲的（スコア高）
    const invasiveness = candidate.strategy === "generic" ? 0.5 : 0.85;

    return { correctness, safety, testability, invasiveness };
  }

  private scoreCorrectness(strategy: PatchStrategy, finding: VulnFinding): number {
    const cwe = (finding.cwe ?? "").toLowerCase();
    const desc = (finding.description + " " + finding.title).toLowerCase();

    const STRATEGY_CWE_MAP: Record<PatchStrategy, string[]> = {
      "input-validation": ["cwe-20", "cwe-79", "cwe-78", "cwe-89", "cwe-1321"],
      "sanitization": ["cwe-79", "cwe-80"],
      "parameterization": ["cwe-89", "cwe-564"],
      "access-control": ["cwe-284", "cwe-285", "cwe-306"],
      "crypto-upgrade": ["cwe-327", "cwe-328", "cwe-338"],
      "dependency-update": ["cve", "cwe-1104"],
      "config-hardening": ["cwe-798", "cwe-259", "cwe-489", "cwe-942", "cwe-321"],
      "code-removal": ["cwe-95", "cwe-78", "cwe-77"],
      "generic": [],
    };

    const relatedCwes = STRATEGY_CWE_MAP[strategy] ?? [];
    const isMatch = relatedCwes.some((c) => cwe.includes(c) || desc.includes(c.replace("cwe-", "")));
    return isMatch ? 0.90 : 0.55;
  }

  private scoreSafety(candidate: PatchCandidate): number {
    const code = (candidate.codeExample ?? "").toLowerCase();

    // 危険パターンチェック（パッチ自体に問題がないか）
    const dangerPatterns = [
      /eval\s*\(/,
      /\bexec\s*\(/,
      /dangerouslysetinnerhtml/i,
      /math\.random\(\)/,
      /createhash\("md5"\)/i,
    ];

    // "After (safe)" セクション以降のコードのみチェック
    const afterMatch = code.match(/after\s*\(safe\)[^]*$/i);
    const codeToCheck = afterMatch ? afterMatch[0] : code;

    const hasDanger = dangerPatterns.some((p) => p.test(codeToCheck));
    return hasDanger ? 0.40 : 0.90;
  }

  // ============================================================
  // PRIVATE: PRレコード生成
  // ============================================================

  private buildPrRecord(
    finding: VulnFinding,
    patch: PatchCandidate,
    severity: VulnSeverity,
  ): RemediationResult["prRecord"] {
    const severityPrefix: Record<VulnSeverity, string> = {
      Critical: "fix!",
      High: "fix",
      Medium: "fix",
      Low: "refactor",
    };

    const prTitle = `${severityPrefix[severity]}(security): ${patch.title} — ${finding.title}`;
    const branchName = `blue/remediate-${finding.id.slice(0, 8)}`;

    const prBody = `## 🔵 BLUE Agent Remediation — Issue #${finding.id}

### 対象脆弱性
- **タイトル**: ${finding.title}
- **重大度**: ${severity}
${finding.cve ? `- **CVE**: ${finding.cve}` : ""}
- **発見日時**: ${finding.discoveredAt}

### 修正戦略
**${patch.strategy}**: ${patch.description}

${patch.codeExample ? `### 修正コード例\n\`\`\`typescript\n${patch.codeExample}\n\`\`\`` : ""}

${patch.testSuggestion ? `### テストケース提案\n\`\`\`typescript\n${patch.testSuggestion}\n\`\`\`` : ""}

### パッチ品質評価 (TrustScorer)
| 軸 | スコア |
|---|---|
| Correctness | ${(patch.qualityAxes.correctness * 100).toFixed(0)}% |
| Safety | ${(patch.qualityAxes.safety * 100).toFixed(0)}% |
| Testability | ${(patch.qualityAxes.testability * 100).toFixed(0)}% |
| Invasiveness | ${(patch.qualityAxes.invasiveness * 100).toFixed(0)}% |
| **総合スコア** | **${(patch.qualityScore * 100).toFixed(0)}%** |

### 参照
${patch.references.map((r) => `- ${r}`).join("\n")}

---
🤖 Generated by BLUE Agent (Katala Remediation Engine)
Patch ID: \`${patch.id}\``;

    return {
      patchId: patch.id,
      targetRepo: finding.targetRepo,
      branchName,
      prTitle,
      prBody,
      submittedAt: new Date().toISOString(),
      status: "draft",
    };
  }

  // ============================================================
  // PRIVATE: イベントログ
  // ============================================================

  private logEvent(event: RemediationEvent): void {
    this.eventLog.push(event);
  }
}
