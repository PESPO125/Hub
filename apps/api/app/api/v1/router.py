from fastapi import APIRouter

from app.api.v1.endpoints import plugins, settings, system, tasks_files, youtube_dl

api_router = APIRouter()
for module in (system, plugins, tasks_files, settings, youtube_dl):
    api_router.include_router(module.router)
