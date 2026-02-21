import Link from "next/link";
import { auth, signOut } from "@/auth";
import SynergyDashboard from "@/components/SynergyDashboard";
import { sampleIdentities } from "@/lib/kani/dataProvider";
import { sharedLedger } from "@/lib/ledger/store";

export default async function Home() {
  const session = await auth();
  const recentLedger = sharedLedger.getHistory(5);

  return (
    <main className="flex min-h-screen flex-col items-center p-8 md:p-24 bg-gray-50 dark:bg-zinc-950">
      <div className="z-10 w-full max-w-5xl items-center justify-between font-mono text-sm lg:flex">
        <p className="fixed left-0 top-0 flex w-full justify-center border-b border-gray-300 bg-gradient-to-b from-zinc-200 pb-6 pt-8 backdrop-blur-2xl dark:border-neutral-800 dark:bg-zinc-800/30 dark:from-inherit lg:static lg:w-auto lg:rounded-xl lg:border lg:bg-gray-200 lg:p-4 lg:dark:bg-zinc-800/30">
          Katala (カタラ)
        </p>
      </div>

      <div className="relative flex place-items-center mt-12 mb-8">
        <h1 className="text-4xl font-bold tracking-tighter sm:text-5xl md:text-6xl lg:text-7xl bg-clip-text text-transparent bg-gradient-to-r from-blue-500 to-purple-600">
          Katala
        </h1>
      </div>

      <div className="mb-8 text-center">
        <p className="text-sm text-gray-600 dark:text-gray-400">AI間通信・仲介パイプライン</p>
      </div>

      {/* Authentication Status */}
      <div className="mb-12 w-full max-w-5xl">
        <div className="group rounded-3xl border border-transparent px-5 py-4 transition-colors hover:border-gray-300 hover:bg-gray-100 hover:dark:border-neutral-700 hover:dark:bg-neutral-800/30 bg-white dark:bg-zinc-900/50 backdrop-blur-sm shadow-sm">
          <h2 className="mb-3 text-xl font-semibold">認証ステータス</h2>
          <div className="m-0 text-sm opacity-75">
            {session ? (
              <div className="space-y-4">
                <p>サインイン中: {session.user?.email}</p>
                <form
                  action={async () => {
                    "use server";
                    await signOut();
                  }}
                >
                  <button className="rounded-full bg-red-500/10 px-4 py-2 text-red-500 hover:bg-red-500/20 transition-colors">
                    サインアウト
                  </button>
                </form>
              </div>
            ) : (
              <div className="space-y-4">
                <p>未サインイン</p>
                <Link
                  href="/login"
                  className="inline-block rounded-full bg-blue-500/10 px-4 py-2 text-blue-500 hover:bg-blue-500/20 transition-colors"
                >
                  サインイン →
                </Link>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Board: Recent Agreement Events */}
      <div className="mb-12 w-full max-w-5xl">
        <div className="group rounded-3xl border border-transparent px-5 py-4 bg-white dark:bg-zinc-900/50 backdrop-blur-sm shadow-sm">
          <h2 className="mb-3 text-xl font-semibold">Board（直近の合意ログ）</h2>
          {recentLedger.length === 0 ? (
            <p className="text-sm opacity-70">まだ記録はありません</p>
          ) : (
            <ul className="space-y-2 text-sm">
              {recentLedger.map((entry) => (
                <li key={entry.id} className="rounded-lg border border-zinc-200/50 dark:border-zinc-800 px-3 py-2">
                  <div className="font-mono text-xs opacity-70">{new Date(entry.timestamp).toLocaleString("ja-JP")}</div>
                  <div>{entry.eventType}</div>
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>

      {/* Synergy Dashboard - Phase 3 */}
      <SynergyDashboard
        identityA={sampleIdentities.analytical}
        identityB={sampleIdentities.empathetic}
      />
    </main>
  );
}
