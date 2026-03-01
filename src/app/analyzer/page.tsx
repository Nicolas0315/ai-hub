"use client";

import { useState } from "react";

interface AnalysisGoal {
  goal: string;
  priority: "high" | "medium" | "low";
  rationale: string;
  estimated_impact: string;
  source: string;
}

interface AnalysisResult {
  purpose: string;
  architecture: string;
  frameworks: string[];
  patterns: string[];
  concepts: string[];
  confidence: number;
  coverage: number;
  goals: AnalysisGoal[];
  incomplete: string[];
  undocumented: string[];
}

const PRIORITY_CONFIG = {
  high: { icon: "🔴", label: "高", color: "border-red-500/30 bg-red-500/5" },
  medium: { icon: "🟡", label: "中", color: "border-yellow-500/30 bg-yellow-500/5" },
  low: { icon: "🟢", label: "低", color: "border-green-500/30 bg-green-500/5" },
};

// Music production phases from KS41b
const MUSIC_PHASES = [
  { name: "compose", topAxis: "R_struct", boost: 1.8, desc: "和声・構造設計" },
  { name: "arrange", topAxis: "R_cultural", boost: 1.8, desc: "編曲・ジャンル適合" },
  { name: "produce", topAxis: "R_qualia", boost: 1.8, desc: "音色・サウンドデザイン" },
  { name: "mix", topAxis: "R_qualia", boost: 1.8, desc: "バランス・空間配置" },
  { name: "master", topAxis: "R_temporal", boost: 1.8, desc: "最終仕上げ・ラウドネス" },
];

export default function AnalyzerPage() {
  const [code, setCode] = useState("");
  const [result, setResult] = useState<AnalysisResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [activeTab, setActiveTab] = useState<"analyze" | "phases">("analyze");

  const handleAnalyze = async () => {
    setLoading(true);
    try {
      const res = await fetch("/api/analyze", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ code }),
      });
      if (!res.ok) throw new Error("Analysis failed");
      const data = await res.json();
      setResult(data);
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  };

  return (
    <main className="flex min-h-screen flex-col items-center p-8 md:p-24 bg-gray-50 dark:bg-zinc-950">
      <div className="w-full max-w-5xl">
        {/* Header */}
        <div className="mb-8">
          <h1 className="text-3xl font-bold tracking-tight bg-clip-text text-transparent bg-gradient-to-r from-emerald-500 to-cyan-600">
            KCS-2a Analyzer
          </h1>
          <p className="text-sm text-gray-500 dark:text-gray-400 mt-2">
            Design Intent Reverse Inference — コードから設計意図を逆推論し、次のゴールを自動生成
          </p>
        </div>

        {/* Tab Switcher */}
        <div className="flex gap-2 mb-6">
          <button
            onClick={() => setActiveTab("analyze")}
            className={`px-4 py-2 rounded-full text-sm font-medium transition-all ${
              activeTab === "analyze"
                ? "bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border border-emerald-500/30"
                : "text-gray-500 hover:text-gray-700 dark:hover:text-gray-300"
            }`}
          >
            コード分析
          </button>
          <button
            onClick={() => setActiveTab("phases")}
            className={`px-4 py-2 rounded-full text-sm font-medium transition-all ${
              activeTab === "phases"
                ? "bg-purple-500/10 text-purple-600 dark:text-purple-400 border border-purple-500/30"
                : "text-gray-500 hover:text-gray-700 dark:hover:text-gray-300"
            }`}
          >
            音楽フェーズ (KS41b)
          </button>
        </div>

        {activeTab === "analyze" && (
          <>
            {/* Code Input */}
            <div className="rounded-2xl border border-gray-200 dark:border-neutral-800 bg-white dark:bg-zinc-900/50 p-6 mb-6">
              <textarea
                value={code}
                onChange={(e) => setCode(e.target.value)}
                placeholder="Pythonコードを貼り付けてください..."
                className="w-full h-64 bg-transparent font-mono text-sm resize-none outline-none text-gray-800 dark:text-gray-200 placeholder:text-gray-400"
              />
              <div className="flex justify-end mt-4">
                <button
                  onClick={handleAnalyze}
                  disabled={loading || !code.trim()}
                  className="px-6 py-2 rounded-full bg-gradient-to-r from-emerald-500 to-cyan-600 text-white font-medium text-sm hover:from-emerald-600 hover:to-cyan-700 transition-all disabled:opacity-40"
                >
                  {loading ? "分析中..." : "逆推論を実行"}
                </button>
              </div>
            </div>

            {/* Results */}
            {result && (
              <div className="space-y-6">
                {/* Overview */}
                <div className="rounded-2xl border border-gray-200 dark:border-neutral-800 bg-white dark:bg-zinc-900/50 p-6">
                  <h2 className="text-lg font-semibold mb-4">推論結果</h2>
                  <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                    <MetricCard label="信頼度" value={`${(result.confidence * 100).toFixed(0)}%`} />
                    <MetricCard label="カバレッジ" value={`${(result.coverage * 100).toFixed(0)}%`} />
                    <MetricCard label="フレームワーク" value={`${result.frameworks.length}`} />
                    <MetricCard label="ゴール数" value={`${result.goals.length}`} />
                  </div>
                </div>

                {/* Purpose & Architecture */}
                <div className="rounded-2xl border border-gray-200 dark:border-neutral-800 bg-white dark:bg-zinc-900/50 p-6">
                  <h3 className="text-sm font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wider mb-3">
                    設計意図
                  </h3>
                  <p className="text-gray-800 dark:text-gray-200 mb-4">{result.purpose}</p>
                  <div className="flex flex-wrap gap-2">
                    <Tag label={result.architecture} color="blue" />
                    {result.patterns.map((p) => (
                      <Tag key={p} label={p} color="purple" />
                    ))}
                  </div>
                </div>

                {/* Frameworks */}
                {result.frameworks.length > 0 && (
                  <div className="rounded-2xl border border-gray-200 dark:border-neutral-800 bg-white dark:bg-zinc-900/50 p-6">
                    <h3 className="text-sm font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wider mb-3">
                      検知フレームワーク
                    </h3>
                    <div className="flex flex-wrap gap-2">
                      {result.frameworks.map((fw) => (
                        <Tag key={fw} label={fw} color="emerald" />
                      ))}
                    </div>
                  </div>
                )}

                {/* Goals */}
                <div className="rounded-2xl border border-gray-200 dark:border-neutral-800 bg-white dark:bg-zinc-900/50 p-6">
                  <h3 className="text-sm font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wider mb-4">
                    自動生成ゴール
                  </h3>
                  <div className="space-y-3">
                    {result.goals.map((g, i) => {
                      const cfg = PRIORITY_CONFIG[g.priority];
                      return (
                        <div key={i} className={`rounded-xl border p-4 ${cfg.color}`}>
                          <div className="flex items-start gap-3">
                            <span className="text-lg">{cfg.icon}</span>
                            <div className="flex-1">
                              <p className="text-sm font-medium text-gray-800 dark:text-gray-200">
                                {g.goal}
                              </p>
                              <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
                                {g.estimated_impact} · {g.source}
                              </p>
                            </div>
                          </div>
                        </div>
                      );
                    })}
                  </div>
                </div>
              </div>
            )}
          </>
        )}

        {activeTab === "phases" && (
          <div className="rounded-2xl border border-gray-200 dark:border-neutral-800 bg-white dark:bg-zinc-900/50 p-6">
            <h2 className="text-lg font-semibold mb-2">音楽プロダクションフェーズ</h2>
            <p className="text-sm text-gray-500 dark:text-gray-400 mb-6">
              KS41b Goal Planning Engine — フェーズごとに翻訳損失軸の重要度が変わる
            </p>
            <div className="space-y-4">
              {MUSIC_PHASES.map((phase, i) => (
                <div
                  key={phase.name}
                  className="flex items-center gap-4 p-4 rounded-xl border border-purple-500/20 bg-purple-500/5"
                >
                  <div className="w-8 h-8 rounded-full bg-purple-500/20 flex items-center justify-center text-sm font-bold text-purple-600 dark:text-purple-400">
                    {i + 1}
                  </div>
                  <div className="flex-1">
                    <div className="flex items-baseline gap-2">
                      <span className="font-semibold text-gray-800 dark:text-gray-200 capitalize">
                        {phase.name}
                      </span>
                      <span className="text-xs text-gray-500">{phase.desc}</span>
                    </div>
                    <div className="flex items-center gap-2 mt-1">
                      <span className="text-xs font-mono text-purple-600 dark:text-purple-400">
                        {phase.topAxis}
                      </span>
                      <div className="flex-1 h-2 bg-gray-200 dark:bg-zinc-800 rounded-full overflow-hidden">
                        <div
                          className="h-full bg-gradient-to-r from-purple-500 to-pink-500 rounded-full"
                          style={{ width: `${(phase.boost / 2.0) * 100}%` }}
                        />
                      </div>
                      <span className="text-xs font-medium text-gray-600 dark:text-gray-400">
                        {phase.boost}x
                      </span>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </main>
  );
}

function MetricCard({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-xl bg-gray-50 dark:bg-zinc-800/50 p-4 text-center">
      <div className="text-2xl font-bold text-gray-800 dark:text-gray-200">{value}</div>
      <div className="text-xs text-gray-500 dark:text-gray-400 mt-1">{label}</div>
    </div>
  );
}

function Tag({ label, color }: { label: string; color: string }) {
  const colors: Record<string, string> = {
    blue: "bg-blue-500/10 text-blue-600 dark:text-blue-400 border-blue-500/20",
    purple: "bg-purple-500/10 text-purple-600 dark:text-purple-400 border-purple-500/20",
    emerald: "bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border-emerald-500/20",
  };
  return (
    <span className={`text-xs font-medium px-3 py-1 rounded-full border ${colors[color] || colors.blue}`}>
      {label}
    </span>
  );
}
