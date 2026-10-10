"""Manifiesto de plugin (v1). Fuente de verdad del contrato; el JSON Schema se genera de aquí."""
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.modules.execution.schema import SchemaError, validate_schema

IconName = Literal[
    "wrench", "download", "file-text", "image", "music", "video", "qr-code", "code",
    "sparkles", "folder", "scissors", "file-archive", "terminal", "globe", "puzzle",
]
Permission = Literal["files.read", "files.write", "network.outbound", "process.spawn", "config.read"]
Category = Literal["media", "documents", "images", "developer", "ai", "files", "utilities"]
CONTRACT_VERSIONS_SUPPORTED = (1,)


class ToolDecl(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str = Field(pattern=r"^[a-z][a-z0-9-]{1,47}$")
    name: str = Field(min_length=1, max_length=60)
    description: str = Field(default="", max_length=300)
    params_schema: dict[str, Any] = Field(default_factory=lambda: {"type": "object", "properties": {}, "additionalProperties": False})
    max_concurrency: int = Field(default=1, ge=1, le=16)
    timeout_seconds: int = Field(default=300, ge=1, le=86400)

    @field_validator("params_schema")
    @classmethod
    def _validate_params_schema(cls, value: dict[str, Any]) -> dict[str, Any]:
        try:
            validate_schema(value)
        except SchemaError as exc:
            raise ValueError(str(exc)) from exc
        return value


class Integration(BaseModel):
    model_config = ConfigDict(extra="forbid")
    type: Literal["python_inprocess", "subprocess", "remote_api"]
    entrypoint: str | None = Field(default=None, min_length=1, max_length=255)


class PlatformCompat(BaseModel):
    model_config = ConfigDict(extra="forbid")
    min_version: str = Field(default="1.0", pattern=r"^\d+\.\d+$")
    max_version: str | None = Field(default=None, pattern=r"^\d+\.\d+$")


class PluginManifest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str = Field(pattern=r"^[a-z][a-z0-9-]{2,47}$")
    name: str = Field(min_length=1, max_length=60)
    description: str = Field(default="", max_length=400)
    version: str = Field(pattern=r"^\d+\.\d+$")
    contract_version: int = 1
    categories: list[Category] = Field(default_factory=list, max_length=4)
    icon: IconName = "puzzle"
    integration: Integration
    tools: list[ToolDecl] = Field(default_factory=list, max_length=20)
    capabilities: list[str] = Field(default_factory=list, max_length=20)
    permissions: list[Permission] = Field(default_factory=list)
    config_requirements: list[str] = Field(default_factory=list, max_length=20)
    platform: PlatformCompat = Field(default_factory=PlatformCompat)
