import type { FullConfig } from '@playwright/test';
import { mkdir, writeFile } from 'node:fs/promises';
import path from 'node:path';

export default async function finalize(config: FullConfig) {
  const baseURL = config.projects[0].use.baseURL!;
  const output = path.dirname(config.projects[0].outputDir);
  const response = await fetch(`${baseURL}/__fixture/finalize`, { method: 'POST', signal: AbortSignal.timeout(30_000) });
  if (!response.ok) throw new Error(`Fixture cleanup failed: HTTP ${response.status}`);
  const result = await response.json();
  await mkdir(output, { recursive: true });
  await writeFile(path.join(output, 'fixture-finalization.json'), JSON.stringify(result, null, 2));
}
