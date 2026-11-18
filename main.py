#!/usr/bin/env python3
"""نقطة تشغيل برنامج المكتبة — أرشفة ويندوز."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import customtkinter as ctk

from app.api.client import ApiClient
from app.config import APP_NAME, APP_VERSION
from app.ui import theme as T
from app.ui.archive_add import ArchiveAddFrame
from app.ui.archive_list import ArchiveListFrame
from app.ui.login_window import LoginFrame
from app.utils.session import SessionData, clear_session, load_session


class AlmktabApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        T.apply_app_theme()

        self.title(f"{APP_NAME} v{APP_VERSION}")
        self.geometry("1240x820")
        self.minsize(1020, 700)
        self.configure(fg_color=T.BG)

        self.api = ApiClient()
        self.session: SessionData | None = None
        self._current = None

        self.container = ctk.CTkFrame(self, fg_color=T.BG, corner_radius=0)
        self.container.pack(fill="both", expand=True)

        self.protocol("WM_DELETE_WINDOW", self._on_close)

        existing = load_session()
        if existing and existing.token:
            self.api.set_token(existing.token)
            self.session = existing
            self.show_list()
        else:
            self.show_login()

    def _clear(self) -> None:
        if self._current is not None:
            self._current.destroy()
            self._current = None
        for child in self.container.winfo_children():
            child.destroy()

    def show_login(self) -> None:
        self._clear()
        self.session = None
        self.api.set_token(None)
        frame = LoginFrame(self.container, api=self.api, on_success=self._on_login)
        frame.pack(fill="both", expand=True)
        self._current = frame

    def _on_login(self, session: SessionData) -> None:
        self.session = session
        self.api.set_token(session.token)
        self.show_list()

    def show_list(self) -> None:
        self._clear()
        name = self.session.name if self.session else ""
        frame = ArchiveListFrame(
            self.container,
            api=self.api,
            user_name=name,
            on_add=self.show_add,
            on_logout=self._logout,
        )
        frame.pack(fill="both", expand=True)
        self._current = frame

    def show_add(self) -> None:
        self._clear()
        frame = ArchiveAddFrame(
            self.container,
            api=self.api,
            on_back=self.show_list,
        )
        frame.pack(fill="both", expand=True)
        self._current = frame

    def _logout(self) -> None:
        clear_session()
        self.show_login()

    def _on_close(self) -> None:
        try:
            self.api.close()
        except Exception:
            pass
        self.destroy()


def _hide_console_window() -> None:
    """إخفاء نافذة CMD إن فُتح البرنامج من طرفية ويندوز."""
    if sys.platform != "win32":
        return
    try:
        import ctypes

        hwnd = ctypes.windll.kernel32.GetConsoleWindow()
        if hwnd:
            ctypes.windll.user32.ShowWindow(hwnd, 0)
            ctypes.windll.kernel32.FreeConsole()
    except Exception:
        pass


def main() -> None:
    _hide_console_window()
    app = AlmktabApp()
    app.mainloop()


if __name__ == "__main__":
    main()
