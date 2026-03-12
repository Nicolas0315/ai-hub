import { describe, expect, it } from "vitest";
import { CHANNEL_ORDER, DERIVED_MAP_KINDS, RENDERER_TARGETS, distillSceneText } from "./sceneChannels";

describe("distillSceneText", () => {
  it("returns the full three-layer deluxe structure", () => {
    const input = "薄暗い部屋で、窓際に立つ人物。手前に机、その上に白いカップ。";
    const result = distillSceneText(input);

    expect(result.schemaVersion).toBe("0.3");
    expect(result.channels.map((channel) => channel.key)).toEqual(CHANNEL_ORDER);
    expect(result.nodes.length).toBeGreaterThan(0);
    expect(result.edges.length).toBeGreaterThan(0);
    expect(result.derivedMaps.length).toBe(DERIVED_MAP_KINDS.length);
    expect(result.renderers.map((renderer) => renderer.target)).toEqual(RENDERER_TARGETS);
  });

  it("creates blur-capable temporal linkage", () => {
    const input = "高速で点滅する光が突然走る。";
    const result = distillSceneText(input);

    expect(result.links.some((link) => link.relation === "modulates_blur")).toBe(true);
  });

  it("attaches nodeRefs and mapRefs to channel items", () => {
    const input = "ガラスの机の上に白いカップがある。";
    const result = distillSceneText(input);
    const obj = result.channels.find((channel) => channel.key === "obj");

    expect(obj).toBeDefined();
    expect(obj?.items.some((item) => item.nodeRefs.length > 0)).toBe(true);
    expect(obj?.items.some((item) => item.mapRefs.length > 0)).toBe(true);
  });

  it("keeps merged explanation distinct from near-duplicate source text", () => {
    const input = "静かな部屋。静かな部屋で白い光がある。";
    const result = distillSceneText(input);
    const merged = result.channels.find((channel) => channel.key === "merged");

    expect(merged?.items[0]?.text).not.toContain("静かな部屋。");
  });
});
