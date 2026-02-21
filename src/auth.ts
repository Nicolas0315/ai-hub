import type { NextAuthConfig } from "next-auth";
import NextAuth from "next-auth";
import Credentials from "next-auth/providers/credentials";
import type { Provider } from "next-auth/providers";

function buildProviders(): Provider[] {
  const providers: Provider[] = [];

  // Dev-only credentials provider (explicit opt-in)
  if (process.env.KATALA_DEV_CREDENTIALS === "true") {
    const devUser = process.env.KATALA_DEV_USERNAME;
    const devPass = process.env.KATALA_DEV_PASSWORD;

    if (devUser && devPass) {
      providers.push(
        Credentials({
          credentials: {
            username: { label: "Username" },
            password: { label: "Password", type: "password" },
          },
          async authorize(credentials) {
            if (credentials?.username === devUser && credentials?.password === devPass) {
              return { id: "dev-1", name: "Dev User", email: "dev@example.com" };
            }
            return null;
          },
        }),
      );
    }
  }

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

  // Safety fallback: keep auth subsystem bootable but reject all logins
  if (providers.length === 0) {
    providers.push(
      Credentials({
        credentials: {
          username: { label: "Username" },
          password: { label: "Password", type: "password" },
        },
        async authorize() {
          return null;
        },
      }),
    );
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
