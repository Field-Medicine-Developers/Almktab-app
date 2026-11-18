"""حفظ واسترجاع جلسة المستخدم محلياً."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from typing import Optional

from app.config import DATA_DIR, SESSION_FILE


@dataclass
class SessionData:
    token: str
    role: str = ""
    name: str = ""
    permissions: str = ""

    @property
    def is_authenticated(self) -> bool:
        return bool(self.token)


def ensure_data_dir() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)


def save_session(session: SessionData) -> None:
    ensure_data_dir()
    SESSION_FILE.write_text(
        json.dumps(asdict(session), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def load_session() -> Optional[SessionData]:
    if not SESSION_FILE.exists():
        return None
    try:
        raw = json.loads(SESSION_FILE.read_text(encoding="utf-8"))
        token = (raw.get("token") or "").strip()
        if not token:
            return None
        return SessionData(
            token=token,
            role=str(raw.get("role") or ""),
            name=str(raw.get("name") or ""),
            permissions=str(raw.get("permissions") or ""),
        )
    except (OSError, json.JSONDecodeError, TypeError, ValueError):
        return None


def clear_session() -> None:
    if SESSION_FILE.exists():
        try:
            SESSION_FILE.unlink()
        except OSError:
            pass
