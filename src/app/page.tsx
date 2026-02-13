import { auth, signOut } from "@/auth"
import Link from "next/link"

export default async function Home() {
  const session = await auth()

  return (
    <main className="flex min-h-screen flex-col items-center justify-center p-24 bg-gray-50 dark:bg-zinc-950">
      <div className="z-10 w-full max-w-5xl items-center justify-between font-mono text-sm lg:flex">
        <p className="fixed left-0 top-0 flex w-full justify-center border-b border-gray-300 bg-gradient-to-b from-zinc-200 pb-6 pt-8 backdrop-blur-2xl dark:border-neutral-800 dark:bg-zinc-800/30 dark:from-inherit lg:static lg:w-auto  lg:rounded-xl lg:border lg:bg-gray-200 lg:p-4 lg:dark:bg-zinc-800/30">
          Katala Auth Base
        </p>
      </div>

      <div className="relative flex place-items-center mt-20 mb-20">
        <h1 className="text-4xl font-bold tracking-tighter sm:text-5xl md:text-6xl lg:text-7xl bg-clip-text text-transparent bg-gradient-to-r from-blue-500 to-purple-600">
          Katala
        </h1>
      </div>

      <div className="mb-32 grid text-center lg:mb-0 lg:w-full lg:max-w-5xl lg:grid-cols-1 lg:text-left">
        <div className="group rounded-3xl border border-transparent px-5 py-4 transition-colors hover:border-gray-300 hover:bg-gray-100 hover:dark:border-neutral-700 hover:dark:bg-neutral-800/30 bg-white dark:bg-zinc-900/50 backdrop-blur-sm shadow-sm">
          <h2 className={`mb-3 text-2xl font-semibold`}>
            Authentication Status
          </h2>
          <div className={`m-0 max-w-[30ch] text-sm opacity-50`}>
            {session ? (
              <div className="space-y-4">
                <p>Signed in as {session.user?.email}</p>
                <form
                  action={async () => {
                    "use server"
                    await signOut()
                  }}
                >
                  <button className="rounded-full bg-red-500/10 px-4 py-2 text-red-500 hover:bg-red-500/20 transition-colors">
                    Sign Out
                  </button>
                </form>
              </div>
            ) : (
              <div className="space-y-4">
                <p>Not signed in</p>
                <Link
                  href="/login"
                  className="inline-block rounded-full bg-blue-500/10 px-4 py-2 text-blue-500 hover:bg-blue-500/20 transition-colors"
                >
                  Sign In →
                </Link>
              </div>
            )}
          </div>
        </div>
      </div>
    </main>
  )
}
