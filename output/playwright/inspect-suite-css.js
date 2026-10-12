async (page) => {
  await page.getByRole('navigation').getByRole('button', { name: 'Test cases', exact: true }).click();
  return await page.evaluate(() => ({
    sheets: [...document.styleSheets].map(sheet => {
      try { return { href: sheet.href, count: sheet.cssRules.length, matches: [...sheet.cssRules].filter(rule => rule.cssText.includes('suite-controls')).map(rule => rule.cssText) }; }
      catch { return { href: sheet.href }; }
    }),
    computed: ['.suite-controls', '.run-options', '.suite-table'].map(selector => { const node = document.querySelector(selector); const style = getComputedStyle(node); return { selector, padding: style.padding, display: style.display, minWidth: style.minWidth }; }),
    contains: [...document.querySelectorAll('style')].map(node => node.textContent.includes('.suite-controls')),
  }));
}
