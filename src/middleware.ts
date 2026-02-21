import NextAuth from "next-auth";
import { authConfig } from "./auth";

export const { auth } = NextAuth(authConfig);

export default auth((req) => {
  const { nextUrl } = req;
  const isLoggedIn = !!req.auth;
  const isLoginPage = nextUrl.pathname.startsWith("/login");

  if (isLoggedIn && isLoginPage) {
    return Response.redirect(new URL("/dashboard", nextUrl));
  }

  if (!isLoggedIn && !isLoginPage) {
    return Response.redirect(new URL("/login", nextUrl));
  }
});

export const config = {
  matcher: ["/((?!api|_next/static|_next/image|favicon.ico).*)"],
};
