"""شاشة إضافة أرشيف: بحث جريح + مسح + رفع ملفات."""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from io import BytesIO
from pathlib import Path
from typing import Callable, List, Optional

import customtkinter as ctk
from PIL import Image, ImageTk
from tkinter import filedialog

from app.api.client import ApiClient, ApiError, ArchiveFileItem
from app.config import MAX_REQUEST_BYTES
from app.scanner import twain_scanner
from app.ui import theme as T
from app.ui.widgets import (
    AccentButton,
    AppCard,
    DangerButton,
    GhostButton,
    InfoChip,
    LabeledEntry,
    PrimaryButton,
    SectionTitle,
    StatusBadge,
    show_error,
    show_info,
)
from app.utils.images import compress_image_bytes, load_and_prepare_file


@dataclass
class PendingFile:
    data: bytes
    file_name: str
    mime_type: str
    is_image: bool
    book_type: str = ""
    book_number: str = ""
    preview: Optional[ImageTk.PhotoImage] = field(default=None, repr=False)


class ArchiveAddFrame(ctk.CTkFrame):
    def __init__(
        self,
        master,
        api: ApiClient,
        on_back: Optional[Callable[[], None]] = None,
        **kwargs,
    ):
        super().__init__(master, fg_color=T.BG, **kwargs)
        self.api = api
        self.on_back = on_back
        self.files: List[PendingFile] = []
        self.injury_name = ""
        self.injury_archive_number = ""
        self.injury_statistical_number = ""
        self.devices: List[str] = []
        self._busy = False

        self._build_ui()
        self.after(200, self._refresh_devices)

    def _build_ui(self) -> None:
        bar = ctk.CTkFrame(self, fg_color=T.PRIMARY, corner_radius=0, height=72)
        bar.pack(fill="x")
        bar.pack_propagate(False)
        inner = ctk.CTkFrame(bar, fg_color="transparent")
        inner.pack(fill="both", expand=True, padx=22)

        right = ctk.CTkFrame(inner, fg_color="transparent")
        right.pack(side="right", fill="y")
        ctk.CTkLabel(
            right,
            text="أرشفة الوثائق",
            font=T.font(20, "bold"),
            text_color="#FFFFFF",
        ).pack(anchor="e", pady=(14, 0))
        ctk.CTkLabel(
            right,
            text="مسح مباشر أو رفع ملفات ثم الحفظ على النظام",
            font=T.font(12),
            text_color="#D7EBEF",
        ).pack(anchor="e")

        left = ctk.CTkFrame(inner, fg_color="transparent")
        left.pack(side="left", fill="y", pady=14)
        GhostButton(left, "رجوع للقائمة", command=self._back, width=130).pack(
            side="left", padx=4
        )
        PrimaryButton(left, "رفع ملفات", command=self._pick_files, width=120).pack(
            side="left", padx=4
        )
        self.scan_btn = AccentButton(
            left, "مسح من السكنر", command=self._scan, width=140
        )
        self.scan_btn.pack(side="left", padx=4)
        GhostButton(left, "فحص السكنر", command=self._refresh_devices, width=110).pack(
            side="left", padx=4
        )

        # السكنر
        scanner = AppCard(self)
        scanner.pack(fill="x", padx=20, pady=(16, 8))
        head = ctk.CTkFrame(scanner, fg_color="transparent")
        head.pack(fill="x", padx=16, pady=(14, 6))
        SectionTitle(head, "إعدادات السكنر", "TWAIN — ويندوز فقط للمسح المباشر").pack(
            side="right", fill="x", expand=True
        )
        self.scanner_badge = StatusBadge(head, "غير مفحوص", "muted")
        self.scanner_badge.pack(side="left")

        row = ctk.CTkFrame(scanner, fg_color="transparent")
        row.pack(fill="x", padx=16, pady=(0, 14))

        self.device_var = ctk.StringVar(value="")
        self.dpi_var = ctk.StringVar(value="300")
        self.feeder_var = ctk.BooleanVar(value=True)

        ctk.CTkLabel(row, text="الجهاز", font=T.font(12, "bold"), text_color=T.TEXT_MUTED).pack(
            side="right", padx=(8, 4)
        )
        self.device_menu = ctk.CTkOptionMenu(
            row,
            variable=self.device_var,
            values=["— لا يوجد —"],
            width=240,
            height=38,
            corner_radius=10,
            fg_color=T.SURFACE_2,
            button_color=T.PRIMARY,
            button_hover_color=T.PRIMARY_HOVER,
            text_color=T.TEXT,
        )
        self.device_menu.pack(side="right", padx=4)

        ctk.CTkLabel(row, text="الدقة", font=T.font(12, "bold"), text_color=T.TEXT_MUTED).pack(
            side="right", padx=(16, 4)
        )
        ctk.CTkOptionMenu(
            row,
            variable=self.dpi_var,
            values=["200", "300", "400", "600"],
            width=100,
            height=38,
            corner_radius=10,
            fg_color=T.SURFACE_2,
            button_color=T.PRIMARY,
            button_hover_color=T.PRIMARY_HOVER,
        ).pack(side="right", padx=4)

        ctk.CTkCheckBox(
            row,
            text="التغذية ADF",
            variable=self.feeder_var,
            font=T.font(12),
            text_color=T.TEXT,
            fg_color=T.PRIMARY,
            hover_color=T.PRIMARY_HOVER,
        ).pack(side="right", padx=12)

        self.scanner_status = ctk.CTkLabel(
            row, text="", font=T.font(11), text_color=T.TEXT_MUTED
        )
        self.scanner_status.pack(side="left", padx=8)

        # الجريح
        injury = AppCard(self)
        injury.pack(fill="x", padx=20, pady=8)
        SectionTitle(
            injury, "بيانات الجريح", "ابحث بالاسم أو الرقم الإحصائي قبل الحفظ"
        ).pack(fill="x", padx=16, pady=(14, 8))

        self.injury_info = LabeledEntry(
            injury,
            "الاسم الكامل أو الرقم الإحصائي",
            placeholder="ادخل الاسم أو الرقم ثم اضغط بحث",
        )
        self.injury_info.pack(fill="x", padx=16, pady=(0, 8))
        self.injury_info.bind_return(self._lookup_injury)

        lookup_row = ctk.CTkFrame(injury, fg_color="transparent")
        lookup_row.pack(fill="x", padx=16, pady=(0, 8))
        self.lookup_btn = PrimaryButton(
            lookup_row, "بحث عن الجريح", command=self._lookup_injury, width=150
        )
        self.lookup_btn.pack(side="right")

        chips = ctk.CTkFrame(injury, fg_color="transparent")
        chips.pack(fill="x", padx=12, pady=(0, 14))
        self.name_chip = InfoChip(chips, "الاسم الكامل")
        self.name_chip.pack(side="right", fill="x", expand=True, padx=4)
        self.archive_chip = InfoChip(chips, "الرقم الإحصائي")
        self.archive_chip.pack(side="right", fill="x", expand=True, padx=4)
        self.stat_chip = InfoChip(chips, "الرقم العشوائي")
        self.stat_chip.pack(side="right", fill="x", expand=True, padx=4)

        # الملفات
        files_card = AppCard(self)
        files_card.pack(fill="both", expand=True, padx=20, pady=8)

        files_header = ctk.CTkFrame(files_card, fg_color="transparent")
        files_header.pack(fill="x", padx=16, pady=(14, 6))
        SectionTitle(files_header, "الملفات الممسوحة / المرفوعة").pack(side="right")
        self.files_count = StatusBadge(files_header, "0 ملف", "muted")
        self.files_count.pack(side="left")

        self.files_scroll = ctk.CTkScrollableFrame(
            files_card,
            fg_color=T.SURFACE_2,
            corner_radius=14,
            border_width=1,
            border_color=T.BORDER,
        )
        self.files_scroll.pack(fill="both", expand=True, padx=14, pady=(0, 14))

        footer = ctk.CTkFrame(self, fg_color="transparent")
        footer.pack(fill="x", padx=20, pady=(4, 18))
        self.save_btn = PrimaryButton(
            footer, "حفظ الأرشيف", command=self._save, width=180
        )
        self.save_btn.pack(side="right")
        self.error_label = ctk.CTkLabel(
            footer, text="", text_color=T.DANGER, font=T.font(12), anchor="e"
        )
        self.error_label.pack(side="right", fill="x", expand=True, padx=12)

        self._render_files()

    def _back(self) -> None:
        if self.on_back:
            self.on_back()

    def _set_busy(self, busy: bool, message: str = "") -> None:
        self._busy = busy
        state = "disabled" if busy else "normal"
        self.scan_btn.configure(state=state)
        self.lookup_btn.configure(state=state)
        self.save_btn.configure(state=state, text=message or "حفظ الأرشيف")

    def _refresh_devices(self) -> None:
        self.scanner_badge.set_status("فحص...", "warn")

        def worker():
            try:
                devices = twain_scanner.list_devices()
                names = [d.name for d in devices]
                preferred = twain_scanner.prefer_device_name(devices)
                self.after(0, lambda: self._apply_devices(names, preferred, None))
            except Exception as exc:
                self.after(0, lambda: self._apply_devices([], "", str(exc)))

        threading.Thread(target=worker, daemon=True).start()

    def _apply_devices(
        self, names: List[str], preferred: str, error: Optional[str]
    ) -> None:
        self.devices = names
        if names:
            self.device_menu.configure(values=names)
            self.device_var.set(preferred or names[0])
            self.scanner_badge.set_status(f"جاهز ({len(names)})", "ok")
            self.scanner_status.configure(text=preferred or names[0])
        else:
            self.device_menu.configure(values=["— لا يوجد —"])
            self.device_var.set("— لا يوجد —")
            msg = error or "لا يوجد سكنر"
            self.scanner_badge.set_status("غير متصل", "bad")
            self.scanner_status.configure(text=msg)

    def _lookup_injury(self) -> None:
        info = self.injury_info.get()
        if not info:
            show_error("تنبيه", "أدخل الاسم أو الرقم الإحصائي")
            return
        self._set_busy(True, "جاري البحث...")

        def worker():
            try:
                data = self.api.get_injury(info)
                self.after(0, lambda: self._apply_injury(data))
            except ApiError as exc:
                self.after(0, lambda: self._injury_fail(exc.message))
            except Exception as exc:
                self.after(0, lambda: self._injury_fail(str(exc)))

        threading.Thread(target=worker, daemon=True).start()

    def _apply_injury(self, data) -> None:
        self._set_busy(False)
        if not data:
            self.injury_name = ""
            self.injury_archive_number = ""
            self.injury_statistical_number = ""
            self.name_chip.set_value("—")
            self.archive_chip.set_value("—")
            self.stat_chip.set_value("—")
            show_error("غير موجود", "لم يتم العثور على الجريح")
            return

        self.injury_name = str(data.get("fullName") or "")
        self.injury_archive_number = str(data.get("archiveNumber") or "")
        self.injury_statistical_number = str(data.get("statisticalNumber") or "")
        self.name_chip.set_value(self.injury_name or "—")
        self.archive_chip.set_value(self.injury_archive_number or "—")
        self.stat_chip.set_value(self.injury_statistical_number or "—")

    def _injury_fail(self, message: str) -> None:
        self._set_busy(False)
        show_error("خطأ البحث", message)

    def _scan(self) -> None:
        if self._busy:
            return
        device = self.device_var.get()
        if not device or device.startswith("—"):
            show_error("تنبيه", "اختر سكنراً أولاً أو اضغط فحص السكنر")
            return

        self._set_busy(True, "جاري المسح...")
        self.scan_btn.configure(text="جاري المسح...")
        dpi = int(self.dpi_var.get() or 300)
        use_feeder = bool(self.feeder_var.get())

        def worker():
            try:
                images = twain_scanner.scan(
                    device_name=device,
                    dpi=dpi,
                    use_feeder=use_feeder,
                    show_ui=True,
                )
                prepared = []
                for image in images:
                    data, mime, name = compress_image_bytes(image.data, image.file_name)
                    prepared.append(
                        PendingFile(
                            data=data,
                            file_name=name,
                            mime_type=mime,
                            is_image=True,
                        )
                    )
                self.after(0, lambda: self._after_scan(prepared, None))
            except Exception as exc:
                self.after(0, lambda: self._after_scan([], str(exc)))

        threading.Thread(target=worker, daemon=True).start()

    def _after_scan(self, items: List[PendingFile], error: Optional[str]) -> None:
        self._set_busy(False)
        self.scan_btn.configure(text="مسح من السكنر")
        if error:
            show_error("فشل المسح", error)
            return
        self.files.extend(items)
        self._render_files()
        show_info("تم المسح", f"تمت إضافة {len(items)} صورة")

    def _pick_files(self) -> None:
        paths = filedialog.askopenfilenames(
            title="اختر ملفات الأرشيف",
            filetypes=[
                ("الصور و PDF", "*.jpg *.jpeg *.png *.bmp *.tif *.tiff *.webp *.pdf"),
                ("كل الملفات", "*.*"),
            ],
        )
        if not paths:
            return
        added = 0
        for path_str in paths:
            path = Path(path_str)
            try:
                data, mime, name = load_and_prepare_file(path)
                self.files.append(
                    PendingFile(
                        data=data,
                        file_name=name,
                        mime_type=mime,
                        is_image=mime.startswith("image/"),
                    )
                )
                added += 1
            except Exception as exc:
                show_error("ملف غير صالح", f"{path.name}: {exc}")
        if added:
            self._render_files()

    def _render_files(self) -> None:
        for child in self.files_scroll.winfo_children():
            child.destroy()

        self.files_count.set_status(f"{len(self.files)} ملف", "info" if self.files else "muted")
        if not self.files:
            empty = ctk.CTkFrame(self.files_scroll, fg_color="transparent")
            empty.pack(fill="x", pady=40)
            ctk.CTkLabel(
                empty,
                text="لا توجد ملفات بعد",
                font=T.font(15, "bold"),
                text_color=T.TEXT,
            ).pack()
            ctk.CTkLabel(
                empty,
                text="استخدم المسح من السكنر أو رفع الملفات للبدء",
                font=T.font(12),
                text_color=T.TEXT_MUTED,
            ).pack(pady=(4, 0))
            return

        for index, item in enumerate(self.files):
            card = ctk.CTkFrame(
                self.files_scroll,
                fg_color=T.SURFACE,
                corner_radius=14,
                border_width=1,
                border_color=T.BORDER,
            )
            card.pack(fill="x", pady=6, padx=4)

            left = ctk.CTkFrame(card, fg_color="transparent")
            left.pack(side="left", padx=10, pady=10)
            DangerButton(
                left, "إزالة", command=lambda i=index: self._remove_file(i), width=80
            ).pack()

            meta = ctk.CTkFrame(card, fg_color="transparent")
            meta.pack(side="right", fill="x", expand=True, padx=10, pady=10)

            type_entry = ctk.CTkEntry(
                meta,
                placeholder_text="نوع الكتاب",
                justify="right",
                height=36,
                corner_radius=10,
                border_color=T.BORDER,
            )
            type_entry.pack(fill="x", pady=2)
            type_entry.insert(0, item.book_type)
            number_entry = ctk.CTkEntry(
                meta,
                placeholder_text="العدد",
                justify="right",
                height=36,
                corner_radius=10,
                border_color=T.BORDER,
            )
            number_entry.pack(fill="x", pady=2)
            number_entry.insert(0, item.book_number)

            def bind_type(event, i=index, entry=type_entry):
                self.files[i].book_type = entry.get().strip()

            def bind_number(event, i=index, entry=number_entry):
                self.files[i].book_number = entry.get().strip()

            type_entry.bind("<KeyRelease>", bind_type)
            number_entry.bind("<KeyRelease>", bind_number)
            type_entry.bind("<FocusOut>", bind_type)
            number_entry.bind("<FocusOut>", bind_number)

            ctk.CTkLabel(
                meta,
                text=item.file_name,
                font=T.font(11),
                text_color=T.TEXT_MUTED,
                anchor="e",
            ).pack(fill="x", pady=(4, 0))

            if item.is_image:
                try:
                    img = Image.open(BytesIO(item.data))
                    img.thumbnail((110, 110), Image.Resampling.LANCZOS)
                    photo = ImageTk.PhotoImage(img)
                    item.preview = photo
                    ctk.CTkLabel(card, text="", image=photo).pack(
                        side="right", padx=10, pady=10
                    )
                except Exception:
                    ctk.CTkLabel(card, text="صورة", text_color=T.TEXT_MUTED).pack(
                        side="right", padx=10
                    )
            else:
                ctk.CTkLabel(
                    card,
                    text=" PDF ",
                    font=T.font(13, "bold"),
                    text_color=T.DANGER,
                    fg_color="#FCEBEA",
                    corner_radius=8,
                ).pack(side="right", padx=10, pady=10)

    def _remove_file(self, index: int) -> None:
        if 0 <= index < len(self.files):
            self.files.pop(index)
            self._render_files()

    def _save(self) -> None:
        self.error_label.configure(text="")
        self._sync_meta_from_ui()

        statistical = (self.injury_statistical_number or "").strip()
        if not statistical:
            msg = "الرجاء البحث عن الجريح قبل الحفظ"
            self.error_label.configure(text=msg)
            show_error("تنبيه", msg)
            return
        if not self.files:
            msg = "لا توجد ملفات لإرسالها"
            self.error_label.configure(text=msg)
            show_error("تنبيه", msg)
            return

        for item in self.files:
            if not item.book_type.strip() or not item.book_number.strip():
                msg = "الرجاء تعبئة نوع الكتاب والعدد لكل ملف"
                self.error_label.configure(text=msg)
                show_error("تنبيه", msg)
                return

        total = sum(len(f.data) for f in self.files)
        if total > MAX_REQUEST_BYTES:
            msg = (
                f"حجم الملفات ({total / (1024 * 1024):.1f}MB) أكبر من حد السيرفر (~30MB). "
                "قلّل عدد الصفحات أو الدقة."
            )
            self.error_label.configure(text=msg)
            show_error("حجم كبير", msg)
            return

        payload = [
            ArchiveFileItem(
                book_type=f.book_type.strip(),
                book_number=f.book_number.strip(),
                file_bytes=f.data,
                file_name=f.file_name,
                mime_type=f.mime_type,
            )
            for f in self.files
        ]

        self._set_busy(True, "جاري الحفظ...")

        def worker():
            try:
                result = self.api.add_archive_file(statistical, payload)
                self.after(0, lambda: self._after_save(result, None))
            except ApiError as exc:
                self.after(0, lambda: self._after_save(None, exc.message))
            except Exception as exc:
                self.after(0, lambda: self._after_save(None, str(exc)))

        threading.Thread(target=worker, daemon=True).start()

    def _sync_meta_from_ui(self) -> None:
        children = self.files_scroll.winfo_children()
        for index, card in enumerate(children):
            if index >= len(self.files):
                break
            for frame in card.winfo_children():
                if not isinstance(frame, ctk.CTkFrame):
                    continue
                entry_widgets = [
                    w for w in frame.winfo_children() if isinstance(w, ctk.CTkEntry)
                ]
                if len(entry_widgets) >= 2:
                    self.files[index].book_type = entry_widgets[0].get().strip()
                    self.files[index].book_number = entry_widgets[1].get().strip()

    def _after_save(self, result, error: Optional[str]) -> None:
        self._set_busy(False)
        if error:
            self.error_label.configure(text=error)
            show_error("فشل الحفظ", error)
            return
        if isinstance(result, dict) and result.get("error") is True:
            message = str(result.get("message") or "فشل رفع الملف")
            self.error_label.configure(text=message)
            show_error("فشل الحفظ", message)
            return

        message = ""
        if isinstance(result, dict):
            message = str(result.get("message") or "")
        self.files.clear()
        self._render_files()
        show_info("تم الحفظ", message or "تم رفع الأرشيف بنجاح")
