from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from dotenv import load_dotenv


load_dotenv()


@dataclass(frozen=True)
class Settings:
    data_dir: Path = Path(os.getenv("DATA_DIR", "./data")).resolve()
    import_root: Path = Path(os.getenv("IMPORT_ROOT", ".")).resolve()
    codex_binary: str = os.getenv("CODEX_BINARY", "codex")
    claude_binary: str = os.getenv("CLAUDE_BINARY", "claude")
    antigravity_binary: str = os.getenv("ANTIGRAVITY_BINARY", "agy")
    ai_timeout: int = int(os.getenv("AI_TIMEOUT_SECONDS", "300"))
    subagent_workers: int = max(1, min(3, int(os.getenv("SUBAGENT_WORKERS", "3"))))
    repository_hosts: tuple[str, ...] = tuple(
        part.strip().lower()
        for part in os.getenv("ALLOWED_REPOSITORY_HOSTS", "github.com,gitlab.com,bitbucket.org").split(",")
        if part.strip()
    )
    allow_production_execution: bool = os.getenv("ALLOW_PRODUCTION_EXECUTION", "false").lower() == "true"
    web_origin: str = os.getenv("WEB_ORIGIN", "http://localhost:5173")
    node_binary: str = os.getenv("NODE_BINARY", "node")
    browser_runner_entry: Path = Path(
        os.getenv(
            "BROWSER_RUNNER_ENTRY",
            str(Path(__file__).resolve().parent.parent / "browser_runner" / "dist" / "cli.js"),
        )
    ).resolve()


settings = Settings()
settings.data_dir.mkdir(parents=True, exist_ok=True)

