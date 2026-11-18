"""ثيم واجهة برنامج المكتبة — هوية مؤسسية هادئة."""

from __future__ import annotations

import customtkinter as ctk

# ألوان أساسية (أزرق بحري + تركواز — بدون بنفسجي/كريمي)
BG = "#EAF0F4"
SURFACE = "#FFFFFF"
SURFACE_2 = "#F5F8FA"
BORDER = "#D3DEE7"
PRIMARY = "#0E5C6B"
PRIMARY_HOVER = "#0A4A56"
PRIMARY_SOFT = "#D7EBEF"
ACCENT = "#1F7A68"
ACCENT_HOVER = "#176355"
TEXT = "#15202B"
TEXT_MUTED = "#5E6E7C"
DANGER = "#B42318"
DANGER_HOVER = "#912018"
WARNING = "#B54708"
SUCCESS = "#16794C"
SHADOW = "#C9D5DE"


def font(size: int = 13, weight: str = "normal") -> ctk.CTkFont:
    # Cairo إن وُجد، وإلا خط النظام
    families = ("Cairo", "Segoe UI", "Tahoma", "Arial")
    family = families[0]
    try:
        return ctk.CTkFont(family=family, size=size, weight=weight)
    except Exception:
        return ctk.CTkFont(size=size, weight=weight)


def apply_app_theme() -> None:
    ctk.set_appearance_mode("light")
    ctk.set_default_color_theme("blue")


def style_treeview(style_name: str = "Almktab.Treeview") -> str:
    from tkinter import ttk

    style = ttk.Style()
    try:
        style.theme_use("clam")
    except Exception:
        pass

    style.configure(
        style_name,
        background=SURFACE,
        foreground=TEXT,
        fieldbackground=SURFACE,
        bordercolor=BORDER,
        lightcolor=BORDER,
        darkcolor=BORDER,
        rowheight=38,
        font=("Segoe UI", 11),
    )
    style.configure(
        f"{style_name}.Heading",
        background=PRIMARY,
        foreground="#FFFFFF",
        relief="flat",
        borderwidth=0,
        font=("Segoe UI", 11, "bold"),
        padding=(8, 10),
    )
    style.map(
        style_name,
        background=[("selected", PRIMARY_SOFT)],
        foreground=[("selected", TEXT)],
    )
    style.map(
        f"{style_name}.Heading",
        background=[("active", PRIMARY_HOVER)],
    )
    return style_name
