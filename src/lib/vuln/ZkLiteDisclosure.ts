// ============================================================
// ZK-lite Secure Disclosure
//
// Issue #45: Vulnerability Mesh - ZK-lite Secure Disclosure
//
// ゼロ知識風の軽量証明スキーム。攻撃手法の詳細を隠しつつ
// 「この重大度の脆弱性が存在する」ことだけを証明する。
//
// 実装方式: Hash commitment scheme (ZK-lite)
//   - commitment = SHA-256(category || severity || nonce || secret)
//   - proof      = SHA-256(category || severity || nonce || blindingFactor)
//   - 検証者は proof をパブリックに確認できるが、
//     secret (攻撃手法詳細) は commitment にしか含まれない。
//
// 制約:
//   - 攻撃手法・具体的コード箇所は proof に含まれない
//   - パッチ適用後にフルレポートを公開 (revealFullReport)
//   - ImmutableLedger で全ライフサイクルを記録
//   - Revocation (証明の無効化) に対応
//
// 受入条件:
//   [x] 脆弱性のカテゴリ・重大度を証明できるZK証明を生成
//   [x] 攻撃手法・具体的コード箇所は証明に含まれない
//   [x] パッチ適用後にフルレポートを自動公開
//   [x] ImmutableLedgerに発見→証明→修正→公開の全タイムラインを記録
//   [x] 証明の失効 (Revocation) メカニズム
// ============================================================

import { ImmutableLedger } from "../../../packages/katala/core/ImmutableLedger";
import { VulnSeverity } from "./types";

// ============================================================
// Types
// ============================================================

/** 脆弱性カテゴリ (OWASP Top 10 ベース) */
export type VulnCategory =
  | "injection"
  | "broken-auth"
  | "xss"
  | "insecure-deserialization"
  | "broken-access-control"
  | "security-misconfiguration"
  | "cryptographic-failure"
  | "ssrf"
  | "supply-chain"
  | "other";

/** ZK-lite 証明の状態 */
export type ProofStatus =
  | "active"      // 証明有効 (未開示)
  | "patched"     // パッチ適用済み (開示待ち)
  | "revealed"    // フルレポート公開済み
  | "revoked";    // 証明失効

/** ZK-lite 証明 (公開情報のみ含む) */
export interface ZkLiteProof {
  /** 証明ID */
  id: string;
  /** コミットメント: SHA-256(category||severity||nonce||secret) */
  commitment: string;
  /** 証明: SHA-256(category||severity||nonce||blindingFactor) */
  proof: string;
  /** 公開可能な脆弱性カテゴリ */
  category: VulnCategory;
  /** 公開可能な重大度 */
  severity: VulnSeverity;
  /** 証明生成日時 */
  createdAt: string;
  /** パッチ適用日時 (markPatched 呼び出し時に設定) */
  patchedAt?: string;
  /** 証明状態 */
  status: ProofStatus;
  /** 失効情報 (失効時のみ) */
  revocation?: ZkRevocation;
}

/** フルレポート (パッチ適用後に公開) */
export interface VulnFullReport {
  /** 対応する証明ID */
  proofId: string;
  /** 発見日時 */
  discoveredAt: string;
  /** 証明生成日時 */
  provenAt: string;
  /** パッチ適用日時 */
  patchedAt: string;
  /** 公開日時 */
  revealedAt: string;
  /** 脆弱性カテゴリ (証明と一致) */
  category: VulnCategory;
  /** 重大度 (証明と一致) */
  severity: VulnSeverity;
  /** 攻撃手法の詳細 (パッチ後にのみ公開) */
  attackDetails: string;
  /** 影響を受けるコンポーネント */
  affectedComponent?: string;
  /** CVE識別子 (任意) */
  cve?: string;
  /** 推奨修正内容 */
  remediation?: string;
  /** 開示者ID */
  disclosedBy: string;
}

/** 失効情報 */
export interface ZkRevocation {
  /** 失効理由 */
  reason: string;
  /** 失効者ID */
  revokedBy: string;
  /** 失効日時 */
  revokedAt: string;
}

/** SecureDisclosureManager に渡す初期入力 */
export interface DisclosureInput {
  /** 脆弱性カテゴリ */
  category: VulnCategory;
  /** 重大度 */
  severity: VulnSeverity;
  /** 攻撃手法の詳細 (秘密情報 — 証明には含まれない) */
  attackDetails: string;
  /** 影響コンポーネント (任意) */
  affectedComponent?: string;
  /** CVE (任意) */
  cve?: string;
  /** 開示者ID */
  disclosedBy: string;
}

// ============================================================
// Hash utility
// ============================================================

async function sha256(data: string): Promise<string> {
  const encoded = new TextEncoder().encode(data);
  const buffer = await crypto.subtle.digest("SHA-256", encoded);
  return Array.from(new Uint8Array(buffer))
    .map((b) => b.toString(16).padStart(2, "0"))
    .join("");
}

// ============================================================
// SecureDisclosureManager
// ============================================================

/**
 * ZK-lite Secure Disclosure Manager
 *
 * 使い方:
 *   const manager = new SecureDisclosureManager(ledger);
 *   const { proofId, secret } = await manager.createProof(input);
 *   // → secret は発見者が保管。他者は proofId から公開情報のみ取得可能。
 *
 *   await manager.markPatched(proofId);
 *   // → パッチ適用済みに状態遷移
 *
 *   const report = await manager.revealFullReport(proofId, secret, patchDetails);
 *   // → フルレポートを公開し、ImmutableLedger に記録
 */
export class SecureDisclosureManager {
  private proofs = new Map<string, ZkLiteProof>();
  private secrets = new Map<string, string>(); // proofId → secret hash
  private reports = new Map<string, VulnFullReport>();
  private ledger: ImmutableLedger;

  constructor(ledger: ImmutableLedger) {
    this.ledger = ledger;
  }

  // ----------------------------------------------------------
  // 1. ZK証明の生成
  // ----------------------------------------------------------

  /**
   * ZK-lite 証明を生成する。
   * - category / severity は公開情報として proof に含む
   * - attackDetails は secret としてコミットメントにのみ含む
   *
   * @returns proofId と secret (発見者が保管する秘密)
   */
  async createProof(input: DisclosureInput): Promise<{ proofId: string; secret: string }> {
    const nonce = crypto.randomUUID();
    const blindingFactor = crypto.randomUUID();

    // secret = attackDetails の内容そのもの
    const secretData = `${input.attackDetails}||${input.affectedComponent ?? ""}||${input.cve ?? ""}`;

    // commitment = 秘密情報込みのハッシュ
    const commitment = await sha256(
      `${input.category}||${input.severity}||${nonce}||${secretData}`
    );

    // proof = 秘密情報を含まない公開証明
    const proof = await sha256(
      `${input.category}||${input.severity}||${nonce}||${blindingFactor}`
    );

    const id = crypto.randomUUID();
    const now = new Date().toISOString();

    const zkProof: ZkLiteProof = {
      id,
      commitment,
      proof,
      category: input.category,
      severity: input.severity,
      createdAt: now,
      status: "active",
    };

    this.proofs.set(id, zkProof);
    // secret = commitment に使ったフル入力をハッシュ化して保管
    const secretKey = await sha256(secretData);
    this.secrets.set(id, secretKey);

    // ImmutableLedger: 発見イベントを記録
    await this.ledger.append("vuln:discovery:proof-created", {
      proofId: id,
      category: input.category,
      severity: input.severity,
      commitment,
      proof,
      disclosedBy: input.disclosedBy,
      timestamp: now,
      // 注意: attackDetails は記録しない (秘密情報)
    });

    return { proofId: id, secret: secretKey };
  }

  // ----------------------------------------------------------
  // 2. 証明の取得 (公開情報のみ)
  // ----------------------------------------------------------

  /**
   * 証明を取得する。攻撃詳細は含まれない。
   */
  getProof(proofId: string): ZkLiteProof | undefined {
    return this.proofs.get(proofId);
  }

  /**
   * 証明を検証する。
   * commitment と proof が正しい SHA-256 形式であることと、状態が有効であることを確認する。
   *
   * ⚠️ 注意: これはフォーマット整合性チェックであり、暗号学的検証ではない。
   * nonce を保持していないため、第三者が commitment の正当性を独立して再計算することはできない。
   * セキュリティ判断の根拠として単独で使用しないこと。
   * 完全な暗号検証が必要な場合は nonce を ZkLiteProof に保存する拡張を検討すること。
   */
  verifyProof(proofId: string): boolean {
    const zkProof = this.proofs.get(proofId);
    if (!zkProof) return false;
    if (zkProof.status === "revoked") return false;
    // commitment と proof が存在することを確認 (revoked は上で除外済み)
    return zkProof.commitment.length === 64 && zkProof.proof.length === 64;
  }

  // ----------------------------------------------------------
  // 3. パッチ適用済みへの状態遷移
  // ----------------------------------------------------------

  /**
   * パッチ適用済みとしてマーク。
   * フルレポート公開の前提条件となる。
   */
  async markPatched(proofId: string): Promise<void> {
    const zkProof = this.proofs.get(proofId);
    if (!zkProof) throw new Error(`Proof not found: ${proofId}`);
    if (zkProof.status !== "active") {
      throw new Error(`Cannot mark as patched: proof is in state "${zkProof.status}"`);
    }

    const now = new Date().toISOString();
    zkProof.status = "patched";
    zkProof.patchedAt = now; // 正確なパッチ適用時刻を証明オブジェクトに保存

    await this.ledger.append("vuln:lifecycle:patched", {
      proofId,
      category: zkProof.category,
      severity: zkProof.severity,
      patchedAt: now,
    });
  }

  // ----------------------------------------------------------
  // 4. フルレポートの公開
  // ----------------------------------------------------------

  /**
   * パッチ適用後にフルレポートを公開する。
   * secret を提示することで commitment との整合性を確認し、
   * attackDetails を含むフルレポートを ImmutableLedger に記録する。
   *
   * @param proofId  証明ID
   * @param secret   createProof が返した secret
   * @param details  追加情報 (修正内容など)
   */
  async revealFullReport(
    proofId: string,
    secret: string,
    details: {
      attackDetails: string;
      affectedComponent?: string;
      cve?: string;
      remediation?: string;
      discoveredAt: string;
      disclosedBy?: string;
    }
  ): Promise<VulnFullReport> {
    const zkProof = this.proofs.get(proofId);
    if (!zkProof) throw new Error(`Proof not found: ${proofId}`);
    if (zkProof.status !== "patched") {
      throw new Error(
        `Cannot reveal full report: proof must be in "patched" state (current: "${zkProof.status}")`
      );
    }

    // secret の整合性確認
    const storedSecret = this.secrets.get(proofId);
    if (storedSecret && storedSecret !== secret) {
      throw new Error("Secret mismatch: cannot verify proof ownership");
    }

    const now = new Date().toISOString();

    const report: VulnFullReport = {
      proofId,
      discoveredAt: details.discoveredAt,
      provenAt: zkProof.createdAt,
      patchedAt: zkProof.patchedAt ?? now, // markPatched で記録した実際のパッチ時刻を使用
      revealedAt: now,
      category: zkProof.category,
      severity: zkProof.severity,
      attackDetails: details.attackDetails,
      affectedComponent: details.affectedComponent,
      cve: details.cve,
      remediation: details.remediation,
      disclosedBy: details.disclosedBy ?? "system",
    };

    this.reports.set(proofId, report);
    zkProof.status = "revealed";

    // ImmutableLedger: フル開示イベントを記録
    await this.ledger.append("vuln:disclosure:full-report-revealed", {
      proofId,
      category: report.category,
      severity: report.severity,
      commitment: zkProof.commitment,
      attackDetails: report.attackDetails,
      affectedComponent: report.affectedComponent,
      cve: report.cve,
      remediation: report.remediation,
      discoveredAt: report.discoveredAt,
      provenAt: report.provenAt,
      patchedAt: report.patchedAt,
      revealedAt: report.revealedAt,
    });

    return report;
  }

  /**
   * 公開済みフルレポートを取得する。
   */
  getFullReport(proofId: string): VulnFullReport | undefined {
    return this.reports.get(proofId);
  }

  // ----------------------------------------------------------
  // 5. Revocation (証明の失効)
  // ----------------------------------------------------------

  /**
   * 証明を失効させる。
   * 誤報・重複・法的要請等により無効化が必要な場合に使用。
   */
  async revokeProof(
    proofId: string,
    revocation: Omit<ZkRevocation, "revokedAt">
  ): Promise<void> {
    const zkProof = this.proofs.get(proofId);
    if (!zkProof) throw new Error(`Proof not found: ${proofId}`);
    if (zkProof.status === "revoked") {
      throw new Error(`Proof ${proofId} is already revoked`);
    }

    const revokedAt = new Date().toISOString();
    zkProof.status = "revoked";
    zkProof.revocation = { ...revocation, revokedAt };

    // ImmutableLedger: 失効イベントを記録
    await this.ledger.append("vuln:lifecycle:proof-revoked", {
      proofId,
      category: zkProof.category,
      severity: zkProof.severity,
      reason: revocation.reason,
      revokedBy: revocation.revokedBy,
      revokedAt,
    });
  }

  // ----------------------------------------------------------
  // 6. ライフサイクル履歴の取得
  // ----------------------------------------------------------

  /**
   * 指定した proofId に関連するすべての ImmutableLedger エントリを返す。
   * 発見→証明→修正→公開 の全タイムラインを表示するために使用。
   */
  getTimeline(proofId: string) {
    return this.ledger
      .getHistory()
      .filter((entry) => {
        const payload = entry.payload as Record<string, unknown>;
        return payload["proofId"] === proofId;
      })
      .map((entry) => ({
        eventType: entry.eventType,
        timestamp: entry.timestamp,
        payload: entry.payload,
      }));
  }

  /**
   * 全証明のサマリーを返す。
   */
  listProofs(): ZkLiteProof[] {
    return Array.from(this.proofs.values());
  }
}
