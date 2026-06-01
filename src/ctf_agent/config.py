"""Configuration management."""

from __future__ import annotations

import os
from pathlib import Path

import yaml
from pydantic import BaseModel, Field


class GZCTFConfig(BaseModel):
    """GZCTF platform configuration."""

    url: str = ""
    username: str = ""
    password: str = ""
    team_id: int | None = None


class LLMConfig(BaseModel):
    """LLM provider configuration."""

    provider: str = "openai"
    api_key: str = ""
    base_url: str | None = None
    model: str = "gpt-4o"
    temperature: float = 0.1
    max_tokens: int = 4096


class AgentConfig(BaseModel):
    """Agent behavior configuration."""

    max_retries: int = 3
    auto_submit: bool = True
    auto_start_container: bool = True
    download_dir: str = "downloads"
    categories: list[str] = Field(default_factory=lambda: ["Misc", "Crypto", "Web", "Forensics", "PPC", "OSINT"])
    skip_solved: bool = True
    max_concurrent: int = 1


class AppConfig(BaseModel):
    """Top-level application config."""

    gzctf: GZCTFConfig = Field(default_factory=GZCTFConfig)
    llm: LLMConfig = Field(default_factory=LLMConfig)
    agent: AgentConfig = Field(default_factory=AgentConfig)


def load_config(config_path: str | Path | None = None) -> AppConfig:
    """Load config from YAML file, with env var overrides."""
    data: dict = {}

    if config_path and Path(config_path).exists():
        with open(config_path) as f:
            data = yaml.safe_load(f) or {}

    config = AppConfig(**data)

    # Environment variable overrides
    if url := os.getenv("GZCTF_URL"):
        config.gzctf.url = url
    if user := os.getenv("GZCTF_USERNAME"):
        config.gzctf.username = user
    if pwd := os.getenv("GZCTF_PASSWORD"):
        config.gzctf.password = pwd
    if team := os.getenv("GZCTF_TEAM_ID"):
        config.gzctf.team_id = int(team)
    if key := os.getenv("LLM_API_KEY"):
        config.llm.api_key = key
    if base := os.getenv("LLM_BASE_URL"):
        config.llm.base_url = base
    if model := os.getenv("LLM_MODEL"):
        config.llm.model = model

    return config
