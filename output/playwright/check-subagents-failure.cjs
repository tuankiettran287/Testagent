async (page) => {
  await page.locator('.sub-agent-card').last().locator('.status').filter({hasText: 'FAILED'}).waitFor({timeout: 10000});
  if (await page.locator('.task-meta .status').textContent() !== 'FAILED') throw new Error('Parent did not reflect failure');
  await page.locator('.sub-agent-card').last().locator('summary').click();
  await page.locator('.sub-agent-detail .error-text').waitFor();
  await page.locator('.alert-error').waitFor();
  await page.screenshot({path: 'output/playwright/subagents-failed-mobile.png'});
  return {pollingUpdate: true, parentFailed: true, childErrorVisible: true};
}
