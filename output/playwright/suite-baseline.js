async (page) => {
  await page.unrouteAll({ behavior: 'wait' });
  await page.goto('http://127.0.0.1:15173');
  await page.getByRole('navigation').getByRole('button', { name: 'Test cases', exact: true }).click();
  for (const width of [1440, 1024, 390]) {
    await page.setViewportSize({ width, height: 1000 });
    await page.screenshot({ path: `output/playwright/suite-before-${width}.png`, fullPage: true });
  }
}
