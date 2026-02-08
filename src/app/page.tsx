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
    // Initial dummy data to demonstrate the HIG feel
    setActivities([
      { id: "1", target: "Investor A", action: "Negotiating Terms", synergy: 0.92, timestamp: "Now" },
      { id: "2", target: "Dev Partner", action: "Matching Vision", synergy: 0.78, timestamp: "2m ago" },
      { id: "3", target: "Alpha Group", action: "Scanning Alpha", synergy: 0.85, timestamp: "15m ago" },
    ]);
  }, []);

  return (
    <main className="min-h-screen max-w-lg mx-auto px-6 py-12">
      {/* Header */}
      <header className="mb-12">
        <h1 className="text-4xl font-bold tracking-tight mb-2">ai-hub</h1>
        <p className="text-secondary text-lg">AI-to-AI Mediation Pipeline</p>
      </header>

      {/* Hero / Visualization Placeholder */}
      <section className="apple-glass rounded-3xl p-8 mb-8 aspect-square flex items-center justify-center relative overflow-hidden">
        <div className="absolute inset-0 bg-gradient-to-br from-blue-500/10 to-purple-500/10" />
        <div className="text-center z-10">
          <div className="w-24 h-24 bg-blue-500 rounded-full mx-auto mb-4 blur-xl opacity-50 animate-pulse" />
          <p className="font-semibold text-xl">Sirokuma Agent</p>
          <p className="text-sm text-secondary">Synchronizing Connections...</p>
        </div>
      </section>

      {/* Activity List */}
      <section>
        <h2 className="text-xl font-semibold mb-4 px-2">Live Mediation</h2>
        <div className="space-y-4">
          {activities.map((activity) => (
            <div key={activity.id} className="apple-glass rounded-2xl p-5 flex items-center justify-between transition-transform active:scale-[0.98]">
              <div>
                <p className="font-medium text-lg">{activity.target}</p>
                <p className="text-sm text-secondary">{activity.action}</p>
              </div>
              <div className="text-right">
                <p className="text-accent font-bold text-lg">{(activity.synergy * 100).toFixed(0)}%</p>
                <p className="text-xs text-secondary">{activity.timestamp}</p>
              </div>
            </div>
          ))}
        </div>
      </section>

      {/* Primary Action */}
      <div className="fixed bottom-12 left-0 right-0 px-6 max-w-lg mx-auto">
        <button className="apple-button w-full py-4 text-lg shadow-2xl shadow-blue-500/20">
          Tune Agent Vector
        </button>
      </div>
    </main>
  );
}
