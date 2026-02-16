import NextAuth from "next-auth"
import type { NextAuthConfig } from "next-auth"

import Credentials from "next-auth/providers/credentials"

export const authConfig = {
  providers: [
    Credentials({
      credentials: {
        username: { label: "Username" },
        password: { label: "Password", type: "password" },
      },
      async authorize(credentials) {
        if (credentials?.username === "admin" && credentials?.password === "admin") {
          return { id: "1", name: "Admin User", email: "admin@example.com" }
        }
        return null
      },
    }),
  ],
  pages: {
    signIn: "/login",
  },
  callbacks: {
    authorized({ auth }) {
      // Logic handled in middleware.ts
      return true
    },
  },
} satisfies NextAuthConfig

export const { handlers, auth, signIn, signOut } = NextAuth(authConfig)
