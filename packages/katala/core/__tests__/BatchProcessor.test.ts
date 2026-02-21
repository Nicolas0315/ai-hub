import { describe, it, expect } from "vitest";
import { BatchProcessor, BatchItem, BatchProgress } from "../BatchProcessor";
import { createDefaultVector } from "../IdentityVector";
import { MockLLMAdapter } from "../llm-adapter";
import { ProfilingEngine, ChatMessage } from "../ProfilingEngine";

function makeBatchItem(id: string): BatchItem {
  return {
    id,
    currentVector: createDefaultVector(),
    history: [
      { role: "user", content: "Hello", timestamp: new Date().toISOString() },
    ] as ChatMessage[],
  };
}

describe("BatchProcessor", () => {
  it("processes a batch of items successfully", async () => {
    const adapter = new MockLLMAdapter();
    const engine = new ProfilingEngine(adapter);
    const processor = new BatchProcessor(engine);

    const items = [makeBatchItem("a"), makeBatchItem("b"), makeBatchItem("c")];
    const results = await processor.process(items);

    expect(results).toHaveLength(3);
    expect(results.every((r) => r.status === "success")).toBe(true);
    expect(adapter.callCount).toBe(3);
  });

  it("respects concurrency limit", async () => {
    let peak = 0;
    let running = 0;

    const adapter: MockLLMAdapter = new MockLLMAdapter();
    const originalAnalyze = adapter.analyze.bind(adapter);
    adapter.analyze = async (msgs: ChatMessage[]) => {
      running++;
      peak = Math.max(peak, running);
      await new Promise((r) => setTimeout(r, 50));
      const result = await originalAnalyze(msgs);
      running--;
      return result;
    };

    const engine = new ProfilingEngine(adapter);
    const processor = new BatchProcessor(engine);

    const items = Array.from({ length: 10 }, (_, i) => makeBatchItem(`item-${i}`));
    await processor.process(items, { concurrency: 2 });

    expect(peak).toBeLessThanOrEqual(2);
  });

  it("retries on failure and eventually succeeds", async () => {
    let calls = 0;
    const adapter = new MockLLMAdapter();
    const originalAnalyze = adapter.analyze.bind(adapter);
    adapter.analyze = async (msgs: ChatMessage[]) => {
      calls++;
      if (calls <= 2) throw new Error("LLM API temporary failure");
      return originalAnalyze(msgs);
    };

    const engine = new ProfilingEngine(adapter);
    const processor = new BatchProcessor(engine);

    const results = await processor.process([makeBatchItem("retry-test")], {
      maxRetries: 3,
    });

    expect(results).toHaveLength(1);
    expect(results[0].status).toBe("success");
    expect(results[0].retries).toBe(2);
  });

  it("reports error after max retries exhausted", async () => {
    const adapter = new MockLLMAdapter();
    adapter.analyze = async () => {
      throw new Error("Permanent failure");
    };

    const engine = new ProfilingEngine(adapter);
    const processor = new BatchProcessor(engine);

    const results = await processor.process([makeBatchItem("fail-test")], {
      maxRetries: 2,
    });

    expect(results).toHaveLength(1);
    expect(results[0].status).toBe("error");
    expect(results[0].error).toBe("Permanent failure");
    expect(results[0].retries).toBe(2);
  });

  it("reports progress via callback", async () => {
    const adapter = new MockLLMAdapter();
    const engine = new ProfilingEngine(adapter);
    const processor = new BatchProcessor(engine);

    const progressUpdates: BatchProgress[] = [];
    const items = [makeBatchItem("p1"), makeBatchItem("p2"), makeBatchItem("p3")];

    await processor.process(items, {
      onProgress: (p) => progressUpdates.push({ ...p }),
    });

    expect(progressUpdates).toHaveLength(3);
    expect(progressUpdates[2]).toEqual({ processed: 3, total: 3, errors: 0 });
  });

  it("outputs results as JSON", async () => {
    const adapter = new MockLLMAdapter();
    const engine = new ProfilingEngine(adapter);
    const processor = new BatchProcessor(engine);

    const results = await processor.process([makeBatchItem("json-test")]);
    const json = processor.toJSON(results);
    const parsed = JSON.parse(json);

    expect(Array.isArray(parsed)).toBe(true);
    expect(parsed[0].id).toBe("json-test");
  });
});
