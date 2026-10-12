import type { Locator, Page } from '@playwright/test';
import type { LocatorTarget } from './protocol.js';

function cssString(value: string): string {
  return [...value].map(char => {
    const code = char.codePointAt(0)!;
    return code < 32 || code === 34 || code === 92 || code === 127
      ? `\\${code.toString(16)} ` : char;
  }).join('');
}

function idSelector(id: string): string {
  return `[id="${cssString(id)}"]`;
}

export function resolveLocator(page: Page, target: LocatorTarget): Locator {
  const root = target.scope ? resolveLocator(page, target.scope) : page;
  const exact = target.exact ?? true;
  if (target.testid) return target.test_attribute && target.test_attribute !== 'data-testid'
    ? root.locator(`[${target.test_attribute}="${cssString(target.testid)}"]`) : root.getByTestId(target.testid);
  if (target.role) {
    const role = target.role as Parameters<Page['getByRole']>[0];
    return target.name ? root.getByRole(role, { name: target.name, exact }) : root.getByRole(role);
  }
  if (target.label) return root.getByLabel(target.label, { exact });
  if (target.placeholder) return root.getByPlaceholder(target.placeholder, { exact });
  if (target.id) return root.locator(idSelector(target.id));
  if (target.text) return root.getByText(target.text, { exact });
  return root.locator(target.css!);
}

export function locatorExpression(target: LocatorTarget): string {
  const quoted = (value: string) => JSON.stringify(value);
  const root = target.scope ? locatorExpression(target.scope) : 'page';
  const exact = target.exact ?? true;
  if (target.testid) return target.test_attribute && target.test_attribute !== 'data-testid'
    ? `${root}.locator(${quoted(`[${target.test_attribute}="${cssString(target.testid)}"]`)})`
    : `${root}.getByTestId(${quoted(target.testid)})`;
  if (target.role) {
    const options = target.name ? `, { name: ${quoted(target.name)}, exact: ${exact} }` : '';
    return `${root}.getByRole(${quoted(target.role)}${options})`;
  }
  if (target.label) return `${root}.getByLabel(${quoted(target.label)}, { exact: ${exact} })`;
  if (target.placeholder) return `${root}.getByPlaceholder(${quoted(target.placeholder)}, { exact: ${exact} })`;
  if (target.id) return `${root}.locator(${quoted(idSelector(target.id))})`;
  if (target.text) return `${root}.getByText(${quoted(target.text)}, { exact: ${exact} })`;
  return `${root}.locator(${quoted(target.css!)})`;
}
