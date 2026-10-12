async (page) => {
  const metrics = await page.evaluate(() => ({
    viewport: innerWidth,
    pageWidth: document.documentElement.scrollWidth,
    drawerWidth: document.querySelector('.drawer').clientWidth,
    drawerContentWidth: document.querySelector('.drawer').scrollWidth,
    expanded: document.querySelector('.sub-agent-card').open,
  }));
  if (metrics.pageWidth > metrics.viewport || metrics.drawerContentWidth > metrics.drawerWidth) throw new Error('Horizontal overflow');
  const first = page.locator('.sub-agent-card').first();
  await first.locator('summary').focus();
  await page.keyboard.press('Enter');
  if (await first.evaluate(node => node.open) === metrics.expanded) throw new Error('Keyboard details toggle failed');
  await page.getByRole('button', {name: 'Đóng', exact: true}).click();
  const mode = page.getByRole('combobox', {name: 'Cách điều phối', exact: true});
  await mode.selectOption('single');
  if (await mode.inputValue() !== 'single') throw new Error('Single mode selection failed');
  await page.getByRole('combobox', {name: 'Kỹ năng agent', exact: true}).selectOption('performance');
  if (await mode.count()) throw new Error('Direct specialist should not expose orchestration options');
  await page.getByRole('combobox', {name: 'Kỹ năng agent', exact: true}).selectOption('orchestrator');
  if (await mode.inputValue() !== 'single') throw new Error('Orchestration preference was lost');
  await mode.selectOption('auto');
  console.log(JSON.stringify({metrics, keyboardToggle: true, modeControls: true}));
}
