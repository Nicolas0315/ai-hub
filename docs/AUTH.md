# Authentication Setup (NextAuth v5)

This project uses [Auth.js (NextAuth.js v5 Beta)](https://authjs.dev) for authentication.

## Setup

1.  **Environment Variables**:
    -   `AUTH_SECRET`: Generate using `openssl rand -base64 32`.
    -   Store secrets in 1Password and use `op run` to inject them, or use `.env.local` for local development.

2.  **Providers**:
    -   Currently configured with a **Credentials** provider for testing.
    -   **Username**: `admin`
    -   **Password**: `admin`

## 1Password Integration

To run the project with 1Password CLI:

```bash
op run --env-file=.env.template -- npm run dev
```

Ensure your 1Password vault contains the necessary secrets referenced in `.env.template`.

## Architecture

-   **Config**: `src/auth.ts`
-   **Middleware**: `src/middleware.ts` (protects routes)
-   **API Route**: `src/app/api/auth/[...nextauth]/route.ts`
-   **Login Page**: `src/app/login/page.tsx` (Server Action based)

## Adding Providers

To add OAuth providers (e.g., GitHub, Google), update `src/auth.ts`:

```typescript
import GitHub from "next-auth/providers/github"

export const authConfig = {
  providers: [
    GitHub,
    // ...
  ],
  // ...
}
```
