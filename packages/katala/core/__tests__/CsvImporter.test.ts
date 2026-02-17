import { describe, it, expect, vi } from "vitest";
import { importCsv, type ImportResult } from "../CsvImporter";

const HEADER = "extraversion,intuition,thinking,judging,values,professionalFocus,battery,preferredTone,confidenceScore,lastUpdated";

function makeRow(overrides: Record<string, string> = {}): string {
  const defaults: Record<string, string> = {
    extraversion: "0.8",
    intuition: "0.6",
    thinking: "0.7",
    judging: "0.4",
    values: "honesty|growth",
    professionalFocus: "engineering|design",
    battery: "75",
    preferredTone: "enthusiastic",
    confidenceScore: "0.9",
    lastUpdated: "2026-01-15T00:00:00.000Z",
  };
  const merged = { ...defaults, ...overrides };
  return [
    merged.extraversion, merged.intuition, merged.thinking, merged.judging,
    merged.values, merged.professionalFocus, merged.battery,
    merged.preferredTone, merged.confidenceScore, merged.lastUpdated,
  ].join(",");
}

describe("CsvImporter", () => {
  it("正常なCSVをインポートできる", async () => {
    const csv = `${HEADER}\n${makeRow()}\n${makeRow({ extraversion: "0.3" })}`;
    const result = await importCsv(csv);

    expect(result.success).toHaveLength(2);
    expect(result.errors).toHaveLength(0);
    expect(result.totalRows).toBe(2);
    expect(result.success[0].personality.extraversion).toBe(0.8);
    expect(result.success[1].personality.extraversion).toBe(0.3);
  });

  it("不正データをスキップしてエラーレポートする", async () => {
    const csv = `${HEADER}\n${makeRow()}\n${makeRow({ extraversion: "999" })}\n${makeRow({ preferredTone: "invalid" })}`;
    const result = await importCsv(csv);

    expect(result.success).toHaveLength(1);
    expect(result.errors).toHaveLength(2);
    expect(result.errors[0].row).toBe(3);
    expect(result.errors[0].message).toContain("バリデーションエラー");
    expect(result.errors[1].row).toBe(4);
  });

  it("空のCSVを処理できる", async () => {
    const csv = HEADER;
    const result = await importCsv(csv);

    expect(result.success).toHaveLength(0);
    expect(result.errors).toHaveLength(0);
    expect(result.totalRows).toBe(0);
  });

  it("パイプ区切りのvaluesを正しくパースする", async () => {
    const csv = `${HEADER}\n${makeRow({ values: "a|b|c", professionalFocus: "x" })}`;
    const result = await importCsv(csv);

    expect(result.success[0].values).toEqual(["a", "b", "c"]);
    expect(result.success[0].professionalFocus).toEqual(["x"]);
  });

  it("大量データをバッチ処理できる", async () => {
    const rows = Array.from({ length: 250 }, () => makeRow());
    const csv = `${HEADER}\n${rows.join("\n")}`;
    const batches: number[] = [];
    const onBatch = vi.fn((_batch, idx) => { batches.push(idx); });

    const result = await importCsv(csv, { batchSize: 100, onBatch });

    expect(result.success).toHaveLength(250);
    expect(onBatch).toHaveBeenCalledTimes(3); // 100 + 100 + 50
    expect(batches).toEqual([0, 1, 2]);
  });

  it("空行をスキップする", async () => {
    const csv = `${HEADER}\n${makeRow()}\n\n\n${makeRow()}`;
    const result = await importCsv(csv);

    expect(result.success).toHaveLength(2);
    expect(result.errors).toHaveLength(0);
  });

  it("ヘッダーの前後空白をトリムする", async () => {
    const csv = ` extraversion , intuition , thinking , judging , values , professionalFocus , battery , preferredTone , confidenceScore , lastUpdated \n${makeRow()}`;
    const result = await importCsv(csv);

    expect(result.success).toHaveLength(1);
  });

  it("境界値（0.0, 1.0）を受け入れる", async () => {
    const csv = `${HEADER}\n${makeRow({ extraversion: "0", intuition: "1", confidenceScore: "0" })}`;
    const result = await importCsv(csv);

    expect(result.success).toHaveLength(1);
    expect(result.success[0].personality.extraversion).toBe(0);
    expect(result.success[0].personality.intuition).toBe(1);
  });

  it("Shift-JIS相当のUTF-8テキストを処理できる", async () => {
    // papaparseはUTF-8文字列を受け取るため、事前にデコード済みを想定
    const csv = `${HEADER}\n${makeRow({ values: "誠実|成長" })}`;
    const result = await importCsv(csv);

    expect(result.success).toHaveLength(1);
    expect(result.success[0].values).toEqual(["誠実", "成長"]);
  });
});
