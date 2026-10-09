from typing import Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.db.session import Preference
from app.modules.plugins.service import audit

router = APIRouter(tags=["settings"])


class SettingsBody(BaseModel):
    theme: Literal["light", "dark", "system"]


def _read(db: Session) -> dict:
    pref = db.get(Preference, "theme")
    return {"theme": pref.value if pref and pref.value in ("light", "dark", "system") else "system"}


@router.get("/settings")
def get_settings_endpoint(db: Session = Depends(get_db)) -> dict:
    return _read(db)


@router.put("/settings")
def put_settings(body: SettingsBody, db: Session = Depends(get_db)) -> dict:
    db.merge(Preference(key="theme", value=body.theme))
    audit(db, "settings.updated", "theme", {"theme": body.theme})
    db.commit()
    return _read(db)
