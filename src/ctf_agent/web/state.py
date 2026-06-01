"""Shared application state for the web server."""

from __future__ import annotations

import asyncio
from pathlib import Path

import yaml

from ctf_agent.api.client import GZCTFClient
from ctf_agent.config import AppConfig, load_config

CONFIG_PATH = Path("config.yaml")


class AppState:
    """Singleton-ish state container for the FastAPI app."""

    def __init__(self) -> None:
        self.config: AppConfig = load_config(CONFIG_PATH if CONFIG_PATH.exists() else None)
        self._client: GZCTFClient | None = None
        self.tasks: dict[str, dict] = {}
        self.ws_queues: dict[str, list[asyncio.Queue]] = {}

    async def get_client(self) -> GZCTFClient:
        """Get or create the GZCTF API client."""
        if self._client is None:
            self._client = GZCTFClient(self.config.gzctf)
        return self._client

    async def reset_client(self) -> None:
        """Close and reset the API client (e.g. after settings change)."""
        if self._client:
            await self._client.close()
            self._client = None

    def save_config(self) -> None:
        """Persist current config to config.yaml."""
        data = {
            "gzctf": {
                "url": self.config.gzctf.url,
                "username": self.config.gzctf.username,
                "password": self.config.gzctf.password,
                "token": self.config.gzctf.token,
                "team_id": self.config.gzctf.team_id,
            },
            "llm": {
                "provider": self.config.llm.provider,
                "api_key": self.config.llm.api_key,
                "base_url": self.config.llm.base_url,
                "model": self.config.llm.model,
                "temperature": self.config.llm.temperature,
                "max_tokens": self.config.llm.max_tokens,
            },
            "agent": {
                "max_retries": self.config.agent.max_retries,
                "auto_submit": self.config.agent.auto_submit,
                "auto_start_container": self.config.agent.auto_start_container,
                "skip_solved": self.config.agent.skip_solved,
                "categories": self.config.agent.categories,
                "download_dir": self.config.agent.download_dir,
                "max_concurrent": self.config.agent.max_concurrent,
            },
        }
        with open(CONFIG_PATH, "w") as f:
            yaml.dump(data, f, allow_unicode=True, default_flow_style=False)
