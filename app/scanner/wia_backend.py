"""مسح عبر WIA — ADF متعدد الصفحات بنمط إعادة الاتصال لكل صفحة."""

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

# WIA property IDs (أرقام — أوثق من الأسماء مع بعض التعريفات)
WIA_DPS_PAGES = 3086
WIA_DPS_DOCUMENT_HANDLING_STATUS = 3087
WIA_DPS_DOCUMENT_HANDLING_SELECT = 3088
WIA_IPA_DATATYPE = 4103
WIA_IPA_DEPTH = 4104
WIA_IPS_CUR_INTENT = 6146
WIA_IPS_XRES = 6147
WIA_IPS_YRES = 6148

FEEDER = 0x001
FLATBED = 0x002
FEED_READY = 0x001

_com_state = threading.local()


@contextmanager
def _com_initialized() -> Iterator[None]:
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
            "مكتبة pywin32 غير مثبتة. من واجهة التنصيب اضغط «تنصيب المتطلبات»."
        ) from exc
    return win32com.client.Dispatch(prog_id)


def list_wia_devices() -> List[ScannerDevice]:
    with _com_initialized():
        return _list_devices_unlocked()


def _list_devices_unlocked() -> List[ScannerDevice]:
    manager = _dispatch("WIA.DeviceManager")
    devices: List[ScannerDevice] = []
    for index in range(1, int(manager.DeviceInfos.Count) + 1):
        info = manager.DeviceInfos(index)
        try:
            if int(info.Type) != WIA_DEVICE_SCANNER:
                continue
        except Exception:
            continue
        name = _prop_by_name(info, "Name") or f"Scanner-{index}"
        manufacturer = _prop_by_name(info, "Manufacturer") or "WIA"
        device_id = _prop_by_name(info, "Unique Device ID") or ""
        devices.append(
            ScannerDevice(
                name=f"[WIA] {name}",
                product_family=f"{manufacturer}|{device_id}",
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
    with _com_initialized():
        info = _resolve_info(device_name)
        device_id = _prop_by_name(info, "Unique Device ID") or ""

        if use_feeder:
            images = _scan_adf_reconnect_loop(device_id, info, dpi=dpi)
            if images:
                return images
            # محاولة أخيرة بحوار لمرة واحدة ثم متابعة صامتة
            images = _scan_adf_reconnect_loop(device_id, info, dpi=dpi, use_dialog_first=True)
            if images:
                return images
            raise ScannerError(
                "تعذر مسح الرزمة عبر ADF.\n"
                "تأكد أن الأوراق في المغذي، والجهاز متصل بـ USB (وليس WSD فقط)، "
                "ثم أعد المحاولة."
            )

        # صفحة واحدة
        device = info.Connect()
        item = device.Items[1]
        _prepare_item(item, dpi)
        image = _transfer(item, use_dialog=show_ui)
        if image is None:
            raise ScannerError("لم يتم استلام صورة.")
        return [_to_scanned(image, 1)]


def _scan_adf_reconnect_loop(
    device_id: str,
    first_info,
    dpi: int,
    use_dialog_first: bool = False,
) -> List[ScannedImage]:
    """
    النمط الموثوق لمغذّي الأوراق:
    - إعادة Connect لكل صفحة
    - تخزين Item ثم ضبط الخصائص
    - Pages=1 لكل نقل
    - التحقق من FEED_READY قبل الصفحة التالية
    """
    images: List[ScannedImage] = []
    dialog = _dispatch("WIA.CommonDialog")

    for page in range(1, 201):
        # أعد إيجاد الجهاز والاتصال في كل دورة (مهم مع ADF)
        info = _find_info_by_id(device_id) or first_info
        try:
            device = info.Connect()
        except Exception as exc:
            if page == 1:
                raise ScannerError(f"تعذر الاتصال بالسكنر: {exc}") from exc
            break

        # فعّل المغذي فقط — بدون أعلام مركّبة تسبب Invalid Parameter
        _set_prop_id(device, WIA_DPS_DOCUMENT_HANDLING_SELECT, FEEDER)
        _set_prop_id(device, WIA_DPS_PAGES, 1)

        # قبل الصفحة الثانية: توقف إن لم يعد هناك ورق
        if page > 1 and not _has_feed_ready(device):
            break

        try:
            # مهم: خزّن Item ثم عدّل خصائصه (لا تستخدم Items[1] مباشرة مرتين)
            item = device.Items[1]
            _prepare_item(item, dpi)

            use_dialog = use_dialog_first and page == 1
            if use_dialog:
                image = dialog.ShowTransfer(item, WIA_FORMAT_JPEG, False)
            else:
                image = _transfer(item, use_dialog=False)
        except Exception as exc:
            if page == 1:
                # إن فشل النقل الصامت، اترك الحلقة تُعاد مع dialog لاحقاً
                raise
            if _is_done(exc):
                break
            break

        if image is None:
            break

        images.append(_to_scanned(image, page))

        # حرّر المراجع قبل الدورة التالية
        image = None
        item = None
        device = None

    return images


def _prepare_item(item, dpi: int) -> None:
    # Intent / DPI بأرقام الخصائص
    _set_prop_id(item, WIA_IPS_CUR_INTENT, WIA_INTENT_COLOR)
    for value in (int(dpi), 300, 200):
        ok_x = _set_prop_id(item, WIA_IPS_XRES, value)
        ok_y = _set_prop_id(item, WIA_IPS_YRES, value)
        if ok_x or ok_y:
            break


def _transfer(item, use_dialog: bool = False):
    if use_dialog:
        dialog = _dispatch("WIA.CommonDialog")
        try:
            return dialog.ShowTransfer(item, WIA_FORMAT_JPEG, False)
        except Exception:
            return dialog.ShowTransfer(item, WIA_FORMAT_BMP, False)

    last = None
    for fmt in (WIA_FORMAT_JPEG, WIA_FORMAT_PNG, WIA_FORMAT_BMP, None):
        try:
            return item.Transfer() if fmt is None else item.Transfer(fmt)
        except Exception as exc:
            last = exc
            continue
    raise last or ScannerError("فشل Transfer")


def _has_feed_ready(device) -> bool:
    select = _get_prop_id(device, WIA_DPS_DOCUMENT_HANDLING_SELECT)
    status = _get_prop_id(device, WIA_DPS_DOCUMENT_HANDLING_STATUS)
    # إن لم تتوفر الخصائص نفترض وجود ورق ونترك Transfer يقرر
    if select is None or status is None:
        return True
    if (int(select) & FEEDER) == 0:
        return False
    return (int(status) & FEED_READY) != 0


def _resolve_info(device_name: Optional[str]):
    devices = _list_devices_unlocked()
    if not devices:
        raise ScannerError("لم يتم العثور على سكنر WIA.")

    selected = (device_name or devices[0].name).replace("[WIA] ", "", 1)
    manager = _dispatch("WIA.DeviceManager")
    first = None
    for index in range(1, int(manager.DeviceInfos.Count) + 1):
        info = manager.DeviceInfos(index)
        try:
            if int(info.Type) != WIA_DEVICE_SCANNER:
                continue
        except Exception:
            continue
        if first is None:
            first = info
        name = _prop_by_name(info, "Name") or ""
        if name == selected or selected.lower() in name.lower():
            return info
    if first is None:
        raise ScannerError("تعذر الاتصال بالسكنر.")
    return first


def _find_info_by_id(device_id: str):
    if not device_id:
        return None
    manager = _dispatch("WIA.DeviceManager")
    for index in range(1, int(manager.DeviceInfos.Count) + 1):
        info = manager.DeviceInfos(index)
        if (_prop_by_name(info, "Unique Device ID") or "") == device_id:
            return info
    return None


def _set_prop_id(obj, prop_id: int, value) -> bool:
    try:
        obj.Properties.Item(prop_id).Value = value
        return True
    except Exception:
        pass
    # بعض التعريفات تقبل النص الرقمي
    try:
        obj.Properties.Item(str(prop_id)).Value = value
        return True
    except Exception:
        return False


def _get_prop_id(obj, prop_id: int):
    try:
        return obj.Properties.Item(prop_id).Value
    except Exception:
        try:
            return obj.Properties.Item(str(prop_id)).Value
        except Exception:
            return None


def _prop_by_name(info, name: str) -> Optional[str]:
    try:
        return str(info.Properties(name).Value)
    except Exception:
        try:
            for index in range(1, int(info.Properties.Count) + 1):
                prop = info.Properties(index)
                if str(getattr(prop, "Name", "")).lower() == name.lower():
                    return str(prop.Value)
        except Exception:
            return None
    return None


def _to_scanned(image, page: int) -> ScannedImage:
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    return ScannedImage(
        data=_wia_image_to_jpeg_bytes(image),
        mime_type="image/jpeg",
        file_name=f"wia-{stamp}-{page}.jpg",
    )


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
            raise ScannerError("تعذر حفظ صورة WIA.")
        file_path = max(candidates, key=lambda p: p.stat().st_size)
        with Image.open(file_path) as img:
            if img.mode != "RGB":
                img = img.convert("RGB")
            buf = io.BytesIO()
            img.save(buf, format="JPEG", quality=90, optimize=True)
            return buf.getvalue()


def _is_done(exc: Exception) -> bool:
    text = str(exc).lower()
    if any(x in text for x in ("empty", "cancel", "no paper", "0x80210003", "0x80210064")):
        return True
    if "parameter is incorrect" in text or "0x80070057" in text:
        return True
    return False
