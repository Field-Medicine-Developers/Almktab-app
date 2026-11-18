"""طبقة المسح الموحّدة: WIA أولاً ثم TWAIN."""

from __future__ import annotations

import io
import os
import platform
import sys
import tempfile
import urllib.request
import zipfile
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Sequence

from PIL import Image

from app.scanner.models import ScannerDevice, ScannerError, ScannedImage

# إعادة تصدير الأسماء للتوافق
__all__ = [
    "ScannerDevice",
    "ScannedImage",
    "ScannerError",
    "is_windows",
    "list_devices",
    "prefer_device_name",
    "scan",
    "ensure_twain_dsm",
]

ROOT = Path(__file__).resolve().parents[2]
NATIVE_DIR = ROOT / "app" / "scanner" / "native"
DSM_URLS = (
    # الاسم الصحيح من إصدارات GitHub الرسمية
    "https://github.com/twain/twain-dsm/releases/download/v2.5.1/dsm_020501.zip",
    "https://github.com/twain/twain-dsm/releases/download/v2.5.0/dsm_020500.zip",
    "https://github.com/twain/twain-dsm/releases/download/v2.4.2/dsm_020402.zip",
)


def is_windows() -> bool:
    return platform.system().lower() == "windows"


def prefer_device_name(devices: Sequence[ScannerDevice]) -> str:
    if not devices:
        return ""
    for device in devices:
        if "canon" in device.name.lower():
            return device.name
    # فضّل WIA إن وُجد لأنه لا يحتاج twaindsm
    for device in devices:
        if device.backend == "wia" or device.name.startswith("[WIA]"):
            return device.name
    return devices[0].name


def list_devices() -> List[ScannerDevice]:
    if not is_windows():
        raise ScannerError(
            "المسح المباشر متاح على ويندوز فقط. شغّل التطبيق على جهاز ويندوز متصل بالسكنر."
        )

    _warn_store_python()
    devices: List[ScannerDevice] = []
    errors: List[str] = []

    # 1) WIA — المدمج في ويندوز
    try:
        from app.scanner.wia_backend import list_wia_devices

        devices.extend(list_wia_devices())
    except Exception as exc:
        errors.append(f"WIA: {exc}")

    # 2) TWAIN — اختياري؛ الفشل لا يمنع WIA
    try:
        ensure_twain_dsm()
        devices.extend(_list_twain_devices())
    except Exception as exc:
        # لا نُظهر فشل تحميل DSM إن وُجدت أجهزة WIA
        if not devices:
            errors.append(f"TWAIN: {exc}")

    # إزالة التكرار بالاسم
    unique: dict[str, ScannerDevice] = {}
    for device in devices:
        unique[device.name.lower()] = device
    result = sorted(unique.values(), key=lambda d: d.name.lower())

    if result:
        return result

    hint = (
        "لم يتم العثور على سكنر.\n"
        "- تأكد أن السكنر متصل ومشغّل\n"
        "- جرّب من واجهة التنصيب: تنصيب المتطلبات (يثبّت pywin32)\n"
        "- تجنّب Python من Microsoft Store؛ استخدم python.org\n"
    )
    if errors:
        hint += "\nالتفاصيل:\n- " + "\n- ".join(errors)
    raise ScannerError(hint)


def scan(
    device_name: Optional[str] = None,
    dpi: int = 300,
    use_feeder: bool = True,
    show_ui: bool = False,
) -> List[ScannedImage]:
    """
    مسح صفحات متعددة عند use_feeder=True (ADF مستمر حتى نفاد الورق).
    لرزمة الأوراق: نفضّل TWAIN أولاً (مثل خدمة النظام)، ثم WIA بنمط إعادة الاتصال.
    """
    if not is_windows():
        raise ScannerError("المسح متاح على ويندوز فقط.")

    _warn_store_python()
    name = device_name or ""
    force_wia = name.startswith("[WIA]")
    force_twain = name.startswith("[TWAIN]")
    ui = False if use_feeder else bool(show_ui)
    errors: List[str] = []

    def try_twain() -> List[ScannedImage]:
        ensure_twain_dsm()
        return _scan_twain(
            device_name=_strip_prefix(name),
            dpi=dpi,
            use_feeder=use_feeder,
            show_ui=ui,
        )

    def try_wia() -> List[ScannedImage]:
        from app.scanner.wia_backend import scan_wia

        return scan_wia(
            device_name=name,
            dpi=dpi,
            use_feeder=use_feeder,
            show_ui=ui,
        )

    # ترتيب المحاولات حسب الجهاز والـ ADF
    if force_wia:
        order = [try_wia, try_twain]
    elif force_twain or use_feeder:
        # ADF: TWAIN أولاً (Canon DR يعمل عليه في النظام الحالي)
        order = [try_twain, try_wia]
    else:
        order = [try_wia, try_twain]

    for attempt in order:
        try:
            images = attempt()
            if images:
                return images
        except Exception as exc:
            errors.append(f"{attempt.__name__}: {exc}")
            if force_wia and attempt is try_wia:
                # إن اختير WIA صراحة نكمّل للمحاولة التالية بدل الإيقاف فوراً
                continue
            if force_twain and attempt is try_twain:
                continue

    raise ScannerError(
        "فشل المسح من كل الطرق المتاحة.\n"
        "للـ ADF: ضع الرزمة في المغذي، وفضّل جهاز [TWAIN] إن ظهر، أو USB وليس WSD.\n"
        "- " + "\n- ".join(errors)
    )


def ensure_twain_dsm() -> Path:
    """يضمن وجود TWAINDSM.dll محلياً ويضيفه لمسار البحث."""
    NATIVE_DIR.mkdir(parents=True, exist_ok=True)
    dll_path = NATIVE_DIR / "TWAINDSM.dll"
    alt = NATIVE_DIR / "twaindsm.dll"

    # ابحث أولاً في مسارات ويندوز الشائعة
    windir = Path(os.environ.get("WINDIR", r"C:\Windows"))
    for extra in (
        windir / "System32",
        windir / "SysWOW64",
        windir,
        NATIVE_DIR,
    ):
        for name in ("TWAINDSM.dll", "twaindsm.dll"):
            candidate = extra / name
            if candidate.exists():
                _add_dll_dir(extra)
                _add_dll_dir(NATIVE_DIR)
                return candidate

    if not dll_path.exists() and alt.exists():
        dll_path = alt

    if not dll_path.exists():
        _download_twain_dsm(dll_path)

    lower = NATIVE_DIR / "twaindsm.dll"
    if dll_path.exists() and not lower.exists():
        try:
            lower.write_bytes(dll_path.read_bytes())
        except Exception:
            pass

    _add_dll_dir(NATIVE_DIR)
    return dll_path


def _download_twain_dsm(target_dll: Path) -> None:
    archive = NATIVE_DIR / "twaindsm.zip"
    last_error: Exception | None = None
    try:
        for url in DSM_URLS:
            try:
                urllib.request.urlretrieve(url, filename=str(archive))
                break
            except Exception as exc:
                last_error = exc
                continue
        else:
            raise ScannerError(
                "تعذر تحميل twaindsm.dll تلقائياً.\n"
                "السكنر قد يعمل عبر WIA بدون هذه المكتبة.\n"
                f"التفاصيل: {last_error}"
            )

        with zipfile.ZipFile(archive, "r") as zf:
            members = [
                m
                for m in zf.namelist()
                if m.lower().endswith("twaindsm.dll") and not m.endswith("/")
            ]
            if not members:
                raise ScannerError("حزمة TWAINDSM لا تحتوي على المكتبة.")

            # فضّل 64-bit لتطبيقات python 64
            member = None
            for name in members:
                lower = name.replace("\\", "/").lower()
                if any(token in lower for token in ("/64/", "x64", "amd64", "64bit", "64-bit")):
                    member = name
                    break
            if member is None:
                # بعض الحزم تضع النسخ في مجلدات مثل bin/Release64
                for name in members:
                    lower = name.replace("\\", "/").lower()
                    if "32" not in Path(lower).parts and "x86" not in lower:
                        member = name
                        break
            member = member or members[-1]
            target_dll.write_bytes(zf.read(member))
    except ScannerError:
        raise
    except Exception as exc:
        raise ScannerError(
            "تعذر تحميل twaindsm.dll تلقائياً.\n"
            "السكنر قد يعمل عبر WIA بدون هذه المكتبة.\n"
            f"التفاصيل: {exc}"
        ) from exc
    finally:
        if archive.exists():
            try:
                archive.unlink()
            except OSError:
                pass


def _add_dll_dir(path: Path) -> None:
    path_str = str(path)
    if hasattr(os, "add_dll_directory"):
        try:
            os.add_dll_directory(path_str)
        except Exception:
            pass
    os.environ["PATH"] = path_str + os.pathsep + os.environ.get("PATH", "")


def _warn_store_python() -> None:
    exe = (sys.executable or "").lower()
    if "windowsapps" in exe or "pythonsoftwarefoundation" in exe:
        # لا نرفع خطأ؛ نترك رسالة ضمن الاستثناءات إن فشلت المكتبات
        pass


def _is_store_python() -> bool:
    exe = (sys.executable or "").lower()
    return "windowsapps" in exe or "pythonsoftwarefoundation" in exe


def _import_twain():
    if not is_windows():
        raise ScannerError("TWAIN متاح على ويندوز فقط.")
    if _is_store_python():
        raise ScannerError(
            "أنت تستخدم Python من Microsoft Store وهو غالباً يمنع تحميل twaindsm.dll.\n"
            "ثبّت Python من python.org عبر واجهة التنصيب (تثبيت Python + PATH) ثم أعد المحاولة."
        )
    ensure_twain_dsm()
    try:
        import twain  # type: ignore
    except ImportError as exc:
        raise ScannerError("مكتبة pytwain غير مثبتة. نفّذ تنصيب المتطلبات.") from exc
    except Exception as exc:
        message = str(exc)
        if "twaindsm" in message.lower():
            raise ScannerError(
                "تعذر تحميل twaindsm.dll.\n"
                "جرّب المسح عبر جهاز [WIA] من القائمة، أو ثبّت Python من python.org."
            ) from exc
        raise ScannerError(f"فشل تحميل TWAIN: {exc}") from exc
    return twain


def _list_twain_devices() -> List[ScannerDevice]:
    twain = _import_twain()
    source_manager = None
    try:
        source_manager = twain.SourceManager(0)
        names = list(source_manager.GetSourceList() or [])
        return [
            ScannerDevice(name=f"[TWAIN] {name}", product_family="TWAIN", backend="twain")
            for name in names
        ]
    finally:
        _safe_destroy(source_manager)


def _scan_twain(
    device_name: Optional[str],
    dpi: int,
    use_feeder: bool,
    show_ui: bool,
) -> List[ScannedImage]:
    twain = _import_twain()
    source_manager = None
    source = None
    images: List[ScannedImage] = []

    try:
        source_manager = twain.SourceManager(0)
        names = list(source_manager.GetSourceList() or [])
        if not names:
            raise ScannerError("لا توجد مصادر TWAIN.")

        selected = device_name if device_name in names else None
        if not selected:
            preferred = prefer_device_name(
                [ScannerDevice(name=n, backend="twain") for n in names]
            )
            selected = _strip_prefix(preferred) if preferred else names[0]
            if selected not in names:
                selected = names[0]

        source = source_manager.OpenSource(selected)
        _configure_source(twain, source, dpi=dpi, use_feeder=use_feeder)

        # ADF: بدون UI + غير نافذة مودال حتى يستمر السحب
        if use_feeder:
            source.RequestAcquire(0, 0)
        else:
            source.RequestAcquire(1 if show_ui else 0, 1 if show_ui else 0)

        index = 0
        while index < 200:
            try:
                result = source.XferImageNatively()
            except Exception:
                break
            if not result:
                break

            dib_handle = result[0] if isinstance(result, tuple) else result
            if not dib_handle:
                break
            more = True
            if isinstance(result, tuple) and len(result) > 1:
                # في pytwain: العنصر الثاني غالباً عدد المتبقي / مؤشر استمرار
                more_flag = result[1]
                more = bool(more_flag) if not isinstance(more_flag, bool) else more_flag
                if isinstance(more_flag, int):
                    more = more_flag != 0

            index += 1
            bmp_path = None
            try:
                with tempfile.NamedTemporaryFile(suffix=".bmp", delete=False) as tmp:
                    bmp_path = Path(tmp.name)
                twain.DIBToBMFile(dib_handle, str(bmp_path))
                try:
                    twain.GlobalHandleFree(dib_handle)
                except Exception:
                    pass
                with Image.open(bmp_path) as img:
                    if img.mode != "RGB":
                        img = img.convert("RGB")
                    buf = io.BytesIO()
                    img.save(buf, format="JPEG", quality=90, optimize=True)
                    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
                    images.append(
                        ScannedImage(
                            data=buf.getvalue(),
                            mime_type="image/jpeg",
                            file_name=f"twain-{stamp}-{index}.jpg",
                        )
                    )
            finally:
                if bmp_path and bmp_path.exists():
                    try:
                        bmp_path.unlink()
                    except OSError:
                        pass

            if not use_feeder:
                break
            # مع ADF نستمر ما دام النقل يعيد صوراً؛ more=False لا يوقف فوراً
            # لأن بعض تعريفات Canon تعيده بشكل غير موثوق بين الصفحات
            if use_feeder:
                continue
            if not more:
                break

        if not images:
            raise ScannerError("لم يتم استلام أي صورة من TWAIN.")
        return images
    finally:
        _safe_destroy(source)
        _safe_destroy(source_manager)


def _strip_prefix(name: str) -> str:
    for prefix in ("[WIA] ", "[TWAIN] "):
        if name.startswith(prefix):
            return name[len(prefix) :]
    return name


def _configure_source(twain, source, dpi: int, use_feeder: bool) -> None:
    def _try(setters) -> None:
        for setter in setters:
            try:
                setter()
                return
            except Exception:
                continue

    _try(
        (
            lambda: source.SetCapability(
                twain.ICAP_PIXELTYPE, twain.TWTY_UINT16, twain.TWPT_RGB
            ),
            lambda: source.SetCapability("ICAP_PIXELTYPE", twain.TWPT_RGB),
        )
    )
    _try(
        (
            lambda: source.SetCapability(
                twain.ICAP_XRESOLUTION, twain.TWTY_FIX32, float(dpi)
            ),
            lambda: source.SetCapability("ICAP_XRESOLUTION", float(dpi)),
        )
    )
    _try(
        (
            lambda: source.SetCapability(
                twain.ICAP_YRESOLUTION, twain.TWTY_FIX32, float(dpi)
            ),
            lambda: source.SetCapability("ICAP_YRESOLUTION", float(dpi)),
        )
    )

    if use_feeder:
        # مطابق تقريباً لإعدادات خدمة Alkadmat C# + AutoFeed + كل الصفحات
        _try(
            (
                lambda: source.SetCapability(
                    twain.CAP_FEEDERENABLED, twain.TWTY_BOOL, True
                ),
                lambda: source.SetCapability("CAP_FEEDERENABLED", True),
            )
        )
        _try(
            (
                lambda: source.SetCapability(twain.CAP_AUTOFEED, twain.TWTY_BOOL, True),
                lambda: source.SetCapability("CAP_AUTOFEED", True),
            )
        )
        # -1 = كل الصفحات في المغذي
        _try(
            (
                lambda: source.SetCapability(twain.CAP_XFERCOUNT, twain.TWTY_INT16, -1),
                lambda: source.SetCapability("CAP_XFERCOUNT", -1),
            )
        )


def _safe_destroy(obj) -> None:
    if obj is None:
        return
    try:
        obj.destroy()
    except Exception:
        pass
