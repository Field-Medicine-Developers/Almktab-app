"""مسح عبر WIA المدمج في ويندوز — دعم ADF لعدة صفحات متتالية."""

from __future__ import annotations

import io
import tempfile
import threading
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Iterator, List, Optional

from PIL import Image

from app.scanner.models import ScannerDevice, ScannerError, ScannedImage

WIA_DEVICE_SCANNER = 1
WIA_INTENT_COLOR = 1
WIA_FORMAT_JPEG = "{B96B3CAE-0728-11D3-9D7B-0000F81EF32E}"
WIA_FORMAT_BMP = "{B96B3CAB-0728-11D3-9D7B-0000F81EF32E}"
WIA_FORMAT_PNG = "{B96B3CAF-0728-11D3-9D7B-0000F81EF32E}"
WIA_HORIZONTAL_RESOLUTION = "Horizontal Resolution"
WIA_VERTICAL_RESOLUTION = "Vertical Resolution"
WIA_CURRENT_INTENT = "Current Intent"
WIA_FEEDER = 0x001
WIA_FLATBED = 0x002
WIA_FEED_READY = 0x01

PAPER_EMPTY_CODES = {
    "0x80210003",
    "0x80210002",
    "0x80210001",
    "0x80210006",
    "0x80210064",
}

_com_state = threading.local()


@contextmanager
def _com_initialized() -> Iterator[None]:
    """تهيئة COM مرة واحدة لكل خيط مع عدّاد لمنع الإغلاق المبكر."""
    try:
        import pythoncom  # type: ignore
    except ImportError as exc:
        raise ScannerError(
            "مكتبة pywin32 غير مكتملة. من واجهة التنصيب اضغط «تنصيب المتطلبات»."
        ) from exc

    depth = getattr(_com_state, "depth", 0)
    if depth == 0:
        try:
            pythoncom.CoInitializeEx(pythoncom.COINIT_APARTMENTTHREADED)
        except Exception:
            try:
                pythoncom.CoInitialize()
            except Exception:
                # مهيأ مسبقاً
                pass
        _com_state.owned = True
    _com_state.depth = depth + 1
    try:
        yield
    finally:
        _com_state.depth = getattr(_com_state, "depth", 1) - 1
        if _com_state.depth <= 0 and getattr(_com_state, "owned", False):
            _com_state.depth = 0
            _com_state.owned = False
            try:
                pythoncom.CoUninitialize()
            except Exception:
                pass


def _dispatch(prog_id: str):
    try:
        import win32com.client  # type: ignore
    except ImportError as exc:
        raise ScannerError(
            "مكتبة pywin32 غير مثبتة. من واجهة التنصيب اضغط «تنصيب المتطلبات» "
            "أو نفّذ: pip install pywin32"
        ) from exc
    return win32com.client.Dispatch(prog_id)


def list_wia_devices() -> List[ScannerDevice]:
    with _com_initialized():
        return _list_wia_devices_unlocked()


def _list_wia_devices_unlocked() -> List[ScannerDevice]:
    manager = _dispatch("WIA.DeviceManager")
    devices: List[ScannerDevice] = []
    count = int(manager.DeviceInfos.Count)
    for index in range(1, count + 1):
        info = manager.DeviceInfos(index)
        try:
            if int(info.Type) != WIA_DEVICE_SCANNER:
                continue
        except Exception:
            continue
        name = _prop(info, "Name") or f"Scanner-{index}"
        manufacturer = _prop(info, "Manufacturer") or "WIA"
        devices.append(
            ScannerDevice(
                name=f"[WIA] {name}",
                product_family=str(manufacturer),
                backend="wia",
            )
        )
    devices.sort(key=lambda d: d.name.lower())
    return devices


def scan_wia(
    device_name: Optional[str] = None,
    dpi: int = 300,
    use_feeder: bool = True,
    show_ui: bool = False,
) -> List[ScannedImage]:
    """
    مسح مستمر من ADF قدر الإمكان.
    إن فشلت الإعدادات الصامتة نستخدم حوار السكنر (يدعم الرزم غالباً).
    """
    with _com_initialized():
        info = _resolve_device_info_unlocked(device_name)
        errors: List[str] = []

        # 1) محاولة صامتة مبسّطة للرزمة
        if use_feeder:
            try:
                images = _scan_batch_silent(info, dpi=dpi)
                if images:
                    return images
            except Exception as exc:
                errors.append(f"صامت: {exc}")

        # 2) حوار ويندوز/تعريف السكنر — الأنسب لـ Canon وغيرها مع ADF
        try:
            images = _scan_with_common_dialog_batch(prefer_feeder=use_feeder)
            if images:
                return images
        except Exception as exc:
            errors.append(f"حوار: {exc}")

        # 3) صفحة واحدة كحل أخير
        try:
            device = info.Connect()
            if int(device.Items.Count) < 1:
                raise ScannerError("السكنر لا يوفّر عنصر مسح.")
            item = device.Items[1]
            _soft_set_dpi(item, dpi)
            image = _transfer_image(item)
            if image is not None:
                return [_to_scanned(image, 1)]
        except Exception as exc:
            errors.append(f"صفحة: {exc}")

        detail = "\n- ".join(errors) if errors else "سبب غير معروف"
        raise ScannerError(
            "تعذر مسح الرزمة عبر WIA.\n"
            "ضع الأوراق في المغذي، اختر ADF من شاشة السكنر إن ظهرت، ثم أعد المحاولة.\n"
            f"التفاصيل:\n- {detail}"
        )


def _scan_batch_silent(info, dpi: int) -> List[ScannedImage]:
    """مسح ADF بدون حوار — إعدادات بسيطة جداً لتجنب Invalid Parameter."""
    device = info.Connect()
    if int(device.Items.Count) < 1:
        raise ScannerError("لا يوجد عنصر مسح على الجهاز.")

    # لا نضبط إلا FEEDER=1 إن أمكن — بدون دمج أعلام قد تسبب 0x80070057
    _set_prop(device, "Document Handling Select", WIA_FEEDER)

    images: List[ScannedImage] = []
    for page in range(1, 201):
        if page > 1 and not _feeder_has_paper(device):
            break
        try:
            item = device.Items[1]
            # DPI اختياري — تجاهل إن رفض الجهاز القيمة
            _soft_set_dpi(item, dpi)
            image = _transfer_image(item)
        except Exception as exc:
            if page == 1:
                raise
            if _is_paper_empty(exc) or _is_invalid_arg(exc):
                break
            break

        if image is None:
            break
        images.append(_to_scanned(image, page))

    return images


def _scan_with_common_dialog_batch(prefer_feeder: bool = True) -> List[ScannedImage]:
    """
    يعتمد على شاشة تعريف السكنر.
    كثير من أجهزة Canon تسحب الرزمة كاملة عبر هذا الحوار.
    نكرر الاستدعاء طالما هناك ورق/صور.
    """
    dialog = _dispatch("WIA.CommonDialog")
    images: List[ScannedImage] = []

    # أول استدعاء يظهر واجهة السكنر — اختر المغذي هناك إن لزم
    for page in range(1, 201):
        try:
            image = dialog.ShowAcquireImage(
                WIA_DEVICE_SCANNER,  # DeviceType
                WIA_INTENT_COLOR,  # Intent
                0,  # Bias
                WIA_FORMAT_JPEG,  # FormatID
                False,  # AlwaysSelectDevice
                page == 1,  # UseCommonUI — واجهة في الصفحة الأولى فقط
                True,  # CancelError
            )
        except Exception as exc:
            if page == 1:
                # جرّب بدون Format JPEG
                try:
                    image = dialog.ShowAcquireImage(
                        WIA_DEVICE_SCANNER,
                        WIA_INTENT_COLOR,
                        0,
                        WIA_FORMAT_BMP,
                        False,
                        True,
                        True,
                    )
                except Exception as exc2:
                    if _is_cancelled(exc2):
                        raise ScannerError("تم إلغاء المسح.") from exc2
                    raise ScannerError(
                        "تعذر فتح حوار المسح للرزمة.\n"
                        f"التفاصيل: {exc2}"
                    ) from exc2
            else:
                if _is_paper_empty(exc) or _is_cancelled(exc) or _is_invalid_arg(exc):
                    break
                break

        if image is None:
            break
        images.append(_to_scanned(image, page))

        # بعد الصفحة الأولى: بدون UI؛ إن لم يدعم الجهاز التكرار الصامت نتوقف عند ما جُمع
        if page == 1 and prefer_feeder:
            continue

    return images


def _resolve_device_info_unlocked(device_name: Optional[str]):
    devices = _list_wia_devices_unlocked()
    if not devices:
        raise ScannerError(
            "لم يتم العثور على سكنر WIA. تأكد أن الجهاز متصل ويعمل في ويندوز."
        )

    selected = device_name or devices[0].name
    raw_name = selected.replace("[WIA] ", "", 1)

    manager = _dispatch("WIA.DeviceManager")
    info = None
    first_scanner = None
    for index in range(1, int(manager.DeviceInfos.Count) + 1):
        candidate = manager.DeviceInfos(index)
        try:
            if int(candidate.Type) != WIA_DEVICE_SCANNER:
                continue
        except Exception:
            continue
        if first_scanner is None:
            first_scanner = candidate
        if (_prop(candidate, "Name") or "") == raw_name:
            info = candidate
            break

    info = info or first_scanner
    if info is None:
        raise ScannerError("تعذر الاتصال بالسكنر عبر WIA.")
    return info


def _transfer_image(item):
    last_error = None
    for fmt in (WIA_FORMAT_JPEG, WIA_FORMAT_PNG, WIA_FORMAT_BMP, None):
        try:
            if fmt is None:
                return item.Transfer()
            return item.Transfer(fmt)
        except Exception as exc:
            last_error = exc
            continue
    raise last_error or ScannerError("فشل Transfer")


def _soft_set_dpi(item, dpi: int) -> None:
    """ضبط الدقة بهدوء — بعض الأجهزة ترفض قيماً معيّنة (Invalid Parameter)."""
    for candidate in (int(dpi), 300, 200):
        ok = True
        for name in (WIA_HORIZONTAL_RESOLUTION, WIA_VERTICAL_RESOLUTION):
            if not _set_prop(item, name, candidate):
                ok = False
        if ok:
            break
    _set_prop(item, WIA_CURRENT_INTENT, WIA_INTENT_COLOR)


def _to_scanned(image, page: int) -> ScannedImage:
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    return ScannedImage(
        data=_wia_image_to_jpeg_bytes(image),
        mime_type="image/jpeg",
        file_name=f"wia-{stamp}-{page}.jpg",
    )


def _feeder_has_paper(device) -> bool:
    status = _get_prop_int(device, "Document Handling Status")
    if status is None:
        return True
    return bool(status & WIA_FEED_READY)


def _get_prop_int(obj, name: str) -> Optional[int]:
    try:
        return int(obj.Properties(name).Value)
    except Exception:
        return None


def _set_prop(obj, name: str, value) -> bool:
    try:
        obj.Properties(name).Value = value
        return True
    except Exception:
        return False


def _is_invalid_arg(exc: Exception) -> bool:
    text = str(exc).lower()
    if "parameter is incorrect" in text or "0x80070057" in text:
        return True
    hr = getattr(exc, "hresult", None)
    try:
        if int(hr) == -2147024809:
            return True
    except Exception:
        pass
    # أحياناً يكون داخل args
    try:
        for arg in getattr(exc, "args", ()):
            if arg == -2147024809 or arg == 0x80070057:
                return True
            if isinstance(arg, tuple):
                for nested in arg:
                    if nested == -2147024809:
                        return True
    except Exception:
        pass
    return False


def _is_paper_empty(exc: Exception) -> bool:
    text = str(exc).lower()
    if "empty" in text or "no paper" in text or "out of paper" in text:
        return True
    for code in PAPER_EMPTY_CODES:
        if code.lower() in text:
            return True
    hr = getattr(exc, "hresult", None)
    try:
        if int(hr) in (-2145320957, -2145320958, -2145320955):
            return True
    except Exception:
        pass
    return False


def _is_cancelled(exc: Exception) -> bool:
    text = str(exc).lower()
    return "cancel" in text or "0x80210064" in text


def _wia_image_to_jpeg_bytes(image) -> bytes:
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "scan.jpg"
        try:
            image.SaveFile(str(path))
        except Exception:
            path = Path(tmp) / "scan.bmp"
            image.SaveFile(str(path))

        candidates = list(Path(tmp).glob("scan*"))
        if not candidates:
            raise ScannerError("تعذر حفظ صورة WIA مؤقتاً.")
        file_path = max(candidates, key=lambda p: p.stat().st_size)
        with Image.open(file_path) as img:
            if img.mode != "RGB":
                img = img.convert("RGB")
            buf = io.BytesIO()
            img.save(buf, format="JPEG", quality=90, optimize=True)
            return buf.getvalue()


def _prop(info, name: str) -> Optional[str]:
    try:
        return str(info.Properties(name).Value)
    except Exception:
        try:
            props = info.Properties
            for index in range(1, int(props.Count) + 1):
                prop = props(index)
                if str(getattr(prop, "Name", "")).lower() == name.lower():
                    return str(prop.Value)
        except Exception:
            return None
    return None
