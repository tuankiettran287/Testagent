import { mkdir, writeFile } from 'node:fs/promises';
import { basename, join } from 'node:path';
import { chromium, expect, type Page } from '@playwright/test';
import { locatorExpression, resolveLocator } from './locators.js';
import type { Automation, BrowserAction } from './protocol.js';
import { captureSnapshot } from './snapshot.js';

export type BrowserResult = {
  status: 'PASS' | 'FAIL' | 'ERROR' | 'TIMEOUT';
  message: string;
  artifacts: string[];
};

function errorMessage(error: unknown): string {
  return error instanceof Error ? error.message : String(error);
}

export function checkedUrl(baseUrl: string, requested: string): string {
  let base: URL;
  let result: URL;
  try {
    base = new URL(baseUrl);
    result = new URL(requested, `${baseUrl.replace(/\/+$/, '')}/`);
  } catch {
    throw new Error('Project base_url must be an HTTP(S) URL before execution');
  }
  if (!['http:', 'https:'].includes(base.protocol) || !base.hostname) {
    throw new Error('Project base_url must be an HTTP(S) URL before execution');
  }
  if (result.origin !== base.origin) {
    throw new Error('Browser actions must remain on the project origin');
  }
  return result.href;
}

export function compilePlaywright(automation: Automation, baseUrl: string, title: string): string {
  const lines = [
    "import { test, expect } from '@playwright/test';",
    '',
    `test(${JSON.stringify(title)}, async ({ page }) => {`,
    '  test.setTimeout(600_000);',
    '  page.setDefaultTimeout(10_000);',
  ];
  for (const action of automation.actions) {
    if (action.action === 'navigate') {
      lines.push(`  await page.goto(${JSON.stringify(checkedUrl(baseUrl, action.url!))}, { waitUntil: 'domcontentloaded', timeout: 30_000 });`);
      continue;
    }
    if (action.action === 'assert_url') {
      lines.push(`  await expect(page).toHaveURL(${JSON.stringify(checkedUrl(baseUrl, action.url!))});`);
      continue;
    }
    const locator = locatorExpression(action.target!);
    lines.push(`  await expect(${locator}).toHaveCount(1, { timeout: 10_000 });`);
    if (action.action === 'fill') lines.push(`  await ${locator}.fill(${JSON.stringify(action.value)});`);
    else if (action.action === 'click') lines.push(`  await ${locator}.click();`);
    else if (action.action === 'check') lines.push(`  await ${locator}.check();`);
    else if (action.action === 'select') lines.push(`  await ${locator}.selectOption(${JSON.stringify(action.value)});`);
    else if (action.action === 'assert_visible') lines.push(`  await expect(${locator}).toBeVisible();`);
    else if (action.action === 'assert_text') lines.push(`  await expect(${locator}).toContainText(${JSON.stringify(action.value)});`);
  }
  lines.push('});');
  return `${lines.join('\n')}\n`;
}

export async function inspectUi(baseUrl: string, path: string) {
  const url = checkedUrl(baseUrl, path);
  const browser = await chromium.launch({ headless: true });
  try {
    const page = await browser.newPage({ ignoreHTTPSErrors: false });
    const response = await page.goto(url, { waitUntil: 'domcontentloaded', timeout: 30_000 });
    await page.waitForLoadState('load', { timeout: 10_000 }).catch(() => undefined);
    checkedUrl(baseUrl, page.url());
    return await captureSnapshot(page, response?.status());
  } finally {
    await browser.close();
  }
}

export async function performAction(page: Page, baseUrl: string, action: BrowserAction) {
  if (action.action === 'navigate') {
    await page.goto(checkedUrl(baseUrl, action.url!), { waitUntil: 'domcontentloaded', timeout: 30_000 });
  } else if (action.action === 'assert_url') {
    await expect(page).toHaveURL(checkedUrl(baseUrl, action.url!));
  } else {
    const locator = resolveLocator(page, action.target!);
    // Never silently select the first match or force a click on the wrong control.
    await expect(locator, `Locator must identify exactly one element: ${locatorExpression(action.target!)}`).toHaveCount(1, { timeout: 10_000 });
    if (action.action === 'fill') await locator.fill(action.value!);
    else if (action.action === 'click') await locator.click();
    else if (action.action === 'check') await locator.check();
    else if (action.action === 'select') await locator.selectOption(action.value!);
    else if (action.action === 'assert_visible') await expect(locator).toBeVisible();
    else if (action.action === 'assert_text') await expect(locator).toContainText(action.value!);
  }
  checkedUrl(baseUrl, page.url());
}

export async function executeBrowserCase(
  baseUrl: string, caseId: string, artifactDir: string, automation: Automation, title = caseId,
): Promise<BrowserResult> {
  checkedUrl(baseUrl, '/');
  await mkdir(artifactDir, { recursive: true });
  const browser = await chromium.launch({ headless: true });
  const artifacts: string[] = [];
  const sourceFile = `${caseId}.spec.ts`;
  await writeFile(join(artifactDir, sourceFile), compilePlaywright(automation, baseUrl, title), 'utf8');
  artifacts.push(sourceFile);
  let status: BrowserResult['status'] = 'PASS';
  let message = 'All assertions passed';
  let activeAction: BrowserAction | undefined;
  try {
    const context = await browser.newContext({ ignoreHTTPSErrors: false, recordVideo: { dir: artifactDir } });
    await context.tracing.start({ screenshots: true, snapshots: true, sources: true });
    const page = await context.newPage();
    page.setDefaultTimeout(10_000);
    const video = page.video();
    try {
      for (const action of automation.actions) {
        activeAction = action;
        await performAction(page, baseUrl, action);
      }
      // Short smoke tests can finish before the first video frame arrives.
      // Render the final state so the recorder can finish, and keep the evidence.
      const screenshot = join(artifactDir, `${caseId}.png`);
      await page.screenshot({ path: screenshot, fullPage: true });
      artifacts.push(basename(screenshot));
    } catch (error) {
      status = activeAction?.action.startsWith('assert_') ? 'FAIL'
        : error instanceof Error && error.name === 'TimeoutError' ? 'TIMEOUT' : 'ERROR';
      message = errorMessage(error).slice(0, 1500);
      const screenshot = join(artifactDir, `${caseId}.png`);
      try {
        await page.screenshot({ path: screenshot, fullPage: true });
        artifacts.push(basename(screenshot));
      } catch { /* The page may already be closed. */ }
    } finally {
      const trace = join(artifactDir, `${caseId}-trace.zip`);
      try {
        await context.tracing.stop({ path: trace });
        artifacts.push(basename(trace));
      } catch { /* Preserve the test result if trace capture fails. */ }
      await context.close();
      if (video) {
        try { artifacts.push(basename(await video.path())); }
        catch { /* Video may be unavailable if browser launch failed. */ }
      }
    }
  } finally {
    await browser.close();
  }
  return { status, message, artifacts };
}
