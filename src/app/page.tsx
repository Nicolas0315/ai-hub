"use client";

import { useEffect, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";

interface NegotiationLog {
  id: string;
  agent: string;
  message: string;
  status: "thinking" | "negotiating" | "matched";
}

export default function Home() {
  const [logs, setLogs] = useState<NegotiationLog[]>([]);
  const [synergy, setSynergy] = useState(0);

  useEffect(() => {
    const timer = setInterval(() => {
      setSynergy(prev => Math.min(prev + 0.01, 0.94));
    }, 2000);

    setLogs([
      { id: "1", agent: "しろくま", message: "ニコラスの直近の関心事を『UGC広告の質感』に更新", status: "thinking" },
      { id: "2", agent: "カニ", message: "4側のTailscaleノード『junhwi-1』の疎通を確認", status: "negotiating" },
      { id: "3", agent: "System", message: "エージェント間バックチャネル (SSH) が開通しました", status: "matched" },
    ]);

    return () => clearInterval(timer);
  }, []);

  return (
    <main className="min-h-screen max-w-lg mx-auto px-6 py-12 bg-black text-white selection:bg-blue-500/30 font-sans">
      <header className="mb-12">
        <motion.h1 
          initial={{ opacity: 0, y: -20 }}
          animate={{ opacity: 1, y: 0 }}
          className="text-4xl font-bold tracking-tight mb-2"
        >
          Katala
        </motion.h1>
        <p className="text-[#86868b] text-lg">Agent-to-Agent Mediation Pipeline</p>
      </header>

      {/* Connection Sphere */}
      <section className="relative aspect-square mb-12 flex items-center justify-center">
        <div className="absolute inset-0 bg-gradient-to-br from-blue-600/20 to-purple-600/20 rounded-full blur-3xl animate-pulse" />
        
        {/* Animated Rings */}
        <motion.div 
          animate={{ rotate: 360 }}
          transition={{ duration: 20, repeat: Infinity, ease: "linear" }}
          className="absolute w-full h-full border border-white/5 rounded-full"
        />
        <motion.div 
          animate={{ rotate: -360 }}
          transition={{ duration: 15, repeat: Infinity, ease: "linear" }}
          className="absolute w-[80%] h-[80%] border border-blue-500/10 rounded-full"
        />

        <div className="text-center z-10">
          <motion.div 
            animate={{ scale: [1, 1.1, 1] }}
            transition={{ duration: 4, repeat: Infinity }}
            className="w-32 h-32 bg-blue-500 rounded-full mx-auto mb-6 flex items-center justify-center shadow-[0_0_50px_rgba(59,130,246,0.5)]"
          >
            <span className="text-4xl">🐻‍❄️</span>
          </motion.div>
          <div className="space-y-1">
            <p className="font-semibold text-2xl tracking-wide">{(synergy * 100).toFixed(1)}%</p>
            <p className="text-[#86868b] text-xs uppercase tracking-widest">Matched Synergy</p>
          </div>
        </div>

        {/* Floating Partner Node */}
        <motion.div 
          animate={{ x: [0, 10, 0], y: [0, -10, 0] }}
          transition={{ duration: 5, repeat: Infinity }}
          className="absolute top-10 right-10 w-16 h-16 bg-zinc-800/80 rounded-2xl flex items-center justify-center backdrop-blur-xl border border-white/10"
        >
          <span className="text-2xl">🦀</span>
        </motion.div>
      </section>

      {/* Mediation Logs */}
      <section>
        <div className="flex items-center justify-between mb-6 px-2">
          <h2 className="text-xl font-semibold">Mediation Insights</h2>
          <span className="text-[10px] bg-blue-500/20 text-blue-400 px-2 py-1 rounded-full uppercase tracking-tighter animate-pulse">Live</span>
        </div>
        <div className="space-y-3">
          <AnimatePresence>
            {logs.map((log) => (
              <motion.div 
                key={log.id}
                initial={{ opacity: 0, x: -10 }}
                animate={{ opacity: 1, x: 0 }}
                className="bg-zinc-900/50 backdrop-blur-md rounded-2xl p-4 border border-white/5 flex gap-4 items-start"
              >
                <div className="mt-1 w-2 h-2 rounded-full bg-blue-500 shadow-[0_0_8px_rgba(59,130,246,0.8)]" />
                <div>
                  <p className="text-[10px] text-[#86868b] uppercase tracking-wider mb-1">{log.agent}</p>
                  <p className="text-sm leading-relaxed text-zinc-200">{log.message}</p>
                </div>
              </motion.div>
            ))}
          </AnimatePresence>
        </div>
      </section>

      {/* Ghost Input Prototype */}
      <div className="fixed bottom-12 left-0 right-0 px-6 max-w-lg mx-auto space-y-4">
        <p className="text-center text-[10px] text-[#86868b] italic opacity-50">
          AI Suggestion: \"もっと技術的なシナジーを深めて\"
        </p>
        <button className="w-full py-4 text-lg font-medium rounded-2xl bg-white text-black hover:bg-zinc-200 active:scale-95 transition-all shadow-2xl">
          Tune Identity Vector
        </button>
      </div>
    </main>
  );
}
