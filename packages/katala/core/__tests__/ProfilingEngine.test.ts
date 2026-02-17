import { describe, it, expect } from "vitest";
import { ProfilingEngine, ChatMessage } from "../ProfilingEngine";
import { MockLLMAdapter, PartialIdentityVector } from "../llm-adapter";
import { createDefaultVector } from "../IdentityVector";

function makeHistory(count: number): ChatMessage[] {
  return Array.from({ length: count }, (_, i) => ({
    role: i % 2 === 0 ? ("user" as const) : ("assistant" as const),
    content: `Message ${i}`,
    timestamp: new Date(Date.now() - (count - i) * 60000).toISOString(),
  }));
}

describe("ProfilingEngine", () => {
  it("should use injected LLMAdapter for analysis", async () => {
    const mock = new MockLLMAdapter();
    const engine = new ProfilingEngine(mock);
    const history = makeHistory(5);

    await engine.updateProfile(createDefaultVector(), history);

    expect(mock.callCount).toBe(1);
    expect(mock.lastMessages).toEqual(history);
  });

  it("should merge LLM analysis into the identity vector", async () => {
    const mock = new MockLLMAdapter({
      personality: { extraversion: 0.9 },
      values: ["innovation"],
      professionalFocus: ["Rust"],
      socialEnergy: { preferredTone: "enthusiastic" },
    });
    const engine = new ProfilingEngine(mock);
    const base = createDefaultVector();

    const result = await engine.updateProfile(base, makeHistory(3));

    expect(result.personality.extraversion).toBe(0.9);
    expect(result.personality.intuition).toBe(0.5); // unchanged default
    expect(result.values).toContain("innovation");
    expect(result.professionalFocus).toContain("Rust");
    expect(result.socialEnergy.preferredTone).toBe("enthusiastic");
  });

  it("should accumulate values without duplicates", async () => {
    const mock = new MockLLMAdapter({ values: ["transparency", "honesty"] });
    const engine = new ProfilingEngine(mock);
    const base = { ...createDefaultVector(), values: ["transparency"] };

    const result = await engine.updateProfile(base, makeHistory(2));

    expect(result.values).toEqual(["transparency", "honesty"]);
  });

  it("should calculate confidence based on history length", async () => {
    const engine = new ProfilingEngine(new MockLLMAdapter());

    const short = await engine.updateProfile(createDefaultVector(), makeHistory(5));
    expect(short.meta.confidenceScore).toBe(5 / 50);

    const long = await engine.updateProfile(createDefaultVector(), makeHistory(100));
    expect(long.meta.confidenceScore).toBe(0.9); // capped
  });

  it("should handle empty analysis gracefully", async () => {
    const mock = new MockLLMAdapter({});
    const engine = new ProfilingEngine(mock);
    const base = createDefaultVector();

    const result = await engine.updateProfile(base, makeHistory(2));

    // Should keep defaults when LLM returns nothing
    expect(result.personality).toEqual(base.personality);
    expect(result.values).toEqual([]);
    expect(result.professionalFocus).toEqual([]);
  });

  it("should work with default MockLLMAdapter when no adapter provided", async () => {
    const engine = new ProfilingEngine();
    const result = await engine.updateProfile(createDefaultVector(), makeHistory(3));

    expect(result.personality.extraversion).toBe(0.7);
    expect(result.values).toContain("transparency");
  });

  describe("tuneProfile", () => {
    it("should increase extraversion for 'outgoing' instruction", async () => {
      const engine = new ProfilingEngine(new MockLLMAdapter());
      const base = createDefaultVector();

      const result = await engine.tuneProfile(base, "I want to be more outgoing");

      expect(result.personality.extraversion).toBe(0.7);
      expect(result.meta.confidenceScore).toBe(0.1);
    });

    it("should not change extraversion for unrelated instruction", async () => {
      const engine = new ProfilingEngine(new MockLLMAdapter());
      const base = createDefaultVector();

      const result = await engine.tuneProfile(base, "focus on technical topics");

      expect(result.personality.extraversion).toBe(0.5);
    });
  });
});

describe("MockLLMAdapter", () => {
  it("should track call count and messages", async () => {
    const mock = new MockLLMAdapter();
    const msgs = makeHistory(3);

    await mock.analyze(msgs);
    await mock.analyze(msgs);

    expect(mock.callCount).toBe(2);
    expect(mock.lastMessages).toEqual(msgs);
  });

  it("should return custom result when provided", async () => {
    const custom: PartialIdentityVector = {
      personality: { judging: 0.3 },
      values: ["freedom"],
    };
    const mock = new MockLLMAdapter(custom);

    const result = await mock.analyze([]);

    expect(result).toEqual(custom);
  });
});
