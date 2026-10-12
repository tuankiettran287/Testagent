export type LocatorTarget = {
  testid?: string;
  role?: string;
  name?: string;
  label?: string;
  id?: string;
  text?: string;
  css?: string;
  placeholder?: string;
  test_attribute?: 'data-testid' | 'data-test' | 'data-qa';
  exact?: boolean;
  scope?: LocatorTarget;
};

export type ActionName =
  | 'navigate' | 'fill' | 'click' | 'check' | 'select'
  | 'assert_visible' | 'assert_text' | 'assert_url';

export type BrowserAction = {
  action: ActionName;
  url?: string;
  target?: LocatorTarget;
  value?: string;
};

export type Automation = { actions: BrowserAction[] };

export type RunnerCommand =
  | { command: 'health' }
  | { command: 'execute'; baseUrl: string; caseId: string; title?: string; artifactDir: string; automation: Automation }
  | { command: 'inspect'; baseUrl: string; path: string }
  | { command: 'compile'; baseUrl: string; title: string; automation: Automation };

const ACTIONS = new Set<ActionName>([
  'navigate', 'fill', 'click', 'check', 'select',
  'assert_visible', 'assert_text', 'assert_url',
]);

function object(value: unknown, field: string): Record<string, unknown> {
  if (!value || typeof value !== 'object' || Array.isArray(value)) {
    throw new Error(`${field} must be an object`);
  }
  return value as Record<string, unknown>;
}

function string(value: unknown, field: string): string {
  if (typeof value !== 'string' || !value.trim()) {
    throw new Error(`${field} must be a non-empty string`);
  }
  return value;
}

function optionalString(value: unknown, field: string): string | undefined {
  if (value === undefined || value === null) return undefined;
  if (typeof value !== 'string') throw new Error(`${field} must be a string`);
  return value;
}

function target(value: unknown, nested = false): LocatorTarget {
  const raw = object(value, 'target');
  const result: LocatorTarget = {};
  for (const key of ['testid', 'role', 'name', 'label', 'id', 'text', 'css', 'placeholder'] as const) {
    const item = optionalString(raw[key], `target.${key}`);
    if (item) result[key] = item;
  }
  if (!['testid', 'role', 'label', 'id', 'text', 'css', 'placeholder'].some(key => result[key as keyof LocatorTarget])) {
    throw new Error('A locator strategy is required');
  }
  if (raw.test_attribute !== undefined) {
    if (!['data-testid', 'data-test', 'data-qa'].includes(String(raw.test_attribute))) throw new Error('Invalid test attribute');
    result.test_attribute = raw.test_attribute as LocatorTarget['test_attribute'];
  }
  if (raw.exact !== undefined) {
    if (typeof raw.exact !== 'boolean') throw new Error('target.exact must be boolean');
    result.exact = raw.exact;
  }
  if (raw.scope !== undefined) {
    if (nested) throw new Error('Only one locator scope is supported');
    result.scope = target(raw.scope, true);
  }
  if (result.css && /:has\(|xpath=|^\s*\/\/|^\s*\.\//i.test(result.css)) {
    throw new Error('Complex CSS and XPath selectors require review');
  }
  return result;
}

export function parseAutomation(value: unknown): Automation {
  const raw = object(value, 'automation');
  if (!Array.isArray(raw.actions) || raw.actions.length < 1 || raw.actions.length > 50) {
    throw new Error('automation.actions must contain 1 to 50 actions');
  }
  return {
    actions: raw.actions.map((item, index) => {
      const action = object(item, `actions[${index}]`);
      const name = string(action.action, `actions[${index}].action`) as ActionName;
      if (!ACTIONS.has(name)) throw new Error(`Unsupported browser action: ${name}`);
      const result: BrowserAction = { action: name };
      if (name === 'navigate' || name === 'assert_url') {
        result.url = string(action.url, `${name}.url`);
      } else {
        result.target = target(action.target);
      }
      if (name === 'fill' || name === 'select' || name === 'assert_text') {
        result.value = optionalString(action.value, `${name}.value`);
        if (result.value === undefined) throw new Error(`${name}.value is required`);
      }
      return result;
    }),
  };
}

export function parseCommand(value: unknown): RunnerCommand {
  const raw = object(value, 'request');
  const command = string(raw.command, 'command');
  if (command === 'health') return { command };
  const baseUrl = string(raw.baseUrl, 'baseUrl');
  if (command === 'execute') {
    const caseId = string(raw.caseId, 'caseId');
    if (!/^[a-zA-Z0-9_-]{1,80}$/.test(caseId)) throw new Error('Invalid caseId');
    return {
      command, baseUrl, caseId, title: optionalString(raw.title, 'title'),
      artifactDir: string(raw.artifactDir, 'artifactDir'),
      automation: parseAutomation(raw.automation),
    };
  }
  if (command === 'inspect') {
    return { command, baseUrl, path: string(raw.path, 'path') };
  }
  if (command === 'compile') {
    return { command, baseUrl, title: string(raw.title, 'title'), automation: parseAutomation(raw.automation) };
  }
  throw new Error(`Unknown browser runner command: ${command}`);
}
