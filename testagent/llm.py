from __future__ import annotations

from .ai_providers import provider_manager
from .cli_transport import CliError


class ModelUnavailable(RuntimeError):
    pass


def complete_json(system: str, user: str, provider: str | None = None, model: str | None = None, effort: str | None = None) -> dict:
    """Use the signed-in native CLI; there is no API-key or HTTP fallback."""
    try:
        selected = provider_manager.resolve(provider, model, effort)
        return provider_manager.complete(system, user, selected["provider"], selected["model"], selected.get("effort"))
    except (CliError, OSError, ValueError) as exc:
        raise ModelUnavailable(str(exc)) from exc

