"""شاشة تسجيل الدخول بمظهر احترافي."""

from __future__ import annotations

import threading
from typing import Callable

import customtkinter as ctk

from app.api.client import ApiClient, ApiError
from app.config import APP_NAME, APP_VERSION
from app.ui import theme as T
from app.ui.widgets import AppCard, LabeledEntry, PrimaryButton, show_error
from app.utils.session import SessionData, save_session


class LoginFrame(ctk.CTkFrame):
    def __init__(
        self,
        master,
        api: ApiClient,
        on_success: Callable[[SessionData], None],
        **kwargs,
    ):
        super().__init__(master, fg_color=T.BG, **kwargs)
        self.api = api
        self.on_success = on_success
        self._busy = False

        shell = ctk.CTkFrame(self, fg_color="transparent")
        shell.place(relx=0.5, rely=0.5, anchor="center", relwidth=0.92, relheight=0.86)

        # لوحة العلامة
        brand = ctk.CTkFrame(
            shell,
            fg_color=T.PRIMARY,
            corner_radius=22,
        )
        brand.pack(side="right", fill="both", expand=True, padx=(10, 0))

        brand_inner = ctk.CTkFrame(brand, fg_color="transparent")
        brand_inner.place(relx=0.5, rely=0.5, anchor="center")

        ctk.CTkLabel(
            brand_inner,
            text="المكتبة",
            font=T.font(42, "bold"),
            text_color="#FFFFFF",
        ).pack(anchor="e")
        ctk.CTkLabel(
            brand_inner,
            text="نظام أرشفة الوثائق الطبية",
            font=T.font(16),
            text_color="#D7EBEF",
        ).pack(anchor="e", pady=(8, 0))
        ctk.CTkLabel(
            brand_inner,
            text="مديرية الخدمات الصحية",
            font=T.font(13),
            text_color="#A9CBD4",
        ).pack(anchor="e", pady=(18, 0))

        # بطاقة الدخول
        form_wrap = ctk.CTkFrame(shell, fg_color="transparent")
        form_wrap.pack(side="left", fill="both", expand=True, padx=(0, 10))

        card = AppCard(form_wrap)
        card.place(relx=0.5, rely=0.5, anchor="center", relwidth=0.86)

        ctk.CTkLabel(
            card,
            text=APP_NAME,
            font=T.font(22, "bold"),
            text_color=T.TEXT,
            anchor="e",
        ).pack(fill="x", padx=36, pady=(34, 4))
        ctk.CTkLabel(
            card,
            text="سجّل الدخول للمتابعة إلى الأرشيف",
            font=T.font(13),
            text_color=T.TEXT_MUTED,
            anchor="e",
        ).pack(fill="x", padx=36, pady=(0, 18))

        self.username = LabeledEntry(card, "اسم المستخدم", placeholder="أدخل اسم المستخدم")
        self.username.pack(fill="x", padx=36, pady=8)
        self.password = LabeledEntry(
            card, "كلمة المرور", placeholder="••••••••", show="*"
        )
        self.password.pack(fill="x", padx=36, pady=8)
        self.username.bind_return(self._login)
        self.password.bind_return(self._login)

        self.status = ctk.CTkLabel(
            card, text="", text_color=T.DANGER, font=T.font(12), anchor="e"
        )
        self.status.pack(fill="x", padx=36, pady=(8, 0))

        self.login_btn = PrimaryButton(
            card, "تسجيل الدخول", command=self._login, width=240
        )
        self.login_btn.pack(pady=(16, 10))

        ctk.CTkLabel(
            card,
            text=f"الإصدار {APP_VERSION}",
            font=T.font(11),
            text_color=T.TEXT_MUTED,
        ).pack(pady=(0, 28))

    def _login(self) -> None:
        if self._busy:
            return
        username = self.username.get()
        password = self.password.get()
        if not username or not password:
            self.status.configure(text="أدخل اسم المستخدم وكلمة المرور")
            return

        self._busy = True
        self.login_btn.configure(state="disabled", text="جاري التحقق...")
        self.status.configure(text="")

        def worker():
            try:
                data = self.api.login(username, password)
                session = SessionData(
                    token=data["token"],
                    role=str(data.get("role") or ""),
                    name=str(data.get("name") or ""),
                    permissions=str(data.get("permissions") or ""),
                )
                save_session(session)
                self.after(0, lambda s=session: self._done_ok(s))
            except ApiError as exc:
                err = exc.message
                self.after(0, lambda e=err: self._done_err(e))
            except Exception as exc:
                err = str(exc)
                self.after(0, lambda e=err: self._done_err(e))

        threading.Thread(target=worker, daemon=True).start()

    def _done_ok(self, session: SessionData) -> None:
        self._busy = False
        self.login_btn.configure(state="normal", text="تسجيل الدخول")
        self.on_success(session)

    def _done_err(self, message: str) -> None:
        self._busy = False
        self.login_btn.configure(state="normal", text="تسجيل الدخول")
        self.status.configure(text=message or "فشل تسجيل الدخول")
        show_error("فشل الدخول", message or "فشل تسجيل الدخول")
