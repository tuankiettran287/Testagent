async (page) => {
  await page.emulateMedia({ reducedMotion: 'reduce' });
  await page.reload();
  await page.locator('.activity-button').first().waitFor();
  const results = [];
  const measure = async () => page.evaluate(() => {
    const panel = document.querySelector('.activity-panel');
    const box = panel.getBoundingClientRect();
    const items = [...panel.querySelectorAll('.activity-item')];
    return {
      panel: { client: panel.clientWidth, scroll: panel.scrollWidth },
      items: items.map(item => {
        const status = item.querySelector('.status');
        const statusBox = status.getBoundingClientRect();
        const title = item.querySelector('strong');
        return { client: item.clientWidth, scroll: item.scrollWidth,
          titleWrap: getComputedStyle(title).whiteSpace,
          statusInside: statusBox.left >= box.left && statusBox.right <= box.right,
          status: status.textContent };
      }),
    };
  });
  const validate = (layout, label) => {
    if (layout.panel.scroll > layout.panel.client + 1 || layout.items.some(item =>
      item.scroll > item.client + 1 || !item.statusInside || item.titleWrap !== 'normal')) {
      throw new Error(`${label}: clipped content ${JSON.stringify(layout)}`);
    }
  };
  for (const width of [1440, 1024, 390]) {
    await page.setViewportSize({ width, height: 900 });
    await page.evaluate(() => document.fonts.ready);
    const layout = await measure();
    validate(layout, `${width}px real activity`);
    await page.locator('.activity-panel').screenshot({ path: `output/playwright/activity-after-${width}.png` });
    await page.locator('.activity-button').first().click();
    await page.getByRole('dialog').waitFor();
    await page.getByRole('button', { name: 'Đóng', exact: true }).click();
    const original = await page.locator('.activity-button strong').first().textContent();
    await page.locator('.activity-button strong').first().evaluate(element => {
      element.textContent = 'https://example.test/' + 'long-unbroken-identifier'.repeat(120);
    });
    const longText = await measure();
    validate(longText, `${width}px long identifier`);
    await page.locator('.activity-button strong').first().evaluate((element, text) => { element.textContent = text; }, original);
    results.push({ width, rows: layout.items.length, noOverflow: true, statusesVisible: true, longTextWraps: true, opensTask: true });
  }
  return results;
}
