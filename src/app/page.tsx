"use client";

import { useEffect, useState } from "react";

interface AgentActivity {
  id: string;
  target: string;
  action: string;
  synergy: number;
  timestamp: string;
}

export default function Home() {
  const [activities, setActivities] = useState<AgentActivity[]>([]);

  useEffect(() => {
    setActivities([
      { id: "1", target: "投資家A", action: "条件交渉中", synergy: 0.92, timestamp: "現在" },
      { id: "2", target: "開発パートナー", action: "ビジョン照合中", synergy: 0.78, timestamp: "2分前" },
      { id: "3", target: "アルファグループ", action: "動向スキャン中", synergy: 0.85, timestamp: "15分前" },
    ]);
  }, []);

  return (
    <main className="min-h-screen max-w-lg mx-auto px-6 py-12">
      <header className="mb-12">
        <h1 className="text-4xl font-bold tracking-tight mb-2">Katala</h1>
        <p className="text-secondary text-lg text-[#86868b]">AI間通信・仲介パイプライン</p>
      </header>

      <section className="apple-glass rounded-3xl p-8 mb-8 aspect-square flex items-center justify-center relative overflow-hidden bg-white/70 dark:bg-zinc-900/70 backdrop-blur-2xl border border-white/20">
        <div className="absolute inset-0 bg-gradient-to-br from-blue-500/10 to-purple-500/10" />
        <div className="text-center z-10">
          <div className="w-24 h-24 bg-blue-500 rounded-full mx-auto mb-4 blur-xl opacity-50 animate-pulse" />
          <p className="font-semibold text-xl">しろくまエージェント</p>
          <p className="text-sm text-secondary text-[#86868b]">コネクションを同期中...</p>
        </div>
      </section>

      <section>
        <h2 className="text-xl font-semibold mb-4 px-2">ライブ仲介ログ</h2>
        <div className="space-y-4">
          {activities.map((activity) => (
            <div key={activity.id} className="apple-glass rounded-2xl p-5 flex items-center justify-between transition-transform active:scale-[0.98] bg-white/70 dark:bg-zinc-900/70 backdrop-blur-2xl border border-white/20">
              <div>
                <p className="font-medium text-lg">{activity.target}</p>
                <p className="text-sm text-secondary text-[#86868b]">{activity.action}</p>
              </div>
              <div className="text-right">
                <p className="text-[#0071e3] font-bold text-lg">{(activity.synergy * 100).toFixed(0)}%</p>
                <p className="text-xs text-secondary text-[#86868b]">{activity.timestamp}</p>
              </div>
            </div>
          ))}
        </div>
      </section>

      <div className="fixed bottom-12 left-0 right-0 px-6 max-w-lg mx-auto">
        <button className="w-full py-4 text-lg font-medium rounded-full bg-[#0071e3] text-white shadow-2xl shadow-blue-500/20 active:scale-95 transition-transform">
          エージェント・ベクトルを調教
        </button>
      </div>
    </main>
  );
}
