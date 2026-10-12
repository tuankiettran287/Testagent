/** Stateful browser channel: the Python agent owns this process and exchanges JSON lines. */
import { createInterface } from 'node:readline';
import { chromium } from '@playwright/test';
import { parseAutomation, parseCommand } from './protocol.js';
import { checkedUrl, performAction } from './runtime.js';
import { captureSnapshot } from './snapshot.js';

const output = (value: unknown) => process.stdout.write(JSON.stringify(value) + '\n');
const input = createInterface({ input: process.stdin, crlfDelay: Infinity });
const lines = input[Symbol.asyncIterator]();
const first = await lines.next();
const request = parseCommand({ ...JSON.parse(first.value || '{}'), command: 'inspect' });
if (request.command !== 'inspect') throw new Error('Expected browser session configuration');
const { baseUrl, path } = request;
const browser = await chromium.launch({ headless: true });
try {
  async function openPage() {
    const fresh = await browser.newPage();
    fresh.setDefaultTimeout(10_000);
    // Block cross-origin document navigation before a click can send the browser there.
    await fresh.route('**/*', route => {
      if (route.request().isNavigationRequest() && route.request().frame() === fresh.mainFrame()) {
        try { checkedUrl(baseUrl, route.request().url()); }
        catch { return route.abort('blockedbyclient'); }
      }
      return route.continue();
    });
    const response = await fresh.goto(checkedUrl(baseUrl, path), { waitUntil: 'domcontentloaded', timeout: 30_000 });
    await fresh.waitForLoadState('load', { timeout: 10_000 }).catch(() => undefined);
    return { page: fresh, snapshot: await captureSnapshot(fresh, response?.status()) };
  }
  let initial = await openPage();
  let page = initial.page;
  output({ snapshot: initial.snapshot });
  while (true) {
    const line = await lines.next();
    if (line.done) break;
    let command;
    try {
      if (line.value.length > 200_000) throw new Error('Session request is too large');
      command = JSON.parse(line.value);
      if (command.command === 'close') { output({ closed: true }); break; }
      if (command.command === 'reset') {
        await page.close();
        initial = await openPage();
        page = initial.page;
        output({ snapshot: initial.snapshot });
        continue;
      }
      if (command.command === 'observe') { output({ snapshot: await captureSnapshot(page) }); continue; }
      if (command.command !== 'act') throw new Error('Unsupported session command');
      const automation = parseAutomation(command.automation);
      const performed = [];
      let error: string | undefined;
      for (const action of automation.actions) {
        try {
          await performAction(page, request.baseUrl, action);
          performed.push(action);
        } catch (failure) { error = String(failure).slice(0, 1800); break; }
      }
      await page.waitForLoadState('domcontentloaded', { timeout: 10_000 }).catch(() => undefined);
      // DOM may update asynchronously without document navigation.
      await page.screenshot({ timeout: 5000 }).catch(() => undefined);
      output({ performed, error, snapshot: await captureSnapshot(page) });
    } catch (error) { output({ error: String(error).slice(0, 2000) }); }
  }
} catch (error) { output({ error: String(error).slice(0, 2000) }); }
finally { input.close(); await browser.close(); }
