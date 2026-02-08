import { signIn } from "@/auth"
import { headers } from "next/headers"
import { redirect } from "next/navigation"

export default async function LoginPage(props: {
  searchParams: Promise<{ callbackUrl: string | undefined }>
}) {
  const searchParams = await props.searchParams
  const error = searchParams?.error
  
  return (
    <div className="flex min-h-screen items-center justify-center bg-gray-50 dark:bg-zinc-900">
      <div className="w-full max-w-sm space-y-8 p-8 bg-white dark:bg-black/40 backdrop-blur-xl rounded-3xl shadow-2xl border border-gray-200 dark:border-white/10">
        <div className="text-center">
          <h1 className="text-3xl font-semibold tracking-tight text-gray-900 dark:text-white">
            Welcome Back
          </h1>
          <p className="mt-2 text-sm text-gray-500 dark:text-gray-400">
            Sign in to your account
          </p>
        </div>

        {error && (
          <div className="rounded-lg bg-red-50 dark:bg-red-900/30 p-3 text-sm text-red-500 dark:text-red-400 text-center">
            {error === "CredentialsSignin" ? "Invalid credentials" : "Authentication failed"}
          </div>
        )}

        <form
          action={async (formData) => {
            "use server"
            await signIn("credentials", formData)
          }}
          className="mt-8 space-y-6"
        >
          <div className="space-y-4">
            <div>
              <label 
                htmlFor="username" 
                className="block text-sm font-medium text-gray-700 dark:text-gray-300 ml-1 mb-1"
              >
                Username
              </label>
              <input
                id="username"
                name="username"
                type="text"
                autoComplete="username"
                required
                className="block w-full rounded-2xl border-0 py-3 pl-4 text-gray-900 shadow-sm ring-1 ring-inset ring-gray-300 placeholder:text-gray-400 focus:ring-2 focus:ring-inset focus:ring-blue-500 sm:text-sm sm:leading-6 dark:bg-white/5 dark:text-white dark:ring-white/10 dark:focus:ring-blue-500 transition-all duration-200"
                placeholder="admin"
              />
            </div>

            <div>
              <label 
                htmlFor="password" 
                className="block text-sm font-medium text-gray-700 dark:text-gray-300 ml-1 mb-1"
              >
                Password
              </label>
              <input
                id="password"
                name="password"
                type="password"
                autoComplete="current-password"
                required
                className="block w-full rounded-2xl border-0 py-3 pl-4 text-gray-900 shadow-sm ring-1 ring-inset ring-gray-300 placeholder:text-gray-400 focus:ring-2 focus:ring-inset focus:ring-blue-500 sm:text-sm sm:leading-6 dark:bg-white/5 dark:text-white dark:ring-white/10 dark:focus:ring-blue-500 transition-all duration-200"
                placeholder="admin"
              />
            </div>
          </div>

          <div>
            <button
              type="submit"
              className="flex w-full justify-center rounded-2xl bg-blue-600 px-3 py-3.5 text-sm font-semibold text-white shadow-sm hover:bg-blue-500 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-blue-600 transition-all active:scale-[0.98]"
            >
              Sign in
            </button>
          </div>
        </form>
        
        <div className="text-center text-xs text-gray-400 dark:text-gray-600 mt-4">
          Demo: admin / admin
        </div>
      </div>
    </div>
  )
}
