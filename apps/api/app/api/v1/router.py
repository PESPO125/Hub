from fastapi import APIRouter

from app.api.v1.endpoints import plugins, settings, system, tasks_files

api_router = APIRouter()
for module in (system, plugins, tasks_files, settings):
    api_router.include_router(module.router)
