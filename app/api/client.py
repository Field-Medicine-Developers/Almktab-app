"""عميل HTTP لنفس واجهات الأرشفة في نظام الخدمات الصحية."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Sequence
from urllib.parse import urljoin, urlparse

import httpx

from app.config import API_BASE_URL, LEGACY_UPLOAD_ORIGINS


class ApiError(Exception):
    def __init__(self, message: str, details: Any = None):
        super().__init__(message)
        self.message = message
        self.details = details


@dataclass
class ArchiveFileItem:
    book_type: str
    book_number: str
    file_bytes: bytes
    file_name: str
    mime_type: str = "image/jpeg"


class ApiClient:
    def __init__(self, base_url: str = API_BASE_URL, timeout: float = 120.0):
        self.base_url = base_url.rstrip("/")
        self.token: Optional[str] = None
        self._client = httpx.Client(base_url=self.base_url, timeout=timeout)

    def close(self) -> None:
        self._client.close()

    def set_token(self, token: Optional[str]) -> None:
        self.token = token

    def _headers(self, json_body: bool = False) -> Dict[str, str]:
        headers: Dict[str, str] = {}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        if json_body:
            headers["Content-Type"] = "application/json"
        return headers

    def _unwrap(self, payload: Any) -> Any:
        if isinstance(payload, dict) and payload.get("error") is True:
            raise ApiError(
                str(payload.get("message") or "حدث خطأ في الخادم"),
                details=payload,
            )
        return payload

    def login(self, username: str, password: str) -> Dict[str, Any]:
        response = self._client.post(
            "/Auth/Login",
            json={"username": username, "password": password},
        )
        data = self._parse_response(response)
        body = data.get("data") if isinstance(data, dict) else None
        if not isinstance(body, dict) or not body.get("token"):
            raise ApiError("خطأ في معلومات الدخول")
        self.token = body["token"]
        return body

    def get_injury(self, info: str) -> Optional[Dict[str, Any]]:
        info = (info or "").strip()
        if not info:
            return None
        response = self._client.get(
            "/Injury/GetInjury",
            params={"info": info},
            headers=self._headers(),
        )
        data = self._parse_response(response)
        if isinstance(data, dict):
            return data.get("data")
        return None

    def get_archive_files(
        self,
        page_number: int,
        page_size: int,
        info: str = "",
        book_number: str = "",
        book_type: str = "",
    ) -> Dict[str, Any]:
        response = self._client.get(
            "/InjuryArchiveFile/GetArchiveFile",
            params={
                "info": info or "",
                "PageNumber": page_number,
                "PageSize": page_size,
                "bookNumber": book_number or "",
                "bookType": book_type or "",
            },
            headers=self._headers(),
        )
        data = self._parse_response(response)
        if not isinstance(data, dict):
            return {"data": [], "filteredCount": 0}
        return data

    def add_archive_file(
        self,
        injury_statistical_number: str,
        items: Sequence[ArchiveFileItem],
    ) -> Any:
        if not injury_statistical_number:
            raise ApiError("الرقم الإحصائي مطلوب")
        if not items:
            raise ApiError("لا توجد ملفات لإرسالها")

        files = []
        data: List[tuple[str, str]] = [
            ("InjuryStatisticalNumber", str(injury_statistical_number)),
        ]

        for index, item in enumerate(items):
            data.append((f"ArchiveFilesList[{index}].bookNumber", item.book_number or ""))
            data.append((f"ArchiveFilesList[{index}].bookType", item.book_type or ""))
            files.append(
                (
                    f"ArchiveFilesList[{index}].file",
                    (item.file_name, item.file_bytes, item.mime_type),
                )
            )

        response = self._client.post(
            "/InjuryArchiveFile/AddArchiveFile",
            data=data,
            files=files,
            headers=self._headers(),
        )
        return self._parse_response(response)

    def edit_archive_file(self, body: Dict[str, Any]) -> Any:
        response = self._client.put(
            "/InjuryArchiveFile/EditArchiveFile",
            json=body,
            headers=self._headers(json_body=True),
        )
        return self._parse_response(response)

    def delete_archive_file(self, archive_id: Any) -> Any:
        response = self._client.delete(
            "/InjuryArchiveFile/DeleteArchiveFile",
            params={"id": archive_id},
            headers=self._headers(),
        )
        return self._parse_response(response)

    def resolve_file_url(self, url: Optional[str]) -> Optional[str]:
        if not url:
            return url
        try:
            parsed = urlparse(url)
            origin = f"{parsed.scheme}://{parsed.netloc}" if parsed.scheme else ""
            if origin in LEGACY_UPLOAD_ORIGINS and parsed.path.startswith("/uploads/"):
                return urljoin(self.base_url + "/", parsed.path.lstrip("/"))
            if url.startswith("/"):
                return urljoin(self.base_url + "/", url.lstrip("/"))
        except Exception:
            return url
        return url

    def _parse_response(self, response: httpx.Response) -> Any:
        try:
            payload = response.json()
        except Exception:
            payload = None

        if response.is_success:
            if payload is None:
                return {"success": True}
            return self._unwrap(payload)

        message = f"خطأ من الخادم ({response.status_code})"
        details = payload
        if isinstance(payload, dict):
            message = (
                payload.get("message")
                or payload.get("title")
                or payload.get("detail")
                or message
            )
            if payload.get("errors"):
                message = f"{message}: {payload['errors']}"
        raise ApiError(str(message), details=details)
