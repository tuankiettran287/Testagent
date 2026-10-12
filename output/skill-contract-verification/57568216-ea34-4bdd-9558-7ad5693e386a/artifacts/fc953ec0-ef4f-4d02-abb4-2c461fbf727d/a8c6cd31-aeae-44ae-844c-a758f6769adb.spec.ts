import { test, expect } from '@playwright/test';

test("Đăng nhập hợp lệ tới portal của native_demo", async ({ page }) => {
  test.setTimeout(600_000);
  page.setDefaultTimeout(10_000);
  await page.goto("http://127.0.0.1:55436/signin", { waitUntil: 'domcontentloaded', timeout: 30_000 });
  await expect(page.locator("[data-qa=\"account-id\"]")).toHaveCount(1, { timeout: 10_000 });
  await page.locator("[data-qa=\"account-id\"]").fill("native_demo");
  await expect(page.locator("[data-qa=\"passphrase\"]")).toHaveCount(1, { timeout: 10_000 });
  await page.locator("[data-qa=\"passphrase\"]").fill("portable_test_secret_42");
  await expect(page.locator("[data-qa=\"enter-portal\"]")).toHaveCount(1, { timeout: 10_000 });
  await page.locator("[data-qa=\"enter-portal\"]").click();
  await expect(page).toHaveURL("http://127.0.0.1:55436/portal");
  await expect(page.locator("[data-qa=\"portal-heading\"]")).toHaveCount(1, { timeout: 10_000 });
  await expect(page.locator("[data-qa=\"portal-heading\"]")).toContainText("Portal for native_demo");
});
