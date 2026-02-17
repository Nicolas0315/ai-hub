import Papa from "papaparse";
import { z } from "zod";
import { IdentityVectorSchema, type IdentityVector } from "./IdentityVector";

/** CSVの1行に対応するスキーマ（フラット構造→IdentityVector変換用） */
export const CsvRowSchema = z.object({
  extraversion: z.coerce.number().min(0).max(1),
  intuition: z.coerce.number().min(0).max(1),
  thinking: z.coerce.number().min(0).max(1),
  judging: z.coerce.number().min(0).max(1),
  values: z.string().transform((s) => s.split("|").filter(Boolean)),
  professionalFocus: z.string().transform((s) => s.split("|").filter(Boolean)),
  battery: z.coerce.number().min(0).max(100),
  preferredTone: z.enum(["concise", "enthusiastic", "professional", "casual"]),
  confidenceScore: z.coerce.number().min(0).max(1),
  lastUpdated: z.string().datetime(),
});

export type CsvRow = z.input<typeof CsvRowSchema>;

/** インポート結果 */
export interface ImportResult {
  /** 正常にインポートされたベクトル */
  success: IdentityVector[];
  /** エラー情報（行番号とメッセージ） */
  errors: { row: number; message: string }[];
  /** 処理した総行数 */
  totalRows: number;
}

/** バッチオプション */
export interface ImportOptions {
  /** チャンクサイズ（デフォルト: 100） */
  batchSize?: number;
  /** バッチ処理コールバック */
  onBatch?: (batch: IdentityVector[], batchIndex: number) => void | Promise<void>;
}

/** フラットCSV行をIdentityVectorに変換 */
function rowToVector(row: z.infer<typeof CsvRowSchema>): IdentityVector {
  return {
    personality: {
      extraversion: row.extraversion,
      intuition: row.intuition,
      thinking: row.thinking,
      judging: row.judging,
    },
    values: row.values,
    professionalFocus: row.professionalFocus,
    socialEnergy: {
      battery: row.battery,
      preferredTone: row.preferredTone,
    },
    meta: {
      confidenceScore: row.confidenceScore,
      lastUpdated: row.lastUpdated,
    },
  };
}

/**
 * CSV文字列からIdentityVectorをインポートする
 * 不正な行はスキップしてエラーレポートに記録する
 */
export async function importCsv(
  csvContent: string,
  options: ImportOptions = {},
): Promise<ImportResult> {
  const { batchSize = 100, onBatch } = options;

  const parsed = Papa.parse<Record<string, string>>(csvContent, {
    header: true,
    skipEmptyLines: true,
    transformHeader: (h) => h.trim(),
  });

  const result: ImportResult = { success: [], errors: [], totalRows: parsed.data.length };
  let batch: IdentityVector[] = [];
  let batchIndex = 0;

  for (let i = 0; i < parsed.data.length; i++) {
    const raw = parsed.data[i];
    const rowNum = i + 2; // ヘッダー行 + 0-indexed → 実際の行番号

    const validation = CsvRowSchema.safeParse(raw);
    if (!validation.success) {
      const msg = validation.error.issues.map((e) => `${e.path.join(".")}: ${e.message}`).join("; ");
      result.errors.push({ row: rowNum, message: `バリデーションエラー: ${msg}` });
      continue;
    }

    const vector = rowToVector(validation.data);

    // IdentityVectorSchemaでも最終検証
    const finalCheck = IdentityVectorSchema.safeParse(vector);
    if (!finalCheck.success) {
      result.errors.push({ row: rowNum, message: "IdentityVector変換エラー" });
      continue;
    }

    result.success.push(finalCheck.data);
    batch.push(finalCheck.data);

    if (batch.length >= batchSize) {
      await onBatch?.(batch, batchIndex++);
      batch = [];
    }
  }

  // 残りのバッチを処理
  if (batch.length > 0) {
    await onBatch?.(batch, batchIndex);
  }

  return result;
}
