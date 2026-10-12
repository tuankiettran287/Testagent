import { existsSync } from 'node:fs';
import { chromium } from '@playwright/test';
import { parseCommand } from './protocol.js';
import { compilePlaywright, executeBrowserCase, inspectUi } from './runtime.js';

async function readRequest(): Promise<unknown> {
  let input = '';
  for await (const chunk of process.stdin) {
    input += chunk.toString();
    if (input.length > 2_000_000) throw new Error('Browser runner request is too large');
  }
  return JSON.parse(input) as unknown;
}

async function main(): Promise<void> {
  const request = parseCommand(await readRequest());
  const result = request.command === 'health'
    ? { browserInstalled: existsSync(chromium.executablePath()) }
    : request.command === 'execute'
    ? await executeBrowserCase(request.baseUrl, request.caseId, request.artifactDir, request.automation, request.title)
    : request.command === 'inspect'
      ? await inspectUi(request.baseUrl, request.path)
      : { source: compilePlaywright(request.automation, request.baseUrl, request.title) };
  process.stdout.write(JSON.stringify(result));
}

main().catch(error => {
  const message = error instanceof Error ? error.message : String(error);
  process.stdout.write(JSON.stringify({ error: message.slice(0, 2000) }));
  process.exitCode = 1;
});
