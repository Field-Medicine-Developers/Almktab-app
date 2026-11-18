#!/usr/bin/env python3
"""واجهة تنصيب وتشغيل برنامج المكتبة — بدون أوامر طرفية."""

from __future__ import annotations

import os
import subprocess
import sys
import threading
from pathlib import Path
from tkinter import (
    BOTH,
    END,
    LEFT,
    RIGHT,
    WORD,
    Frame,
    Label,
    Tk,
    messagebox,
    scrolledtext,
)
from tkinter import Button as TkButton

ROOT = Path(__file__).resolve().parent
VENV_DIR = ROOT / ".venv"
REQUIREMENTS = ROOT / "requirements.txt"
MAIN_PY = ROOT / "main.py"

# نفس هوية التطبيق
BG = "#EAF0F4"
SURFACE = "#FFFFFF"
PRIMARY = "#0E5C6B"
PRIMARY_DARK = "#0A4A56"
ACCENT = "#1F7A68"
TEXT = "#15202B"
MUTED = "#5E6E7C"
BORDER = "#D3DEE7"
DANGER = "#B42318"


def is_windows() -> bool:
    return os.name == "nt"


def ui_font(size: int = 12, bold: bool = False):
    family = "Segoe UI" if is_windows() else "Helvetica Neue"
    return (family, size, "bold" if bold else "normal")


def venv_python() -> Path:
    if is_windows():
        return VENV_DIR / "Scripts" / "python.exe"
    return VENV_DIR / "bin" / "python"


class PillButton(TkButton):
    def __init__(self, master, text, command=None, kind="primary", width=18):
        colors = {
            "primary": (PRIMARY, PRIMARY_DARK, "#FFFFFF"),
            "accent": (ACCENT, "#176355", "#FFFFFF"),
            "ghost": (SURFACE, BORDER, TEXT),
            "danger": (DANGER, "#912018", "#FFFFFF"),
        }
        bg, active, fg = colors.get(kind, colors["primary"])
        super().__init__(
            master,
            text=text,
            command=command,
            width=width,
            height=2,
            relief="flat",
            bd=0,
            bg=bg,
            activebackground=active,
            fg=fg,
            activeforeground=fg,
            font=ui_font(11, True),
            cursor="hand2",
            highlightthickness=1 if kind == "ghost" else 0,
            highlightbackground=BORDER,
        )


class SetupApp:
    def __init__(self) -> None:
        self.root = Tk()
        self.root.title("تنصيب وتشغيل — برنامج المكتبة")
        self.root.geometry("780x560")
        self.root.minsize(700, 500)
        self.root.configure(bg=BG)
        self.busy = False

        # شريط علوي
        top = Frame(self.root, bg=PRIMARY, height=88)
        top.pack(fill="x")
        top.pack_propagate(False)
        Label(
            top,
            text="برنامج المكتبة — الأرشفة",
            bg=PRIMARY,
            fg="#FFFFFF",
            font=ui_font(20, True),
            anchor="e",
        ).pack(fill="x", padx=24, pady=(18, 0))
        Label(
            top,
            text="نصّب المتطلبات وشغّل النظام من واجهة واحدة بدون أوامر",
            bg=PRIMARY,
            fg="#D7EBEF",
            font=ui_font(11),
            anchor="e",
        ).pack(fill="x", padx=24, pady=(4, 0))

        body = Frame(self.root, bg=BG)
        body.pack(fill=BOTH, expand=True, padx=20, pady=16)

        # بطاقة أزرار
        card = Frame(body, bg=SURFACE, highlightbackground=BORDER, highlightthickness=1)
        card.pack(fill="x", pady=(0, 12))

        Label(
            card,
            text="اختر العملية",
            bg=SURFACE,
            fg=TEXT,
            font=ui_font(13, True),
            anchor="e",
        ).pack(fill="x", padx=18, pady=(14, 8))

        btns = Frame(card, bg=SURFACE)
        btns.pack(fill="x", padx=14, pady=(0, 14))

        self.install_btn = PillButton(
            btns, "① تنصيب المتطلبات", command=self.start_install, kind="primary", width=20
        )
        self.install_btn.pack(side=RIGHT, padx=6)

        self.run_btn = PillButton(
            btns, "② تشغيل البرنامج", command=self.start_run, kind="accent", width=18
        )
        self.run_btn.pack(side=RIGHT, padx=6)

        self.both_btn = PillButton(
            btns, "تنصيب ثم تشغيل", command=self.start_install_and_run, kind="ghost", width=16
        )
        self.both_btn.pack(side=LEFT, padx=6)

        self.open_folder_btn = PillButton(
            btns, "فتح المجلد", command=self.open_folder, kind="ghost", width=12
        )
        self.open_folder_btn.pack(side=LEFT, padx=6)

        self.status = Label(
            body,
            text=self._status_text(),
            bg=BG,
            fg=MUTED,
            font=ui_font(10),
            anchor="e",
        )
        self.status.pack(fill="x", pady=(0, 8))

        # سجل
        log_card = Frame(body, bg=SURFACE, highlightbackground=BORDER, highlightthickness=1)
        log_card.pack(fill=BOTH, expand=True)
        Label(
            log_card,
            text="سجل العمليات",
            bg=SURFACE,
            fg=TEXT,
            font=ui_font(12, True),
            anchor="e",
        ).pack(fill="x", padx=14, pady=(12, 4))

        self.log = scrolledtext.ScrolledText(
            log_card,
            wrap=WORD,
            height=16,
            font=("Consolas", 10) if is_windows() else ("Menlo", 11),
            bg="#10242B",
            fg="#E7F2F4",
            insertbackground="#E7F2F4",
            relief="flat",
            borderwidth=0,
        )
        self.log.pack(fill=BOTH, expand=True, padx=12, pady=(0, 12))
        self.log.tag_configure("right", justify="right")

        footer = Frame(self.root, bg=BG)
        footer.pack(fill="x", padx=20, pady=(0, 14))
        PillButton(footer, "إغلاق", command=self.root.destroy, kind="ghost", width=10).pack(
            side=LEFT
        )
        Label(
            footer,
            text="المسح من السكنر متاح على ويندوز فقط",
            bg=BG,
            fg=MUTED,
            font=ui_font(10),
        ).pack(side=RIGHT)

        self._log("جاهز. اضغط «تنصيب المتطلبات» ثم «تشغيل البرنامج».")

    def _status_text(self) -> str:
        py = venv_python()
        if py.exists():
            return f"البيئة جاهزة ✓  —  {py}"
        return "لم يتم التنصيب بعد — ابدأ بـ «تنصيب المتطلبات»"

    def _set_busy(self, busy: bool) -> None:
        self.busy = busy
        state = "disabled" if busy else "normal"
        for btn in (
            self.install_btn,
            self.run_btn,
            self.both_btn,
            self.open_folder_btn,
        ):
            btn.configure(state=state)

    def _log(self, message: str) -> None:
        self.log.insert(END, message + "\n")
        self.log.see(END)
        self.root.update_idletasks()

    def _run_cmd(self, args: list[str]) -> int:
        self._log("$ " + " ".join(str(a) for a in args))
        process = subprocess.Popen(
            args,
            cwd=str(ROOT),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )
        assert process.stdout is not None
        for line in process.stdout:
            line = line.rstrip()
            if line:
                self._log(line)
        return process.wait()

    def start_install(self) -> None:
        if self.busy:
            return
        self._set_busy(True)
        threading.Thread(target=self._install_worker, args=(False,), daemon=True).start()

    def start_install_and_run(self) -> None:
        if self.busy:
            return
        self._set_busy(True)
        threading.Thread(target=self._install_worker, args=(True,), daemon=True).start()

    def _install_worker(self, then_run: bool) -> None:
        try:
            if not MAIN_PY.exists():
                raise RuntimeError("لم يتم العثور على main.py")
            if not REQUIREMENTS.exists():
                raise RuntimeError("لم يتم العثور على requirements.txt")

            self.root.after(0, lambda: self._log("بدء التنصيب..."))
            base_python = sys.executable
            if not VENV_DIR.exists() or not venv_python().exists():
                self.root.after(0, lambda: self._log("إنشاء البيئة الافتراضية (.venv)..."))
                code = self._run_cmd([base_python, "-m", "venv", str(VENV_DIR)])
                if code != 0:
                    raise RuntimeError("فشل إنشاء البيئة الافتراضية")

            py = str(venv_python())
            self.root.after(0, lambda: self._log("تحديث pip..."))
            self._run_cmd([py, "-m", "pip", "install", "--upgrade", "pip"])

            self.root.after(0, lambda: self._log("تثبيت المكتبات..."))
            code = self._run_cmd([py, "-m", "pip", "install", "-r", str(REQUIREMENTS)])
            if code != 0:
                raise RuntimeError("فشل تثبيت المتطلبات")

            check = self._run_cmd(
                [py, "-c", "import customtkinter, httpx, PIL; print('imports-ok')"]
            )
            if check != 0:
                raise RuntimeError(
                    "فشل الاستيراد. على macOS قد تحتاج: brew install python-tk@3.14"
                )

            self.root.after(0, lambda: self.status.configure(text=self._status_text(), fg=ACCENT))
            self.root.after(0, lambda: self._log("تم التنصيب بنجاح."))
            self.root.after(0, lambda: messagebox.showinfo("تم", "تم تنصيب المتطلبات بنجاح"))
            if then_run:
                self.root.after(0, self._launch_app)
            else:
                self.root.after(0, lambda: self._set_busy(False))
        except Exception as exc:
            self.root.after(0, lambda: self._log(f"خطأ: {exc}"))
            self.root.after(0, lambda: messagebox.showerror("فشل التنصيب", str(exc)))
            self.root.after(0, lambda: self._set_busy(False))

    def start_run(self) -> None:
        if self.busy:
            return
        if not venv_python().exists():
            if messagebox.askyesno(
                "غير منصّب",
                "البيئة غير موجودة بعد. هل تريد التنصيب ثم التشغيل؟",
            ):
                self.start_install_and_run()
            return
        self._set_busy(True)
        threading.Thread(target=self._launch_app, daemon=True).start()

    def _launch_app(self) -> None:
        try:
            py = str(venv_python())
            self.root.after(0, lambda: self._log("تشغيل البرنامج..."))
            creationflags = 0
            if is_windows():
                creationflags = getattr(subprocess, "CREATE_NEW_CONSOLE", 0)
            subprocess.Popen([py, str(MAIN_PY)], cwd=str(ROOT), creationflags=creationflags)
            self.root.after(0, lambda: self._log("تم إطلاق البرنامج."))
            self.root.after(0, lambda: self._set_busy(False))
            self.root.after(
                0,
                lambda: messagebox.showinfo(
                    "تشغيل",
                    "تم تشغيل برنامج المكتبة.\nيمكنك إغلاق نافذة التنصيب إن أردت.",
                ),
            )
        except Exception as exc:
            self.root.after(0, lambda: self._log(f"خطأ التشغيل: {exc}"))
            self.root.after(0, lambda: messagebox.showerror("فشل التشغيل", str(exc)))
            self.root.after(0, lambda: self._set_busy(False))

    def open_folder(self) -> None:
        path = str(ROOT)
        if is_windows():
            os.startfile(path)  # type: ignore[attr-defined]
        elif sys.platform == "darwin":
            subprocess.Popen(["open", path])
        else:
            subprocess.Popen(["xdg-open", path])

    def run(self) -> None:
        self.root.mainloop()


def main() -> None:
    try:
        SetupApp().run()
    except Exception as exc:
        print("تعذر فتح واجهة التنصيب:", exc)
        print("على macOS نفّذ: brew install python-tk@3.14")
        raise


if __name__ == "__main__":
    main()
