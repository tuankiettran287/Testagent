# Final automation examples

These two fictional GeneratedPlan examples illustrate supported payloads only. They are loaded in final generation, not live exploration. Accounts, URLs, labels, targets and expectations must come from current task evidence. Never copy example values into a different site.

## Independent successful and rejected login

Assume an authorized fixture supplies the account below, observed controls/destination, and a stated invalid-login rule. Each test owns navigation and login; neither consumes the other's session.

```json
{
  "intent": "ui_automation",
  "summary": "Two independent login cases from a known fixture and observed outcomes.",
  "risks": [],
  "cases": [
    {
      "title": "Authorized account reaches its account page",
      "level": "e2e", "type": "positive", "priority": "high",
      "preconditions": ["The supplied fixture account is active."],
      "steps": ["Open login.", "Submit known credentials.", "Verify the account destination."],
      "expected": ["The account page shows the signed-in account heading."],
      "source_ids": [],
      "automation": {"actions": [
        {"action": "navigate", "url": "/login"},
        {"action": "fill", "target": {"testid": "username", "test_attribute": "data-test"}, "value": "example_account"},
        {"action": "fill", "target": {"testid": "password", "test_attribute": "data-test"}, "value": "example_password"},
        {"action": "click", "target": {"role": "button", "name": "Sign in"}},
        {"action": "assert_url", "url": "/account"},
        {"action": "assert_text", "target": {"testid": "account-heading", "test_attribute": "data-test"}, "value": "Account: example_account"}
      ]}
    },
    {
      "title": "An incorrect password is rejected",
      "level": "ui", "type": "negative", "priority": "high",
      "preconditions": ["The stated rule rejects invalid credentials without signing in."],
      "steps": ["Open a fresh login page.", "Submit known username with an intentionally wrong password.", "Verify rejection and login URL."],
      "expected": ["The specified rejection appears and the user remains on login."],
      "source_ids": [],
      "automation": {"actions": [
        {"action": "navigate", "url": "/login"},
        {"action": "fill", "target": {"testid": "username", "test_attribute": "data-test"}, "value": "example_account"},
        {"action": "fill", "target": {"testid": "password", "test_attribute": "data-test"}, "value": "intentionally_wrong_example_password"},
        {"action": "click", "target": {"role": "button", "name": "Sign in"}},
        {"action": "assert_text", "target": {"testid": "login-error", "test_attribute": "data-test"}, "value": "Invalid credentials"},
        {"action": "assert_url", "url": "/login"}
      ]}
    }
  ]
}
```

The error text must be specified or explicitly observation-based. assert_text checks containment; this payload does not prove exact text or absence of a server session. If actual behavior contradicts the intended rule, retain that rule and report the mismatch.

## Repeated controls with an observed scope

Assume the selected product has the unique observed container below and adding it should expose its name in a public cart.

```json
{
  "intent": "ui_automation",
  "summary": "Add the selected fixture product and check its cart entry.",
  "risks": ["An authenticated cart would require known login steps in this case."],
  "cases": [{
    "title": "Add the selected product to a fresh cart",
    "level": "e2e", "type": "positive", "priority": "high",
    "preconditions": ["The fixture has an initially empty public cart."],
    "steps": ["Open products.", "Add the specified product.", "Open cart and check that product."],
    "expected": ["Cart contains Example product."],
    "source_ids": [],
    "automation": {"actions": [
      {"action": "navigate", "url": "/products"},
      {"action": "click", "target": {"role": "button", "name": "Add", "scope": {"testid": "product-example", "test_attribute": "data-qa"}}},
      {"action": "click", "target": {"role": "link", "name": "Cart"}},
      {"action": "assert_url", "url": "/cart"},
      {"action": "assert_text", "target": {"testid": "cart-item-example", "test_attribute": "data-qa"}, "value": "Example product"}
    ]}
  }]
}
```

Both scope and target must identify one observed element. Do not manufacture an attribute or use row position.

## Manual and revised cases

Omit automation for a case needing an unsupported assertion (for example cleared input value). Visibility does not prove emptiness; name the capability gap in risks/preconditions. Missing essential access during exploration instead uses BrowserDecision.blocked_reason.

For selected-case implementation/repair, return exactly one supplied origin_case_id per original. Repair preserves assertion action/value/URL signatures, including repeated checks. No guessed IDs, weakened expectations or PASS claim.
