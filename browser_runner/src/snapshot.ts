import type { Page } from '@playwright/test';
import { locatorExpression, resolveLocator } from './locators.js';
import type { LocatorTarget } from './protocol.js';

export async function captureSnapshot(page: Page, httpStatus?: number | null) {
  const elements = await page.locator('input, textarea, select, button, a, h1, h2, h3, [role], [data-testid], [data-test], [data-qa]').evaluateAll(nodes =>
    nodes.filter(element => element.getClientRects().length > 0 && getComputedStyle(element).visibility !== 'hidden').slice(0, 100).map(element => {
      const control = element as HTMLInputElement;
      const tag = element.tagName.toLowerCase();
      const type = element.getAttribute('type');
      const text = ((element as HTMLElement).innerText || '').trim().slice(0, 120);
      const label = control.labels?.item(0)?.textContent?.trim().slice(0, 120) || element.getAttribute('aria-label');
      const role = element.getAttribute('role') || (tag === 'button' || (tag === 'input' && ['submit', 'button'].includes(type || '')) ? 'button'
        : tag === 'a' && element.hasAttribute('href') ? 'link' : /^h[1-6]$/.test(tag) ? 'heading'
        : tag === 'textarea' || (tag === 'input' && !['password', 'hidden', 'checkbox', 'radio', 'submit', 'button'].includes(type || '')) ? 'textbox'
        : tag === 'input' && ['checkbox', 'radio'].includes(type || '') ? type : tag === 'select' ? 'combobox' : null);
      const testAttribute = ['data-testid', 'data-test', 'data-qa'].find(attribute => element.hasAttribute(attribute));
      return {
        tag, role, name: label || text || (tag === 'input' && role === 'button' ? control.value : ''),
        testid: testAttribute ? element.getAttribute(testAttribute) : null, test_attribute: testAttribute,
        id: element.getAttribute('id'), type, label, placeholder: element.getAttribute('placeholder'), text,
        href: element.getAttribute('href'), visible: true, required: element.hasAttribute('required'),
        disabled: element.hasAttribute('disabled'), pattern: element.getAttribute('pattern'),
        min: element.getAttribute('min'), max: element.getAttribute('max'),
        minlength: element.getAttribute('minlength'), maxlength: element.getAttribute('maxlength'),
      };
    }),
  );
  const resolved = [];
  for (const element of elements) {
    const candidates: LocatorTarget[] = [];
    if (element.testid) candidates.push({ testid: element.testid, test_attribute: element.test_attribute as LocatorTarget['test_attribute'] });
    if (element.role && element.name) candidates.push({ role: element.role, name: element.name });
    if (element.label) candidates.push({ label: element.label });
    if (element.placeholder) candidates.push({ placeholder: element.placeholder });
    if (element.id) candidates.push({ id: element.id });
    if (element.text && element.text.length < 100) candidates.push({ text: element.text });
    let suggested: LocatorTarget | undefined;
    for (const candidate of candidates) {
      if (await resolveLocator(page, candidate).count() === 1) { suggested = candidate; break; }
    }
    resolved.push({ ...element, suggested_target: suggested, locator: suggested ? locatorExpression(suggested) : undefined, match_count: suggested ? 1 : undefined });
  }
  return {
    url: page.url(), title: await page.title(), http_status: httpStatus ?? null,
    text: (await page.locator('body').innerText({ timeout: 5000 })).slice(0, 8000),
    aria_snapshot: (await page.locator('body').ariaSnapshot()).slice(0, 12000), elements: resolved,
  };
}
