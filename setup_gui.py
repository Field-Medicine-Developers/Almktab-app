#!/usr/bin/env python3
"""واجهة تنصيب وتشغيل برنامج المكتبة — بدون أوامر طرفية."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import threading
import urllib.request
import webbrowser
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
DOWNLOADS_DIR = ROOT / "downloads"

# مثبت Python الرسمي لويندوز (64-bit) مع Tcl/Tk
PYTHON_VERSION = "3.12.10"
PYTHON_INSTALLER_NAME = f"python-{PYTHON_VERSION}-amd64.exe"
PYTHON_INSTALLER_URL = (
    f"https://www.python.org/ftp/python/{PYTHON_VERSION}/{PYTHON_INSTALLER_NAME}"
)
PYTHON_DOWNLOAD_PAGE = "https://www.python.org/downloads/windows/"

BG = "#EAF0F4"
SURFACE = "#FFFFFF"
PRIMARY = "#0E5C6B"
PRIMARY_DARK = "#0A4A56"
ACCENT = "#1F7A68"
TEXT = "#15202B"
MUTED = "#5E6E7C"
BORDER = "#D3DEE7"
DANGER = "#B42318"
WARNING = "#B54708"


def is_windows() -> bool:
    return os.name == "nt"


def ui_font(size: int = 12, bold: bool = False):
    family = "Segoe UI" if is_windows() else "Helvetica Neue"
    return (family, size, "bold" if bold else "normal")


def venv_python() -> Path:
    if is_windows():
        return VENV_DIR / "Scripts" / "python.exe"
    return VENV_DIR / "bin" / "python"


def venv_pythonw() -> Path:
    """نسخة بدون نافذة CMD على ويندوز."""
    if is_windows():
        pyw = VENV_DIR / "Scripts" / "pythonw.exe"
        if pyw.exists():
            return pyw
        # بجانب python.exe في نفس المجلد
        py = venv_python()
        sibling = py.with_name("pythonw.exe")
        if sibling.exists():
            return sibling
        return py
    return venv_python()


def hide_console_window() -> None:
    """إخفاء نافذة الكونسول إن ظهرت خلف الواجهة."""
    if not is_windows():
        return
    try:
        import ctypes

        hwnd = ctypes.windll.kernel32.GetConsoleWindow()
        if hwnd:
            ctypes.windll.user32.ShowWindow(hwnd, 0)  # SW_HIDE
            ctypes.windll.kernel32.FreeConsole()
    except Exception:
        pass


def refresh_windows_path() -> None:
    """تحديث PATH للعملية الحالية من إعدادات ويندوز."""
    if not is_windows():
        return
    try:
        import winreg

        paths: list[str] = []
        for root_key, sub in (
            (winreg.HKEY_CURRENT_USER, r"Environment"),
            (
                winreg.HKEY_LOCAL_MACHINE,
                r"SYSTEM\CurrentControlSet\Control\Session Manager\Environment",
            ),
        ):
            try:
                with winreg.OpenKey(root_key, sub) as key:
                    value, _ = winreg.QueryValueEx(key, "Path")
                    if value:
                        paths.append(str(value))
            except OSError:
                continue
        if paths:
            merged = os.pathsep.join(paths)
            # أبقِ مسارات العملية الحالية أيضاً
            current = os.environ.get("PATH", "")
            os.environ["PATH"] = merged + os.pathsep + current
    except Exception:
        pass


def look_for_system_python() -> str | None:
    """يعيد مسار بايثون صالح أو أمر التشغيل."""
    refresh_windows_path()

    venv = venv_python()
    if venv.exists():
        return str(venv)

    candidates: list[list[str]] = []
    if is_windows():
        candidates.append(["py", "-3"])
        local = os.environ.get("LOCALAPPDATA", "")
        if local:
            for ver in ("312", "311", "313", "310"):
                p = Path(local) / "Programs" / "Python" / f"Python{ver}" / "python.exe"
                if p.exists():
                    return str(p)
        pf = os.environ.get("ProgramFiles", r"C:\Program Files")
        for ver in ("312", "311", "313", "310"):
            p = Path(pf) / "Python" / f"Python{ver}" / "python.exe"
            if p.exists():
                return str(p)
            p2 = Path(pf) / f"Python{ver}" / "python.exe"
            if p2.exists():
                return str(p2)

    for cmd in ("python3", "python"):
        path = shutil.which(cmd)
        if path and "WindowsApps" not in path:
            return path
        if path and "WindowsApps" in path:
            # اختصار المتجر — غير موثوق
            continue

    # py launcher
    py = shutil.which("py")
    if py:
        try:
            out = subprocess.check_output(
                [py, "-3", "-c", "import sys; print(sys.executable)"],
                text=True,
                stderr=subprocess.DEVNULL,
                timeout=10,
            ).strip()
            if out and Path(out).exists():
                return out
        except Exception:
            pass

    return None


def python_version_of(executable: str) -> str:
    try:
        out = subprocess.check_output(
            [executable, "-c", "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}')"],
            text=True,
            stderr=subprocess.DEVNULL,
            timeout=10,
        ).strip()
        return out
    except Exception:
        return "?"


class PillButton(TkButton):
    def __init__(self, master, text, command=None, kind="primary", width=18):
        colors = {
            "primary": (PRIMARY, PRIMARY_DARK, "#FFFFFF"),
            "accent": (ACCENT, "#176355", "#FFFFFF"),
            "ghost": (SURFACE, BORDER, TEXT),
            "danger": (DANGER, "#912018", "#FFFFFF"),
            "warn": (WARNING, "#93370D", "#FFFFFF"),
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
        self.root.geometry("860x680")
        self.root.minsize(760, 600)
        self.root.configure(bg=BG)
        self.busy = False
        self.system_python = look_for_system_python()

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
            text="تحميل Python + PATH + تنصيب المتطلبات + التشغيل من واجهة واحدة",
            bg=PRIMARY,
            fg="#D7EBEF",
            font=ui_font(11),
            anchor="e",
        ).pack(fill="x", padx=24, pady=(4, 0))

        body = Frame(self.root, bg=BG)
        body.pack(fill=BOTH, expand=True, padx=20, pady=16)

        # بطاقة Python
        py_card = Frame(body, bg=SURFACE, highlightbackground=BORDER, highlightthickness=1)
        py_card.pack(fill="x", pady=(0, 12))
        Label(
            py_card,
            text="① Python والنظام",
            bg=SURFACE,
            fg=TEXT,
            font=ui_font(13, True),
            anchor="e",
        ).pack(fill="x", padx=18, pady=(14, 4))

        self.python_status = Label(
            py_card,
            text=self._python_status_text(),
            bg=SURFACE,
            fg=MUTED,
            font=ui_font(10),
            anchor="e",
            justify="right",
        )
        self.python_status.pack(fill="x", padx=18, pady=(0, 8))

        py_btns = Frame(py_card, bg=SURFACE)
        py_btns.pack(fill="x", padx=14, pady=(0, 14))

        self.download_py_btn = PillButton(
            py_btns,
            "تحميل Python",
            command=self.start_download_python,
            kind="warn",
            width=16,
        )
        self.download_py_btn.pack(side=RIGHT, padx=6)

        self.install_py_btn = PillButton(
            py_btns,
            "تثبيت Python + PATH",
            command=self.start_install_python,
            kind="primary",
            width=20,
        )
        self.install_py_btn.pack(side=RIGHT, padx=6)

        self.refresh_py_btn = PillButton(
            py_btns,
            "فحص Python",
            command=self.refresh_python_status,
            kind="ghost",
            width=12,
        )
        self.refresh_py_btn.pack(side=LEFT, padx=6)

        self.aliases_btn = PillButton(
            py_btns,
            "إعدادات PATH/Aliases",
            command=self.open_alias_settings,
            kind="ghost",
            width=18,
        )
        self.aliases_btn.pack(side=LEFT, padx=6)

        # بطاقة التطبيق
        card = Frame(body, bg=SURFACE, highlightbackground=BORDER, highlightthickness=1)
        card.pack(fill="x", pady=(0, 12))
        Label(
            card,
            text="② تنصيب وتشغيل البرنامج",
            bg=SURFACE,
            fg=TEXT,
            font=ui_font(13, True),
            anchor="e",
        ).pack(fill="x", padx=18, pady=(14, 8))

        btns = Frame(card, bg=SURFACE)
        btns.pack(fill="x", padx=14, pady=(0, 14))

        self.install_btn = PillButton(
            btns, "تنصيب المتطلبات", command=self.start_install, kind="primary", width=18
        )
        self.install_btn.pack(side=RIGHT, padx=6)

        self.run_btn = PillButton(
            btns, "تشغيل البرنامج", command=self.start_run, kind="accent", width=16
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
            height=14,
            font=("Consolas", 10) if is_windows() else ("Menlo", 11),
            bg="#10242B",
            fg="#E7F2F4",
            insertbackground="#E7F2F4",
            relief="flat",
            borderwidth=0,
        )
        self.log.pack(fill=BOTH, expand=True, padx=12, pady=(0, 12))

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

        self._log("جاهز.")
        if is_windows() and not self.system_python:
            self._log("Python غير موجود. اضغط «تحميل Python» ثم «تثبيت Python + PATH».")
        elif self.system_python:
            self._log(f"تم اكتشاف Python: {self.system_python}")

    def _python_status_text(self) -> str:
        if not is_windows():
            exe = self.system_python or sys.executable
            return f"macOS/Linux — Python الحالي: {exe}"
        if self.system_python:
            ver = python_version_of(self.system_python)
            return f"Python جاهز ✓  |  الإصدار {ver}  |  {self.system_python}"
        return (
            "Python غير موجود أو اختصار Microsoft Store فقط.\n"
            "اضغط «تحميل Python» ثم «تثبيت Python + PATH»."
        )

    def _status_text(self) -> str:
        py = venv_python()
        if py.exists():
            return f"بيئة البرنامج جاهزة ✓  —  {py}"
        return "بعد تجهيز Python: اضغط «تنصيب المتطلبات»"

    def _all_action_buttons(self):
        return (
            self.download_py_btn,
            self.install_py_btn,
            self.refresh_py_btn,
            self.aliases_btn,
            self.install_btn,
            self.run_btn,
            self.both_btn,
            self.open_folder_btn,
        )

    def _set_busy(self, busy: bool) -> None:
        self.busy = busy
        state = "disabled" if busy else "normal"
        for btn in self._all_action_buttons():
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

    def refresh_python_status(self) -> None:
        self.system_python = look_for_system_python()
        color = ACCENT if self.system_python else DANGER
        self.python_status.configure(text=self._python_status_text(), fg=color)
        self.status.configure(text=self._status_text())
        if self.system_python:
            self._log(f"فحص Python: موجود — {self.system_python}")
            messagebox.showinfo("Python", f"تم العثور على Python:\n{self.system_python}")
        else:
            self._log("فحص Python: غير موجود")
            messagebox.showwarning(
                "Python",
                "لم يتم العثور على Python.\nحمّله وثبّته مع PATH من الأزرار أعلاه.",
            )

    def open_alias_settings(self) -> None:
        if is_windows():
            self._log("فتح إعدادات App execution aliases...")
            try:
                subprocess.Popen(
                    [
                        "start",
                        "ms-settings:appsfeatures-app",
                    ],
                    shell=True,
                )
            except Exception:
                webbrowser.open("ms-settings:appsfeatures-app")
            messagebox.showinfo(
                "PATH / Aliases",
                "1) عطّل اختصارات python.exe و python3.exe من App execution aliases.\n"
                "2) ثبّت Python بزر «تثبيت Python + PATH».\n"
                "3) اضغط «فحص Python» بعد انتهاء التثبيت.",
            )
        else:
            webbrowser.open(PYTHON_DOWNLOAD_PAGE)

    def start_download_python(self) -> None:
        if self.busy:
            return
        if not is_windows():
            webbrowser.open(PYTHON_DOWNLOAD_PAGE)
            messagebox.showinfo("تحميل", "تم فتح صفحة تحميل Python.")
            return
        self._set_busy(True)
        threading.Thread(target=self._download_python_worker, daemon=True).start()

    def _installer_path(self) -> Path:
        DOWNLOADS_DIR.mkdir(parents=True, exist_ok=True)
        return DOWNLOADS_DIR / PYTHON_INSTALLER_NAME

    def _download_python_worker(self) -> None:
        try:
            target = self._installer_path()
            if target.exists() and target.stat().st_size > 1_000_000:
                self.root.after(
                    0,
                    lambda: self._log(f"ملف التثبيت موجود مسبقاً: {target}"),
                )
                self.root.after(
                    0,
                    lambda: messagebox.showinfo(
                        "تحميل",
                        f"ملف Python جاهز:\n{target}\n\nاضغط «تثبيت Python + PATH».",
                    ),
                )
                self.root.after(0, lambda: self._set_busy(False))
                return

            self.root.after(0, lambda: self._log(f"تحميل Python من:\n{PYTHON_INSTALLER_URL}"))
            self.root.after(0, lambda: self._log("قد يستغرق دقيقة حسب سرعة الإنترنت..."))

            def _report(block_num, block_size, total_size):
                if total_size <= 0:
                    return
                downloaded = block_num * block_size
                percent = min(100, int(downloaded * 100 / total_size))
                if percent % 10 == 0:
                    self.root.after(
                        0,
                        lambda p=percent: self._log(f"التقدم: {p}%"),
                    )

            urllib.request.urlretrieve(
                PYTHON_INSTALLER_URL, filename=str(target), reporthook=_report
            )
            size_mb = target.stat().st_size / (1024 * 1024)
            self.root.after(0, lambda: self._log(f"اكتمل التحميل ({size_mb:.1f} MB): {target}"))
            self.root.after(
                0,
                lambda: messagebox.showinfo(
                    "تم التحميل",
                    "تم تحميل مثبت Python.\nاضغط الآن «تثبيت Python + PATH».",
                ),
            )
        except Exception as exc:
            self.root.after(0, lambda: self._log(f"فشل التحميل: {exc}"))
            self.root.after(
                0,
                lambda: messagebox.showerror(
                    "فشل التحميل",
                    f"{exc}\n\nيمكنك فتح الصفحة يدوياً:\n{PYTHON_DOWNLOAD_PAGE}",
                ),
            )
            self.root.after(0, lambda: webbrowser.open(PYTHON_DOWNLOAD_PAGE))
        finally:
            self.root.after(0, lambda: self._set_busy(False))

    def start_install_python(self) -> None:
        if self.busy:
            return
        if not is_windows():
            messagebox.showinfo(
                "macOS",
                "على الماك ثبّت Python عبر:\nbrew install python-tk@3.14\nأو من python.org",
            )
            webbrowser.open(PYTHON_DOWNLOAD_PAGE)
            return
        self._set_busy(True)
        threading.Thread(target=self._install_python_worker, daemon=True).start()

    def _install_python_worker(self) -> None:
        try:
            installer = self._installer_path()
            if not installer.exists():
                self.root.after(0, lambda: self._log("المثبت غير موجود — بدء التحميل أولاً..."))
                # تحميل متزامن داخل نفس الثريد
                self._download_python_worker_sync()

            if not installer.exists():
                raise RuntimeError("تعذر تحميل مثبت Python")

            self.root.after(
                0,
                lambda: self._log(
                    "تشغيل المثبت مع تفعيل PATH و Tcl/Tk و pip..."
                ),
            )
            # /passive يظهر شريط تقدم؛ PrependPath يضيف PATH
            args = [
                str(installer),
                "/passive",
                "InstallAllUsers=0",
                "PrependPath=1",
                "Include_launcher=1",
                "Include_pip=1",
                "Include_tcltk=1",
                "Include_test=0",
                "AssociateFiles=1",
                "SimpleInstall=1",
            ]
            self._log("$ " + " ".join(args))
            completed = subprocess.run(args, cwd=str(ROOT))
            if completed.returncode not in (0, 3010):
                raise RuntimeError(
                    f"فشل تثبيت Python (رمز {completed.returncode}). "
                    "جرّب التشغيل كمسؤول أو عطّل antivirus مؤقتاً."
                )

            refresh_windows_path()
            self.system_python = look_for_system_python()
            self.root.after(0, lambda: self.python_status.configure(
                text=self._python_status_text(),
                fg=ACCENT if self.system_python else WARNING,
            ))
            self.root.after(0, lambda: self._log("انتهى تثبيت Python."))
            if self.system_python:
                self.root.after(
                    0,
                    lambda: messagebox.showinfo(
                        "تم",
                        "تم تثبيت Python وإضافته إلى PATH.\n"
                        "اضغط الآن «تنصيب المتطلبات».\n\n"
                        f"{self.system_python}",
                    ),
                )
            else:
                self.root.after(
                    0,
                    lambda: messagebox.showwarning(
                        "تنبيه",
                        "اكتمل المثبت لكن لم يُكتشف Python بعد.\n"
                        "1) عطّل App execution aliases\n"
                        "2) أغلق هذه النافذة وافتح run.bat من جديد\n"
                        "3) أو اضغط «فحص Python»",
                    ),
                )
        except Exception as exc:
            self.root.after(0, lambda: self._log(f"خطأ تثبيت Python: {exc}"))
            self.root.after(0, lambda: messagebox.showerror("فشل التثبيت", str(exc)))
        finally:
            self.root.after(0, lambda: self._set_busy(False))

    def _download_python_worker_sync(self) -> None:
        target = self._installer_path()
        if target.exists() and target.stat().st_size > 1_000_000:
            self._log(f"استخدام المثبت الموجود: {target}")
            return
        self._log(f"تحميل: {PYTHON_INSTALLER_URL}")
        urllib.request.urlretrieve(PYTHON_INSTALLER_URL, filename=str(target))
        self._log(f"تم الحفظ: {target}")

    def _base_python_for_venv(self) -> str:
        found = look_for_system_python()
        if found:
            return found
        # إذا كنا نعمل أصلاً ببايثون صالح
        if "WindowsApps" not in sys.executable:
            return sys.executable
        raise RuntimeError(
            "لا يوجد Python صالح. استخدم «تحميل Python» ثم «تثبيت Python + PATH»."
        )

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

            self.root.after(0, lambda: self._log("بدء تنصيب متطلبات البرنامج..."))
            base_python = self._base_python_for_venv()
            self.root.after(0, lambda: self._log(f"باستخدام: {base_python}"))

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
                    "فشل الاستيراد. تأكد أن تثبيت Python شمل Tcl/Tk "
                    "(زر تثبيت Python + PATH يفعل ذلك)."
                )

            self.root.after(0, lambda: self.status.configure(text=self._status_text(), fg=ACCENT))
            self.root.after(0, lambda: self._log("تم تنصيب متطلبات البرنامج بنجاح."))
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
                "بيئة البرنامج غير موجودة بعد. هل تريد التنصيب ثم التشغيل؟",
            ):
                self.start_install_and_run()
            return
        self._set_busy(True)
        threading.Thread(target=self._launch_app, daemon=True).start()

    def _launch_app(self) -> None:
        try:
            py = str(venv_pythonw())
            self.root.after(0, lambda: self._log("تشغيل البرنامج..."))
            kwargs: dict = {
                "cwd": str(ROOT),
                "close_fds": True,
            }
            if is_windows():
                # بدون نافذة CMD جديدة
                create_no_window = getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)
                detached = getattr(subprocess, "DETACHED_PROCESS", 0x00000008)
                kwargs["creationflags"] = create_no_window | detached
                kwargs["stdout"] = subprocess.DEVNULL
                kwargs["stderr"] = subprocess.DEVNULL
                kwargs["stdin"] = subprocess.DEVNULL
            subprocess.Popen([py, str(MAIN_PY)], **kwargs)
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
    hide_console_window()
    try:
        SetupApp().run()
    except Exception as exc:
        print("تعذر فتح واجهة التنصيب:", exc)
        print("على macOS نفّذ: brew install python-tk@3.14")
        raise


if __name__ == "__main__":
    main()
