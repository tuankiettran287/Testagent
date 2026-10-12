async (page) => {
  const results = [];
  const measure = async (view, width) => {
    await page.evaluate(() => document.fonts.ready);
    const dimensions = await page.evaluate(() => ({
      viewport: window.innerWidth,
      document: document.documentElement.scrollWidth,
      overflow: [...document.querySelectorAll('.panel, .drawer, .ai-picker, .agent-selector, .activity-item, .skill-reference, .provider-card, .result-card a, .page-header, .composer-footer')]
        .map(element => ({ selector: element.className || element.tagName, text: element.textContent.slice(0, 90), client: element.clientWidth, scroll: element.scrollWidth }))
        .filter(row => row.scroll > row.client + 1),
      ellipsis: [...document.querySelectorAll('.activity-item strong, .readiness-step small')]
        .filter(element => element.scrollWidth > element.clientWidth + 1)
        .map(element => ({ text: element.textContent.slice(0, 90), client: element.clientWidth, scroll: element.scrollWidth })),
    }));
    results.push({ view, width, ...dimensions });
    await page.screenshot({ path: `output/playwright/clipping-before-${view}-${width}.png`, fullPage: true });
  };
  for (const width of [1440, 1024, 390]) {
    await page.setViewportSize({ width, height: 900 });
    await page.getByRole('heading', { name: 'Giao việc cho TestAgent' }).waitFor();
    await measure('overview', width);
    const firstTask = page.locator('.activity-button').first();
    await firstTask.click();
    await page.getByRole('dialog').waitFor();
    await measure('task', width);
    await page.getByRole('button', { name: 'Đóng', exact: true }).click();
  }
  return results;
}
