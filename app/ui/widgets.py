"""مكوّنات واجهة مشتركة بمظهر احترافي."""

from __future__ import annotations

import tkinter as tk
from io import BytesIO
from tkinter import messagebox
from typing import Callable, Optional, Union

import customtkinter as ctk
from PIL import Image, ImageDraw, ImageOps, ImageTk

from app.ui import theme as T


def show_error(title: str, message: str) -> None:
    messagebox.showerror(title, message)


def show_info(title: str, message: str) -> None:
    messagebox.showinfo(title, message)


def ask_yes_no(title: str, message: str) -> bool:
    return bool(messagebox.askyesno(title, message))


def make_document_thumbnail(
    image_bytes: bytes,
    width: int = 168,
    height: int = 230,
) -> Image.Image:
    """معاينة مستند واضحة بنسبة عمودية مع خلفية ورقية وإطار."""
    with Image.open(BytesIO(image_bytes)) as src:
        src = ImageOps.exif_transpose(src)
        if src.mode not in ("RGB", "L"):
            src = src.convert("RGB")
        elif src.mode == "L":
            src = src.convert("RGB")

        # ورقة بيضاء بحجم البطاقة
        canvas = Image.new("RGB", (width, height), "#F4F7FA")
        # هامش داخلي لإطار المستند
        pad = 10
        inner_w = width - pad * 2
        inner_h = height - pad * 2 - 8
        page = ImageOps.contain(src, (inner_w, inner_h), Image.Resampling.LANCZOS)

        # ظل بسيط
        shadow = Image.new("RGB", (page.width + 4, page.height + 4), "#D5DEE7")
        sx = (width - shadow.width) // 2 + 1
        sy = pad + 2
        canvas.paste(shadow, (sx, sy))

        px = (width - page.width) // 2
        py = pad
        canvas.paste(page, (px, py))

        draw = ImageDraw.Draw(canvas)
        draw.rectangle(
            [px - 1, py - 1, px + page.width, py + page.height],
            outline="#C5D0DA",
            width=1,
        )
        return canvas


class AppCard(ctk.CTkFrame):
    def __init__(self, master, **kwargs):
        super().__init__(
            master,
            fg_color=T.SURFACE,
            corner_radius=18,
            border_width=1,
            border_color=T.BORDER,
            **kwargs,
        )


class SectionTitle(ctk.CTkFrame):
    def __init__(self, master, title: str, subtitle: str = "", **kwargs):
        super().__init__(master, fg_color="transparent", **kwargs)
        ctk.CTkLabel(
            self,
            text=title,
            font=T.font(18, "bold"),
            text_color=T.TEXT,
            anchor="e",
        ).pack(fill="x")
        if subtitle:
            ctk.CTkLabel(
                self,
                text=subtitle,
                font=T.font(12),
                text_color=T.TEXT_MUTED,
                anchor="e",
            ).pack(fill="x", pady=(2, 0))


class PrimaryButton(ctk.CTkButton):
    def __init__(self, master, text: str, command=None, width: int = 140, **kwargs):
        super().__init__(
            master,
            text=text,
            command=command,
            width=width,
            height=40,
            corner_radius=12,
            fg_color=T.PRIMARY,
            hover_color=T.PRIMARY_HOVER,
            text_color="#FFFFFF",
            font=T.font(13, "bold"),
            **kwargs,
        )


class AccentButton(ctk.CTkButton):
    def __init__(self, master, text: str, command=None, width: int = 140, **kwargs):
        super().__init__(
            master,
            text=text,
            command=command,
            width=width,
            height=40,
            corner_radius=12,
            fg_color=T.ACCENT,
            hover_color=T.ACCENT_HOVER,
            text_color="#FFFFFF",
            font=T.font(13, "bold"),
            **kwargs,
        )


class GhostButton(ctk.CTkButton):
    def __init__(self, master, text: str, command=None, width: int = 120, **kwargs):
        super().__init__(
            master,
            text=text,
            command=command,
            width=width,
            height=40,
            corner_radius=12,
            fg_color=T.SURFACE_2,
            hover_color=T.BORDER,
            text_color=T.TEXT,
            border_width=1,
            border_color=T.BORDER,
            font=T.font(13),
            **kwargs,
        )


class DangerButton(ctk.CTkButton):
    def __init__(self, master, text: str, command=None, width: int = 100, **kwargs):
        super().__init__(
            master,
            text=text,
            command=command,
            width=width,
            height=36,
            corner_radius=10,
            fg_color=T.DANGER,
            hover_color=T.DANGER_HOVER,
            text_color="#FFFFFF",
            font=T.font(12, "bold"),
            **kwargs,
        )


class StatusBadge(ctk.CTkLabel):
    def __init__(self, master, text: str, kind: str = "muted", **kwargs):
        colors = {
            "ok": (T.SUCCESS, "#E8F7EF"),
            "bad": (T.DANGER, "#FCEBEA"),
            "warn": (T.WARNING, "#FEF4E6"),
            "muted": (T.TEXT_MUTED, T.SURFACE_2),
            "info": (T.PRIMARY, T.PRIMARY_SOFT),
        }
        fg, bg = colors.get(kind, colors["muted"])
        super().__init__(
            master,
            text=f"  {text}  ",
            text_color=fg,
            fg_color=bg,
            corner_radius=999,
            font=T.font(12, "bold"),
            **kwargs,
        )

    def set_status(self, text: str, kind: str = "muted") -> None:
        colors = {
            "ok": (T.SUCCESS, "#E8F7EF"),
            "bad": (T.DANGER, "#FCEBEA"),
            "warn": (T.WARNING, "#FEF4E6"),
            "muted": (T.TEXT_MUTED, T.SURFACE_2),
            "info": (T.PRIMARY, T.PRIMARY_SOFT),
        }
        fg, bg = colors.get(kind, colors["muted"])
        self.configure(text=f"  {text}  ", text_color=fg, fg_color=bg)


class LabeledEntry(ctk.CTkFrame):
    def __init__(
        self,
        master,
        label: str,
        placeholder: str = "",
        show: Optional[str] = None,
        height: int = 42,
        **kwargs,
    ):
        super().__init__(master, fg_color="transparent", **kwargs)
        self.label = ctk.CTkLabel(
            self,
            text=label,
            anchor="e",
            font=T.font(12, "bold"),
            text_color=T.TEXT_MUTED,
        )
        self.label.pack(fill="x", pady=(0, 6))
        self.entry = ctk.CTkEntry(
            self,
            placeholder_text=placeholder,
            justify="right",
            height=height,
            corner_radius=12,
            border_width=1,
            border_color=T.BORDER,
            fg_color=T.SURFACE,
            text_color=T.TEXT,
            font=T.font(13),
        )
        if show is not None:
            self.entry.configure(show=show)
        self.entry.pack(fill="x")

    def get(self) -> str:
        return self.entry.get().strip()

    def set(self, value: str) -> None:
        self.entry.delete(0, "end")
        self.entry.insert(0, value or "")

    def bind_return(self, callback: Callable) -> None:
        self.entry.bind("<Return>", lambda _e: callback())


class InfoChip(ctk.CTkFrame):
    def __init__(self, master, label: str, value: str = "—", **kwargs):
        super().__init__(
            master,
            fg_color=T.SURFACE_2,
            corner_radius=14,
            border_width=1,
            border_color=T.BORDER,
            **kwargs,
        )
        ctk.CTkLabel(
            self,
            text=label,
            font=T.font(11),
            text_color=T.TEXT_MUTED,
            anchor="e",
        ).pack(fill="x", padx=14, pady=(10, 0))
        self.value_label = ctk.CTkLabel(
            self,
            text=value or "—",
            font=T.font(14, "bold"),
            text_color=T.TEXT,
            anchor="e",
        )
        self.value_label.pack(fill="x", padx=14, pady=(2, 12))

    def set_value(self, value: str) -> None:
        self.value_label.configure(text=value or "—")


class EditArchiveDialog(ctk.CTkToplevel):
    def __init__(self, master, book_type: str, book_number: str, on_save: Callable):
        super().__init__(master)
        self.title("تعديل الكتاب")
        self.geometry("460x320")
        self.resizable(False, False)
        self.configure(fg_color=T.BG)
        self._on_save = on_save

        card = AppCard(self)
        card.pack(fill="both", expand=True, padx=18, pady=18)

        SectionTitle(card, "تعديل بيانات الكتاب", "حدّث نوع الكتاب والعدد ثم احفظ").pack(
            fill="x", padx=20, pady=(18, 10)
        )

        self.type_entry = LabeledEntry(card, "نوع الكتاب")
        self.type_entry.pack(fill="x", padx=20, pady=6)
        self.type_entry.set(book_type or "")

        self.number_entry = LabeledEntry(card, "العدد")
        self.number_entry.pack(fill="x", padx=20, pady=6)
        self.number_entry.set(book_number or "")

        btns = ctk.CTkFrame(card, fg_color="transparent")
        btns.pack(fill="x", padx=20, pady=18)
        PrimaryButton(btns, "حفظ التعديل", command=self._save, width=140).pack(
            side="right", padx=6
        )
        GhostButton(btns, "إلغاء", command=self.destroy, width=110).pack(
            side="right", padx=6
        )

        self.transient(master)
        self.grab_set()

    def _save(self) -> None:
        book_type = self.type_entry.get()
        book_number = self.number_entry.get()
        if not book_type or not book_number:
            show_error("تنبيه", "الرجاء تعبئة نوع الكتاب والعدد")
            return
        self._on_save(book_type, book_number)
        self.destroy()


class ImagePreviewDialog(ctk.CTkToplevel):
    """عارض مستند واضح مع تكبير وتدوير."""

    def __init__(
        self,
        master,
        title: str,
        image_path_or_bytes: Union[str, bytes],
        is_bytes: bool = False,
    ):
        super().__init__(master)
        self.title(title)
        self.geometry("980x780")
        self.minsize(720, 560)
        self.configure(fg_color=T.BG)
        self._photos = []
        self._scale = 1.0
        self._rotation = 0
        self._source: Optional[Image.Image] = None

        try:
            if is_bytes:
                img = Image.open(BytesIO(image_path_or_bytes))
            else:
                img = Image.open(image_path_or_bytes)
            img = ImageOps.exif_transpose(img)
            if img.mode != "RGB":
                img = img.convert("RGB")
            self._source = img
        except Exception as exc:
            ctk.CTkLabel(self, text=f"تعذر عرض المستند: {exc}").pack(pady=40)
            PrimaryButton(self, "إغلاق", command=self.destroy, width=120).pack(pady=12)
            self.transient(master)
            self.grab_set()
            return

        toolbar = ctk.CTkFrame(self, fg_color=T.SURFACE, corner_radius=0)
        toolbar.pack(fill="x")
        GhostButton(toolbar, "تكبير +", command=self._zoom_in, width=90).pack(
            side="right", padx=6, pady=10
        )
        GhostButton(toolbar, "تصغير −", command=self._zoom_out, width=90).pack(
            side="right", padx=6, pady=10
        )
        GhostButton(toolbar, "تدوير", command=self._rotate, width=90).pack(
            side="right", padx=6, pady=10
        )
        GhostButton(toolbar, "ملاءمة", command=self._fit, width=90).pack(
            side="right", padx=6, pady=10
        )
        PrimaryButton(toolbar, "إغلاق", command=self.destroy, width=100).pack(
            side="left", padx=10, pady=10
        )
        ctk.CTkLabel(
            toolbar,
            text=title,
            font=T.font(14, "bold"),
            text_color=T.TEXT,
        ).pack(side="left", padx=8)

        wrap = AppCard(self)
        wrap.pack(fill="both", expand=True, padx=14, pady=14)

        self.canvas = tk.Canvas(
            wrap,
            background="#E8EEF2",
            highlightthickness=0,
        )
        yscroll = tk.Scrollbar(wrap, orient="vertical", command=self.canvas.yview)
        xscroll = tk.Scrollbar(wrap, orient="horizontal", command=self.canvas.xview)
        self.canvas.configure(yscrollcommand=yscroll.set, xscrollcommand=xscroll.set)
        yscroll.pack(side="left", fill="y")
        xscroll.pack(side="bottom", fill="x")
        self.canvas.pack(side="right", fill="both", expand=True, padx=8, pady=8)

        self.canvas.bind("<Configure>", lambda _e: self._render())
        self.canvas.bind("<MouseWheel>", self._on_wheel)
        self.after(80, self._fit)

        self.transient(master)
        self.grab_set()

    def _on_wheel(self, event) -> None:
        if event.delta > 0:
            self._zoom_in()
        else:
            self._zoom_out()

    def _zoom_in(self) -> None:
        self._scale = min(4.0, self._scale + 0.15)
        self._render()

    def _zoom_out(self) -> None:
        self._scale = max(0.25, self._scale - 0.15)
        self._render()

    def _rotate(self) -> None:
        self._rotation = (self._rotation + 90) % 360
        self._render()

    def _fit(self) -> None:
        if self._source is None:
            return
        self.update_idletasks()
        cw = max(self.canvas.winfo_width() - 40, 200)
        ch = max(self.canvas.winfo_height() - 40, 200)
        img = self._source.rotate(-self._rotation, expand=True)
        sw, sh = img.size
        self._scale = min(cw / sw, ch / sh, 1.5)
        self._render()

    def _render(self) -> None:
        if self._source is None:
            return
        img = self._source.rotate(-self._rotation, expand=True)
        w = max(1, int(img.width * self._scale))
        h = max(1, int(img.height * self._scale))
        resized = img.resize((w, h), Image.Resampling.LANCZOS)

        # خلفية ورق مع هامش
        paper_w, paper_h = w + 48, h + 48
        paper = Image.new("RGB", (paper_w, paper_h), "#FFFFFF")
        paper.paste(resized, (24, 24))
        draw = ImageDraw.Draw(paper)
        draw.rectangle([12, 12, paper_w - 13, paper_h - 13], outline="#C9D5DE", width=1)

        photo = ImageTk.PhotoImage(paper)
        self._photos = [photo]
        self.canvas.delete("all")
        self.canvas.create_image(20, 20, anchor="nw", image=photo)
        self.canvas.configure(scrollregion=(0, 0, paper_w + 40, paper_h + 40))
