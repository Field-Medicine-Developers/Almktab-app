"""شاشة قائمة الأرشيف: بحث، عرض، تعديل، حذف."""

from __future__ import annotations

import threading
import webbrowser
from typing import Any, Callable, Dict, List, Optional

import customtkinter as ctk
from tkinter import ttk

from app.api.client import ApiClient, ApiError
from app.config import APP_NAME, DEFAULT_PAGE_SIZE
from app.ui import theme as T
from app.ui.widgets import (
    AccentButton,
    AppCard,
    EditArchiveDialog,
    GhostButton,
    LabeledEntry,
    PrimaryButton,
    SectionTitle,
    StatusBadge,
    ask_yes_no,
    show_error,
    show_info,
)


class ArchiveListFrame(ctk.CTkFrame):
    def __init__(
        self,
        master,
        api: ApiClient,
        user_name: str = "",
        on_add: Optional[Callable[[], None]] = None,
        on_logout: Optional[Callable[[], None]] = None,
        **kwargs,
    ):
        super().__init__(master, fg_color=T.BG, **kwargs)
        self.api = api
        self.on_add = on_add
        self.on_logout = on_logout
        self.page_number = 1
        self.page_size = DEFAULT_PAGE_SIZE
        self.total_count = 0
        self.rows: List[Dict[str, Any]] = []
        self._busy = False

        self._build_topbar(user_name)
        self._build_search()
        self._build_table()
        self._build_pager()
        self.after(100, self.refresh)

    def _build_topbar(self, user_name: str) -> None:
        bar = ctk.CTkFrame(
            self,
            fg_color=T.PRIMARY,
            corner_radius=0,
            height=72,
        )
        bar.pack(fill="x")
        bar.pack_propagate(False)

        inner = ctk.CTkFrame(bar, fg_color="transparent")
        inner.pack(fill="both", expand=True, padx=22)

        right = ctk.CTkFrame(inner, fg_color="transparent")
        right.pack(side="right", fill="y")
        ctk.CTkLabel(
            right,
            text=APP_NAME,
            font=T.font(20, "bold"),
            text_color="#FFFFFF",
        ).pack(anchor="e", pady=(14, 0))
        ctk.CTkLabel(
            right,
            text="إدارة ملفات الأرشيف والوثائق",
            font=T.font(12),
            text_color="#D7EBEF",
        ).pack(anchor="e")

        left = ctk.CTkFrame(inner, fg_color="transparent")
        left.pack(side="left", fill="y", pady=14)

        GhostButton(left, "تسجيل الخروج", command=self._logout, width=120).pack(
            side="left", padx=6
        )
        AccentButton(left, "إضافة أرشيف", command=self._go_add, width=140).pack(
            side="left", padx=6
        )
        if user_name:
            ctk.CTkLabel(
                left,
                text=f"مرحباً، {user_name}",
                font=T.font(12, "bold"),
                text_color="#FFFFFF",
            ).pack(side="left", padx=10)

    def _build_search(self) -> None:
        card = AppCard(self)
        card.pack(fill="x", padx=20, pady=(18, 10))

        head = ctk.CTkFrame(card, fg_color="transparent")
        head.pack(fill="x", padx=18, pady=(16, 8))
        SectionTitle(
            head, "البحث والتصفية", "ابحث بالاسم أو الرقم الإحصائي أو بيانات الكتاب"
        ).pack(side="right", fill="x", expand=True)
        self.status_badge = StatusBadge(head, "جاهز", "info")
        self.status_badge.pack(side="left", padx=4)

        grid = ctk.CTkFrame(card, fg_color="transparent")
        grid.pack(fill="x", padx=14, pady=(0, 8))

        self.info_entry = LabeledEntry(
            grid, "الاسم / الرقم الإحصائي", placeholder="ادخل الاسم أو الرقم..."
        )
        self.info_entry.pack(side="right", fill="x", expand=True, padx=6)

        self.book_number_entry = LabeledEntry(
            grid, "عدد الكتاب", placeholder="رقم الكتاب..."
        )
        self.book_number_entry.pack(side="right", fill="x", expand=True, padx=6)

        self.book_type_entry = LabeledEntry(
            grid, "نوع الكتاب", placeholder="نوع الوثيقة..."
        )
        self.book_type_entry.pack(side="right", fill="x", expand=True, padx=6)

        actions = ctk.CTkFrame(card, fg_color="transparent")
        actions.pack(fill="x", padx=18, pady=(4, 16))
        self.search_btn = PrimaryButton(actions, "بحث", command=self._search, width=120)
        self.search_btn.pack(side="right", padx=6)
        GhostButton(actions, "مسح الفلترة", command=self._clear, width=120).pack(
            side="right", padx=6
        )
        self.status_label = ctk.CTkLabel(
            actions, text="", font=T.font(12), text_color=T.TEXT_MUTED, anchor="e"
        )
        self.status_label.pack(side="left", fill="x", expand=True)

        self.info_entry.bind_return(self._search)
        self.book_number_entry.bind_return(self._search)
        self.book_type_entry.bind_return(self._search)

    def _build_table(self) -> None:
        card = AppCard(self)
        card.pack(fill="both", expand=True, padx=20, pady=8)

        title_row = ctk.CTkFrame(card, fg_color="transparent")
        title_row.pack(fill="x", padx=18, pady=(14, 8))
        SectionTitle(title_row, "نتائج الأرشيف").pack(side="right")
        ctk.CTkLabel(
            title_row,
            text="انقر عرض / تعديل / حذف من عمود الإجراءات",
            font=T.font(11),
            text_color=T.TEXT_MUTED,
        ).pack(side="left")

        wrap = ctk.CTkFrame(card, fg_color=T.SURFACE, corner_radius=12)
        wrap.pack(fill="both", expand=True, padx=14, pady=(0, 14))

        style_name = T.style_treeview("Almktab.Treeview")
        columns = (
            "actions",
            "created_by",
            "book",
            "book_type",
            "book_number",
            "archive_number",
            "full_name",
            "index",
        )
        self.tree = ttk.Treeview(
            wrap,
            columns=columns,
            show="headings",
            style=style_name,
            selectmode="browse",
        )
        headings = {
            "index": "#",
            "full_name": "اسم الجريح",
            "archive_number": "الرقم الإحصائي",
            "book_number": "العدد",
            "book_type": "نوع الكتاب",
            "book": "الكتاب",
            "created_by": "بواسطة",
            "actions": "إجراءات",
        }
        widths = {
            "index": 50,
            "full_name": 170,
            "archive_number": 120,
            "book_number": 80,
            "book_type": 130,
            "book": 100,
            "created_by": 110,
            "actions": 170,
        }
        for col in columns:
            self.tree.heading(col, text=headings[col], anchor="center")
            self.tree.column(col, width=widths[col], anchor="center")

        yscroll = ttk.Scrollbar(wrap, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=yscroll.set)
        self.tree.pack(side="left", fill="both", expand=True, padx=1, pady=1)
        yscroll.pack(side="right", fill="y")
        self.tree.bind("<Double-1>", self._on_double_click)
        self.tree.bind("<Button-1>", self._on_click)

    def _build_pager(self) -> None:
        pager = ctk.CTkFrame(self, fg_color="transparent")
        pager.pack(fill="x", padx=20, pady=(0, 18))

        self.page_label = ctk.CTkLabel(
            pager, text="", font=T.font(12, "bold"), text_color=T.TEXT
        )
        self.page_label.pack(side="right", padx=8)

        self.next_btn = GhostButton(pager, "التالي", command=self._next_page, width=100)
        self.next_btn.pack(side="left", padx=6)
        self.prev_btn = GhostButton(pager, "السابق", command=self._prev_page, width=100)
        self.prev_btn.pack(side="left", padx=6)

    def refresh(self) -> None:
        if self._busy:
            return
        self._busy = True
        self.search_btn.configure(state="disabled", text="جاري البحث...")
        self.status_label.configure(text="جاري التحميل...")
        self.status_badge.set_status("تحميل", "warn")

        info = self.info_entry.get()
        book_number = self.book_number_entry.get()
        book_type = self.book_type_entry.get()
        page = self.page_number
        size = self.page_size

        def worker():
            try:
                result = self.api.get_archive_files(
                    page, size, info, book_number, book_type
                )
                self.after(0, lambda r=result: self._apply_result(r))
            except ApiError as exc:
                err = exc.message
                self.after(0, lambda e=err: self._fail(e))
            except Exception as exc:
                err = str(exc)
                self.after(0, lambda e=err: self._fail(e))

        threading.Thread(target=worker, daemon=True).start()

    def _apply_result(self, result: Dict[str, Any]) -> None:
        self._busy = False
        self.search_btn.configure(state="normal", text="بحث")
        self.rows = list(result.get("data") or [])
        self.total_count = int(result.get("filteredCount") or 0)
        self._render_rows()
        total_pages = max(1, (self.total_count + self.page_size - 1) // self.page_size)
        self.page_label.configure(
            text=f"{self.total_count} نتيجة — صفحة {self.page_number} من {total_pages}"
        )
        if not self.rows:
            self.status_label.configure(text="لا توجد نتائج مطابقة")
            self.status_badge.set_status("فارغ", "muted")
        else:
            self.status_label.configure(text=f"تم عرض {len(self.rows)} سجل")
            self.status_badge.set_status("نتائج", "ok")
        self.prev_btn.configure(state="normal" if self.page_number > 1 else "disabled")
        self.next_btn.configure(
            state="normal"
            if self.page_number * self.page_size < self.total_count
            else "disabled"
        )

    def _fail(self, message: str) -> None:
        self._busy = False
        self.search_btn.configure(state="normal", text="بحث")
        self.status_label.configure(text=message)
        self.status_badge.set_status("خطأ", "bad")
        show_error("خطأ", message)

    def _render_rows(self) -> None:
        for item in self.tree.get_children():
            self.tree.delete(item)
        for idx, row in enumerate(self.rows):
            injury = row.get("injury") or {}
            created = row.get("createdBy") or {}
            index_no = (self.page_number - 1) * self.page_size + idx + 1
            values = (
                "عرض | تعديل | حذف",
                created.get("username") or "-",
                "فتح الملف",
                row.get("bookType") or "-",
                row.get("bookNumber") or "-",
                injury.get("archiveNumber") or "-",
                injury.get("fullName") or "-",
                str(index_no),
            )
            self.tree.insert("", "end", iid=str(row.get("id")), values=values)

    def _search(self) -> None:
        self.page_number = 1
        self.refresh()

    def _clear(self) -> None:
        self.info_entry.set("")
        self.book_number_entry.set("")
        self.book_type_entry.set("")
        self.page_number = 1
        self.refresh()

    def _prev_page(self) -> None:
        if self.page_number > 1:
            self.page_number -= 1
            self.refresh()

    def _next_page(self) -> None:
        if self.page_number * self.page_size < self.total_count:
            self.page_number += 1
            self.refresh()

    def _find_row(self, item_id: str) -> Optional[Dict[str, Any]]:
        for row in self.rows:
            if str(row.get("id")) == str(item_id):
                return row
        return None

    def _on_double_click(self, _event=None) -> None:
        selection = self.tree.selection()
        if selection:
            self._view_book(selection[0])

    def _on_click(self, event) -> None:
        region = self.tree.identify("region", event.x, event.y)
        if region != "cell":
            return
        column = self.tree.identify_column(event.x)
        row_id = self.tree.identify_row(event.y)
        if not row_id:
            return
        if column == "#1":
            bbox = self.tree.bbox(row_id, column)
            if not bbox:
                return
            ratio = (event.x - bbox[0]) / (bbox[2] or 1)
            if ratio < 0.33:
                self._view_book(row_id)
            elif ratio < 0.66:
                self._edit_book(row_id)
            else:
                self._delete_book(row_id)
        elif column == "#3":
            self._view_book(row_id)

    def _view_book(self, row_id: str) -> None:
        row = self._find_row(row_id)
        if not row:
            return
        url = self.api.resolve_file_url(row.get("fileUrl"))
        if not url:
            show_error("تنبيه", "لا يوجد رابط للملف")
            return
        webbrowser.open(url)

    def _edit_book(self, row_id: str) -> None:
        row = self._find_row(row_id)
        if not row:
            return

        def on_save(book_type: str, book_number: str):
            payload = {
                "id": row.get("id"),
                "bookType": book_type,
                "bookNumber": book_number,
            }

            def worker():
                try:
                    result = self.api.edit_archive_file(payload)
                    self.after(
                        0,
                        lambda: self._after_edit(row, book_type, book_number, result),
                    )
                except ApiError as exc:
                    err = exc.message
                    self.after(0, lambda e=err: show_error("فشل التعديل", e))
                except Exception as exc:
                    err = str(exc)
                    self.after(0, lambda e=err: show_error("فشل التعديل", e))

            threading.Thread(target=worker, daemon=True).start()

        EditArchiveDialog(
            self,
            book_type=str(row.get("bookType") or ""),
            book_number=str(row.get("bookNumber") or ""),
            on_save=on_save,
        )

    def _after_edit(
        self, row: Dict[str, Any], book_type: str, book_number: str, result: Any
    ) -> None:
        message = ""
        if isinstance(result, dict):
            message = str(result.get("message") or "")
            if result.get("error") is True:
                show_error("فشل التعديل", message or "فشل التعديل")
                return
        row["bookType"] = book_type
        row["bookNumber"] = book_number
        self._render_rows()
        show_info("تم", message or "تم التعديل بنجاح")

    def _delete_book(self, row_id: str) -> None:
        row = self._find_row(row_id)
        if not row:
            return
        if not ask_yes_no("تأكيد الحذف", "هل أنت متأكد؟ لن تتمكن من التراجع عن هذا!"):
            return

        def worker():
            try:
                result = self.api.delete_archive_file(row.get("id"))
                self.after(0, lambda: self._after_delete(row_id, result))
            except ApiError as exc:
                err = exc.message
                self.after(0, lambda e=err: show_error("فشل الحذف", e))
            except Exception as exc:
                err = str(exc)
                self.after(0, lambda e=err: show_error("فشل الحذف", e))

        threading.Thread(target=worker, daemon=True).start()

    def _after_delete(self, row_id: str, result: Any) -> None:
        if isinstance(result, dict) and result.get("error") is True:
            show_error("فشل الحذف", str(result.get("message") or "فشل الحذف"))
            return
        self.rows = [r for r in self.rows if str(r.get("id")) != str(row_id)]
        self.total_count = max(0, self.total_count - 1)
        self._render_rows()
        show_info("تم", "تم حذف الملف")

    def _go_add(self) -> None:
        if self.on_add:
            self.on_add()

    def _logout(self) -> None:
        if self.on_logout:
            self.on_logout()
