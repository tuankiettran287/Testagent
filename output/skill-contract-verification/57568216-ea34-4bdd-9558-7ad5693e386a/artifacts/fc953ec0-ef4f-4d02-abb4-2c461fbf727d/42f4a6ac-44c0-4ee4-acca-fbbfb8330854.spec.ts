import { test, expect } from '@playwright/test';

test("Passphrase sai bị từ chối và vẫn ở signin", async ({ page }) => {
  test.setTimeout(600_000);
  page.setDefaultTimeout(10_000);
  await page.goto("http://127.0.0.1:55436/signin", { waitUntil: 'domcontentloaded', timeout: 30_000 });
  await expect(page.locator("[data-qa=\"account-id\"]")).toHaveCount(1, { timeout: 10_000 });
  await page.locator("[data-qa=\"account-id\"]").fill("native_demo");
  await expect(page.locator("[data-qa=\"passphrase\"]")).toHaveCount(1, { timeout: 10_000 });
  await page.locator("[data-qa=\"passphrase\"]").fill("wrong_for_native_fixture");
  await expect(page.locator("[data-qa=\"enter-portal\"]")).toHaveCount(1, { timeout: 10_000 });
  await page.locator("[data-qa=\"enter-portal\"]").click();
  await expect(page.locator("[data-qa=\"signin-problem\"]")).toHaveCount(1, { timeout: 10_000 });
  await expect(page.locator("[data-qa=\"signin-problem\"]")).toContainText("The passphrase is incorrect.");
  await expect(page).toHaveURL("http://127.0.0.1:55436/signin");
});
