import { test, expect } from "@playwright/test";

test.describe("API Health Check", () => {
  test("GET /api/auth should respond", async ({ request }) => {
    const response = await request.get("/api/auth/providers");
    // Auth endpoint should respond (200 or 401 are both valid)
    expect(response.status()).toBeLessThan(500);
  });

  test("GET /api/feedback should respond", async ({ request }) => {
    const response = await request.get("/api/feedback");
    expect(response.status()).toBeLessThan(500);
  });

  test("GET /api/kani should respond", async ({ request }) => {
    const response = await request.get("/api/kani");
    expect(response.status()).toBeLessThan(500);
  });

  test("GET /api/synergy should respond", async ({ request }) => {
    const response = await request.get("/api/synergy");
    expect(response.status()).toBeLessThan(500);
  });
});
