from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class AppConfig(BaseModel):
    gateway_host: str = "127.0.0.1"
    gateway_port: int = 8000
    gateway_version: str = "0.1.0"
    log_backends: list[str] = Field(default_factory=lambda: ["jsonl"])
    log_exclude_fields: list[str] = Field(default_factory=list)
    jsonl_path: str = "logs/gen-gateway.jsonl"
    sidecar_enabled: bool = True
    image_output_path: str = "test_image_output"
    static_image_base_url: str = "http://127.0.0.1:8000/images"
    fal_api_base_url: str = "https://queue.fal.run"
    bfl_api_base_url: str = "https://api.bfl.ai/v1"
    bfl_poll_interval_seconds: float = 0.5
    request_timeout_seconds: float = 120.0


class Secrets(BaseSettings):
    model_config = SettingsConfigDict(extra="ignore", populate_by_name=True)

    fal_key: str | None = Field(default=None, alias="FAL_KEY")
    bfl_key: str | None = Field(default=None, alias="BFL_API_KEY")
    database_url: str | None = Field(default=None, alias="DATABASE_URL")


@dataclass(slots=True)
class RuntimeConfig:
    app: AppConfig
    secrets: Secrets
    project_root: Path


def _read_yaml_config(config_path: Path) -> dict[str, Any]:
    if not config_path.exists():
        return {}

    with config_path.open("r", encoding="utf-8") as handle:
        loaded = yaml.safe_load(handle) or {}

    if not isinstance(loaded, dict):
        raise ValueError(f"Expected mapping in {config_path}")

    return loaded


def resolve_path(path_value: str, project_root: Path) -> Path:
    path = Path(path_value).expanduser()
    if path.is_absolute():
        return path
    return (project_root / path).resolve()


def load_runtime_config(
    config_path: str | Path | None = None,
    env_file: str | Path | None = ".env",
) -> RuntimeConfig:
    resolved_config_path = Path(config_path or "config.yaml").resolve()
    project_root = resolved_config_path.parent
    yaml_data = _read_yaml_config(resolved_config_path)
    app_config = AppConfig.model_validate(yaml_data)

    resolved_env_file: str | None
    if env_file is None:
        resolved_env_file = None
    else:
        env_path = Path(env_file)
        if not env_path.is_absolute():
            env_path = (project_root / env_path).resolve()
        resolved_env_file = str(env_path)

    secrets = Secrets(_env_file=resolved_env_file)
    return RuntimeConfig(app=app_config, secrets=secrets, project_root=project_root)
