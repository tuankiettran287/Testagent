async (page) => {
  const base = 'http://127.0.0.1:15173';
  const ensure = (condition, message) => { if (!condition) throw new Error(message); };
  await page.unrouteAll({ behavior: 'wait' });
  await page.setViewportSize({ width: 1440, height: 1000 });
  await page.goto(base);
  await page.getByRole('button', { name: /Chuyển case đăng nhập đã chọn thành Playwright automation/ }).click();
  const dialog = page.getByRole('dialog');
  await dialog.getByText('Đã tạo test · Chưa chạy xác nhận', { exact: true }).waitFor();
  await dialog.getByRole('button', { name: 'Xem 1 test cases', exact: true }).click();
  const title = 'Đăng nhập bằng tài khoản được công bố trên trang';
  ensure(await page.getByRole('checkbox', { name: `Chọn ${title}`, exact: true }).isChecked(), 'Opening generated cases did not preserve their selection');
  const row = page.getByRole('row').filter({ has: page.getByRole('button', { name: title, exact: true }) });
  ensure(await row.getByText('Playwright · Sẵn sàng', { exact: true }).count() === 1, 'Converted manual case is not ready in the real library');
  await row.getByRole('button', { name: 'PASS', exact: true }).click();
  await dialog.getByRole('heading', { name: 'Kết quả lượt chạy', exact: true }).waitFor();
  ensure(await dialog.getByRole('link', { name: /\.spec\.ts/ }).count() === 2, 'Parallel run did not persist isolated TypeScript artifacts');
  ensure(await dialog.getByRole('link', { name: /trace\.zip/ }).count() === 2, 'Parallel run is missing traces');
  await dialog.getByText('2/2 case hoàn tất · Song song, tối đa 2 case', { exact: true }).waitFor();
  const href = await dialog.getByRole('link', { name: /52c70f49.*\.spec\.ts/ }).getAttribute('href');
  const source = await (await page.request.get(base + href)).text();
  ensure(source.includes('.fill(') && source.includes('.click(') && source.includes('inventory.html') && source.includes('toHaveCount(1'), 'Real test does not preserve the observed journey and unique locators');
  await page.screenshot({ path: 'output/playwright/suite-live-parallel-run.png', fullPage: true });
  await dialog.getByRole('button', { name: 'Đóng', exact: true }).click();
  for (const width of [1440, 1024, 390]) {
    await page.setViewportSize({ width, height: 1000 });
    ensure(!await page.evaluate(() => document.documentElement.scrollWidth > innerWidth), `Live library overflow at ${width}`);
    await page.screenshot({ path: `output/playwright/suite-live-${width}.png`, fullPage: true });
  }
  await page.setViewportSize({ width: 1440, height: 1000 });
  return 'Live native conversion: READY preview, original case ID, selected case highlighting, last PASS, parallel run artifacts, desktop/mobile library verified.';
}
