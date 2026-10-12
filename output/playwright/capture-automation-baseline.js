async (page) => {
  await page.unrouteAll({ behavior: 'wait' });
  await page.goto('http://127.0.0.1:15173');
  await page.getByRole('navigation').getByRole('button', { name: 'Tổng quan', exact: true }).click();
  await page.getByRole('button', { name: /Đăng nhập tài khoản, mật khẩu và vào trang web/ }).click();
  for (const width of [1440, 1024, 390]) {
    await page.setViewportSize({ width, height: 1000 });
    await page.screenshot({ path: `output/playwright/automation-before-${width}.png`, fullPage: true });
  }
  await page.getByRole('button', { name: 'Đóng', exact: true }).click();
  await page.setViewportSize({ width: 1440, height: 1000 });
  return 'Captured existing task result drawer at 1440/1024/390px.';
}
