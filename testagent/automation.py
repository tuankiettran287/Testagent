from __future__ import annotations

import re
from urllib.parse import urljoin, urlparse

from .schemas import Automation


def checked_url(base_url: str, requested: str) -> str:
    base = urlparse(base_url)
    if base.scheme not in {"http", "https"} or not base.hostname:
        raise ValueError("Project base_url must be an HTTP(S) URL before execution")
    result = urlparse(urljoin(base_url.rstrip("/") + "/", requested))
    if (result.scheme, result.hostname, result.port) != (base.scheme, base.hostname, base.port):
        raise ValueError("Browser and API actions must remain on the project origin")
    return result.geturl()


def validate_automation(automation: Automation, base_url: str) -> None:
    for action in automation.actions:
        if action.action in {"navigate", "assert_url"}:
            checked_url(base_url, action.url or "")
        if action.target:
            for target in (action.target, action.target.scope):
                if target and target.css and re.search(r":has\(|xpath=|^\s*//|^\s*\./", target.css, re.I):
                    raise ValueError("Complex CSS and XPath selectors require review")

