async (page) => {
  await page.unrouteAll({ behavior: 'wait' });
  await page.route('**/api/projects', route => route.fulfill({ json: [{ id: 'optional-context-ui', name: 'Test web không có tài liệu', base_url: 'http://127.0.0.1:15173', environment: 'local', created_at: new Date().toISOString() }] }));
  await page.route('**/api/projects/optional-context-ui/**', route => route.fulfill({ json: new URL(route.request().url()).pathname.endsWith('/coverage') ? { source_count: 0, test_case_count: 0, sources_with_tests: 0, uncovered_sources: [] } : [] }));
  await page.goto('http://127.0.0.1:15173');
  await page.getByRole('navigation').getByRole('button', { name: 'Tổng quan', exact: true }).click();
  await page.getByRole('textbox', { name: 'Yêu cầu của bạn', exact: true }).fill('Tạo UI smoke test cho website, kiểm tra các thành phần đang hiển thị.');
  await page.locator('.sidebar-status').filter({ has: page.getByText('Model AI', { exact: true }) }).getByText('Đã kết nối', { exact: true }).waitFor();
  const disabled = await page.getByRole('button', { name: 'Gửi cho agent', exact: true }).isDisabled();
  for (const width of [1440, 1024, 390]) {
    await page.setViewportSize({ width, height: 1000 });
    await page.screenshot({ path: `output/playwright/optional-sources-before-${width}.png`, fullPage: true, animations: 'disabled' });
  }
  return { sendDisabledWithoutSources: disabled };
}
