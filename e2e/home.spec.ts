import { test, expect } from "@playwright/test";

test.describe("Home Page", () => {
  test("should load the top page", async ({ page }) => {
    await page.goto("/");
    await expect(page).toHaveURL("/");
    // Page should have a visible body
    await expect(page.locator("body")).toBeVisible();
  });

  test("should have a valid title", async ({ page }) => {
    await page.goto("/");
    const title = await page.title();
    expect(title).toBeTruthy();
  });

  test("should not return error status", async ({ request }) => {
    const response = await request.get("/");
    expect(response.ok()).toBeTruthy();
  });
});
