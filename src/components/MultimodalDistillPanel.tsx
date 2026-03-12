"use client";

import { useState } from "react";
import type { SceneDistillation } from "@/lib/multimodal/sceneChannels";

const SAMPLE_TEXT = "薄暗い部屋で、窓際に立つ人物。手前に机、その上に白いカップ。";

export default function MultimodalDistillPanel() {
  const [text, setText] = useState(SAMPLE_TEXT);
  const [result, setResult] = useState<SceneDistillation | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const runDistill = async () => {
    setLoading(true);
    setError(null);

    try {
      const response = await fetch("/api/multimodal/distill", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text }),
      });

      const data = await response.json();
      if (!response.ok) {
        throw new Error(data.error ?? "Distillation failed");
      }

      setResult(data.result satisfies SceneDistillation);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unknown error");
    } finally {
      setLoading(false);
    }
  };

  return (
    <section className="mb-12 w-full max-w-5xl">
      <div className="rounded-3xl bg-white px-5 py-4 shadow-sm backdrop-blur-sm dark:bg-zinc-900/50">
        <h2 className="mb-3 text-xl font-semibold">Multimodal Distill Lab</h2>
        <p className="mb-4 text-sm opacity-70">
          全文 + 9チャンネル + 非重複統合説明の10本構成に加えて、link と renderer input までその場で試すパネル。
        </p>

        <div className="space-y-4">
          <textarea
            value={text}
            onChange={(event) => setText(event.target.value)}
            className="min-h-32 w-full rounded-2xl border border-zinc-300 bg-transparent px-4 py-3 text-sm outline-none ring-0 transition focus:border-blue-500 dark:border-zinc-700"
            placeholder="解析したい文章を入力"
          />

          <div className="flex flex-wrap gap-3">
            <button
              type="button"
              onClick={runDistill}
              disabled={loading || text.trim().length === 0}
              className="rounded-full bg-blue-500/10 px-4 py-2 text-sm text-blue-600 transition hover:bg-blue-500/20 disabled:cursor-not-allowed disabled:opacity-50 dark:text-blue-400"
            >
              {loading ? "解析中..." : "10本に蒸留する"}
            </button>
            <button
              type="button"
              onClick={() => {
                setText(SAMPLE_TEXT);
                setError(null);
              }}
              className="rounded-full bg-zinc-500/10 px-4 py-2 text-sm transition hover:bg-zinc-500/20"
            >
              サンプル入力に戻す
            </button>
          </div>

          {error ? <p className="text-sm text-red-500">{error}</p> : null}

          {result ? (
            <div className="space-y-4">
              <div className="rounded-2xl border border-zinc-200/70 px-4 py-3 text-sm dark:border-zinc-800">
                <div className="mb-2 font-semibold">normalized</div>
                <div className="opacity-80">{result.input.normalizedText}</div>
              </div>

              <div className="grid gap-4 md:grid-cols-2">
                {result.channels.map((channel) => (
                  <div
                    key={channel.key}
                    className="rounded-2xl border border-zinc-200/70 px-4 py-3 dark:border-zinc-800"
                  >
                    <div className="mb-2 flex items-center justify-between gap-3">
                      <div>
                        <div className="font-semibold">
                          {channel.key} / {channel.label}
                        </div>
                        <div className="text-xs opacity-60">{channel.description}</div>
                      </div>
                      <span className="rounded-full bg-zinc-500/10 px-2 py-1 text-[10px] uppercase tracking-wide opacity-70">
                        {channel.allowDuplicates ? "dup ok" : "dedup"}
                      </span>
                    </div>

                    <ul className="space-y-2 text-sm">
                      {channel.items.map((entry) => (
                        <li key={entry.id} className="rounded-xl bg-zinc-500/5 px-3 py-2">
                          <div>{entry.text}</div>
                          <div className="mt-1 text-[11px] opacity-60">
                            conf {entry.confidence.toFixed(2)} / source: {entry.source.join(", ")}
                          </div>
                        </li>
                      ))}
                    </ul>
                  </div>
                ))}
              </div>

              <div className="grid gap-4 md:grid-cols-2">
                <div className="rounded-2xl border border-zinc-200/70 px-4 py-3 dark:border-zinc-800">
                  <div className="mb-2 font-semibold">nodes</div>
                  <ul className="space-y-2 text-sm">
                    {result.nodes.map((node) => (
                      <li key={node.nodeId} className="rounded-xl bg-zinc-500/5 px-3 py-2">
                        <div className="font-medium">{node.label}</div>
                        <div className="text-xs opacity-70">{node.nodeId} / {node.type}</div>
                        <div className="mt-1 text-[11px] opacity-60">tags: {node.tags.join(", ") || "-"}</div>
                      </li>
                    ))}
                  </ul>
                </div>

                <div className="rounded-2xl border border-zinc-200/70 px-4 py-3 dark:border-zinc-800">
                  <div className="mb-2 font-semibold">edges</div>
                  <ul className="space-y-2 text-sm">
                    {result.edges.map((edge) => (
                      <li key={edge.edgeId} className="rounded-xl bg-zinc-500/5 px-3 py-2">
                        <div>{edge.fromNodeId} → {edge.toNodeId}</div>
                        <div className="text-xs opacity-70">{edge.relation} / weight {edge.weight.toFixed(2)}</div>
                        <div className="mt-1 text-[11px] opacity-60">{edge.note}</div>
                      </li>
                    ))}
                  </ul>
                </div>
              </div>

              <div className="grid gap-4 md:grid-cols-2">
                <div className="rounded-2xl border border-zinc-200/70 px-4 py-3 dark:border-zinc-800">
                  <div className="mb-2 font-semibold">links</div>
                  <ul className="space-y-2 text-sm">
                    {result.links.map((link, index) => (
                      <li key={`${link.fromItemId}-${link.toItemId}-${index}`} className="rounded-xl bg-zinc-500/5 px-3 py-2">
                        <div>
                          {link.fromChannel}:{link.fromItemId} → {link.toChannel}:{link.toItemId}
                        </div>
                        <div className="text-xs opacity-70">
                          {link.relation} / strength {link.strength.toFixed(2)}
                        </div>
                        <div className="mt-1 text-[11px] opacity-60">{link.note}</div>
                      </li>
                    ))}
                  </ul>
                </div>

                <div className="rounded-2xl border border-zinc-200/70 px-4 py-3 dark:border-zinc-800">
                  <div className="mb-2 font-semibold">derived maps</div>
                  <ul className="space-y-2 text-sm max-h-96 overflow-auto">
                    {result.derivedMaps.map((map) => (
                      <li key={map.mapId} className="rounded-xl bg-zinc-500/5 px-3 py-2">
                        <div className="font-medium">{map.kind}</div>
                        <div className="text-xs opacity-70">{map.mapId}</div>
                        <div className="mt-1 text-[11px] opacity-60">channels: {map.sourceChannels.join(", ")}</div>
                        <div className="text-[11px] opacity-60">tags: {map.tags.join(", ")}</div>
                      </li>
                    ))}
                  </ul>
                </div>
              </div>

              <div className="rounded-2xl border border-zinc-200/70 px-4 py-3 dark:border-zinc-800">
                <div className="mb-2 font-semibold">renderer inputs</div>
                <ul className="space-y-3 text-sm">
                  {result.renderers.map((renderer) => (
                    <li key={renderer.target} className="rounded-xl bg-zinc-500/5 px-3 py-2">
                      <div className="font-medium">{renderer.target}</div>
                      <div className="mt-1 opacity-80">{renderer.prompt}</div>
                      <div className="mt-2 text-[11px] opacity-60">conditions: {renderer.conditions.join(", ")}</div>
                      <div className="text-[11px] opacity-60">emphasis: {renderer.emphasis.join(", ")}</div>
                      <div className="text-[11px] opacity-60">graph refs: nodes {renderer.graphRefs.nodeIds.length}, edges {renderer.graphRefs.edgeIds.length}, maps {renderer.graphRefs.mapIds.length}</div>
                    </li>
                  ))}
                </ul>
              </div>
            </div>
          ) : null}
        </div>
      </div>
    </section>
  );
}
