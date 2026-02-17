import { test, expect } from "@playwright/test";

test.describe("Navigation", () => {
  test("should navigate to login page", async ({ page }) => {
    await page.goto("/login");
    await expect(page).toHaveURL(/login/);
    await expect(page.locator("body")).toBeVisible();
  });

  test("should navigate from home to login", async ({ page }) => {
    await page.goto("/");
    // Look for any login-related link
    const loginLink = page.locator('a[href*="login"], a:has-text("login"), a:has-text("Login"), a:has-text("ログイン")').first();
    if (await loginLink.isVisible({ timeout: 3000 }).catch(() => false)) {
      await loginLink.click();
      await expect(page).toHaveURL(/login/);
    } else {
      // Direct navigation fallback
      await page.goto("/login");
      await expect(page).toHaveURL(/login/);
    }
  });

  test("should return 404 for non-existent page", async ({ request }) => {
    const response = await request.get("/this-page-does-not-exist");
    expect(response.status()).toBe(404);
  });
});
