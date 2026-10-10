import logging
import uuid
from contextlib import asynccontextmanager
from datetime import UTC, datetime

from sqlalchemy import inspect, text
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.router import api_router
from app.core.config import API_VERSION, PLATFORM_VERSION, Settings, get_settings
from app.core.errors import install_error_handlers
from app.db.session import Base, Task, make_engine, make_session_factory
from app.modules.plugins.registry import PluginRegistry
from app.modules.tasks.executor import TaskExecutor

logging.basicConfig(level=logging.INFO, format='{"ts":"%(asctime)s","level":"%(levelname)s","logger":"%(name)s","msg":"%(message)s"}')
log = logging.getLogger("hub")


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        settings.data_dir.mkdir(parents=True, exist_ok=True)
        settings.plugins_dir.mkdir(parents=True, exist_ok=True)
        engine = make_engine(settings.database_url)
        Base.metadata.create_all(engine)  # TODO: reemplazar por migraciones Alembic
        columns = {column["name"] for column in inspect(engine).get_columns("tasks")}
        if "params" not in columns:
            with engine.begin() as connection:
                connection.execute(text("ALTER TABLE tasks ADD COLUMN params JSON NOT NULL DEFAULT '{}'"))
        app.state.engine = engine
        app.state.session_factory = make_session_factory(engine)
        app.state.registry = PluginRegistry(settings.plugins_dir)
        found = app.state.registry.refresh()  # solo lee manifiestos; no ejecuta nada
        log.info("plugins discovered: %d", len(found))
        with app.state.session_factory() as db:
            db.query(Task).filter(Task.status == "running").update(
                {Task.status: "failed", Task.error: {"code": "interrupted_by_restart", "message": "Hub se reinició durante la tarea."},
                 Task.message: "Hub se reinició durante la tarea.", Task.finished_at: datetime.now(UTC)},
                synchronize_session=False,
            )
            db.commit()
        app.state.task_executor = TaskExecutor(app.state.session_factory, app.state.registry, settings)
        app.state.task_executor.resume_pending()
        try:
            yield
        finally:
            app.state.task_executor.shutdown()
            engine.dispose()

    app = FastAPI(title="Hub API", version=PLATFORM_VERSION, lifespan=lifespan,
                  openapi_url=f"/api/{API_VERSION}/openapi.json", docs_url=f"/api/{API_VERSION}/docs")
    app.state.settings = settings
    app.add_middleware(CORSMiddleware, allow_origins=settings.cors_origin_list,
                       allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"], allow_headers=["*"])

    @app.middleware("http")
    async def request_id(request: Request, call_next):
        request.state.request_id = request.headers.get("x-request-id") or uuid.uuid4().hex[:12]
        response = await call_next(request)
        response.headers["x-request-id"] = request.state.request_id
        return response

    install_error_handlers(app)
    app.include_router(api_router, prefix=f"/api/{API_VERSION}")
    return app


app = create_app()
