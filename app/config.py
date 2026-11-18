"""إعدادات تطبيق المكتبة."""

from __future__ import annotations

import os
from pathlib import Path

APP_NAME = "برنامج المكتبة — الأرشفة"
APP_VERSION = "1.0.0"

# نفس الـ API المستخدم في alkadmat-frontend
API_BASE_URL = os.environ.get(
    "ALMKTAB_API_BASE_URL",
    "https://services-api.cmfsa-iq.com",
).rstrip("/")

# حد حجم الطلب تقريباً كما في الواجهة (~30MB)
MAX_REQUEST_BYTES = 28 * 1024 * 1024
MAX_IMAGE_BYTES = 8 * 1024 * 1024
DEFAULT_JPEG_QUALITY = 85
DEFAULT_SCAN_DPI = 300
DEFAULT_PAGE_SIZE = 10

# مسار حفظ الجلسة محلياً
DATA_DIR = Path.home() / ".almktab"
SESSION_FILE = DATA_DIR / "session.json"

# عناوين قديمة لملفات الأرشيف تُصحَّح إلى أصل الـ API
LEGACY_UPLOAD_ORIGINS = (
    "http://185.122.255.78:5000",
)
