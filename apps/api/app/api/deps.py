from collections.abc import Iterator

from fastapi import Request
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.modules.plugins.registry import PluginRegistry


def get_db(request: Request) -> Iterator[Session]:
    with request.app.state.session_factory() as session:
        yield session


def get_registry(request: Request) -> PluginRegistry:
    return request.app.state.registry


def get_app_settings(request: Request) -> Settings:
    return request.app.state.settings
