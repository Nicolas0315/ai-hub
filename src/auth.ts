import type { NextAuthConfig } from "next-auth";
import NextAuth from "next-auth";
import Credentials from "next-auth/providers/credentials";
import type { Provider } from "next-auth/providers";

function buildProviders(): Provider[] {
  const providers: Provider[] = [
    Credentials({
      credentials: {
        username: { label: "Username" },
        password: { label: "Password", type: "password" },
      },
      async authorize(credentials) {
        if (credentials?.username === "admin" && credentials?.password === "admin") {
          return { id: "1", name: "Admin User", email: "admin@example.com" };
        }
        return null;
      },
    }),
  ];

  // Low-risk integration pattern for World ID/OIDC (disabled by default)
  if (
    process.env.WORLD_ID_CLIENT_ID &&
    process.env.WORLD_ID_CLIENT_SECRET &&
    process.env.WORLD_ID_ISSUER
  ) {
    providers.push({
      id: "worldid",
      name: "World ID",
      type: "oidc",
      clientId: process.env.WORLD_ID_CLIENT_ID,
      clientSecret: process.env.WORLD_ID_CLIENT_SECRET,
      issuer: process.env.WORLD_ID_ISSUER,
      checks: ["pkce", "state"],
      profile(profile: Record<string, unknown>) {
        return {
          id: String(profile.sub ?? "unknown"),
          name: (profile.name as string | undefined) ?? "World User",
          email: (profile.email as string | undefined) ?? null,
        };
      },
    } as Provider);
  }

  return providers;
}

export const authConfig = {
  providers: buildProviders(),
  pages: {
    signIn: "/login",
  },
  callbacks: {
    authorized({ auth }) {
      // Logic handled in middleware.ts
      return true;
    },
  },
} satisfies NextAuthConfig;

export const { handlers, auth, signIn, signOut } = NextAuth(authConfig);
