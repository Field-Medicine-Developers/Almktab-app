"""نماذج المسح المشتركة."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class ScannerDevice:
    name: str
    product_family: str = ""
    backend: str = ""  # wia | twain


@dataclass
class ScannedImage:
    data: bytes
    mime_type: str
    file_name: str


class ScannerError(Exception):
    pass
