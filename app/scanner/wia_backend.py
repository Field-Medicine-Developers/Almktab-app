"""مسح عبر WIA المدمج في ويندوز — دعم ADF لعدة صفحات متتالية."""

from __future__ import annotations

import io
import tempfile
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from PIL import Image

from app.scanner.models import ScannerDevice, ScannerError, ScannedImage

WIA_DEVICE_SCANNER = 1
WIA_INTENT_COLOR = 1
WIA_FORMAT_JPEG = "{B96B3CAE-0728-11D3-9D7B-0000F81EF32E}"
WIA_FORMAT_BMP = "{B96B3CAB-0728-11D3-9D7B-0000F81EF32E}"
WIA_HORIZONTAL_RESOLUTION = "Horizontal Resolution"
WIA_VERTICAL_RESOLUTION = "Vertical Resolution"
WIA_CURRENT_INTENT = "Current Intent"

# Document Handling Select
WIA_FEEDER = 0x001
WIA_FLATBED = 0x002
WIA_DUPLEX = 0x004
WIA_FRONT_ONLY = 0x020
WIA_NEXT_PAGE = 0x080

# Document Handling Status
WIA_FEED_READY = 0x01

# أخطاء شائعة لانتهاء الورق / الإلغاء
PAPER_EMPTY_CODES = {
    "0x80210003",  # WIA_ERROR_PAPER_EMPTY
    "0x80210002",  # WIA_ERROR_PAPER_JAM (نتوقف أيضاً)
    "0x80210001",  # WIA_ERROR_COVER_OPEN
    "0x80210006",  # WIA_ERROR_PAPER_PROBLEM
    "0x80210064",  # user cancelled
}


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
    مسح مستمر:
    - use_feeder=True: يسحب كل الأوراق من ADF حتى نفاد الدرج
    - use_feeder=False: صفحة واحدة (اللوح الزجاجي أو ورقة واحدة)
    """
    info = _resolve_device_info(device_name)
    device = info.Connect()
    if int(device.Items.Count) < 1:
        raise ScannerError("السكنر لا يوفّر عنصر مسح عبر WIA.")

    _configure_document_handling(device, use_feeder=use_feeder)
    item = device.Items[1]
    _set_item_dpi(item, dpi)

    if use_feeder:
        images = _scan_feeder_continuous(device, item, dpi=dpi, show_ui=show_ui)
    else:
        images = _scan_single_page(device, item, dpi=dpi, show_ui=show_ui)

    if not images:
        raise ScannerError(
            "لم يتم استلام أي صورة.\n"
            "ضع الأوراق في وحدة التغذية (ADF) وتأكد أن خيار «التغذية ADF» مفعّل."
        )
    return images


def _resolve_device_info(device_name: Optional[str]):
    devices = list_wia_devices()
    if not devices:
        raise ScannerError(
            "لم يتم العثور على سكنر WIA. تأكد أن الجهاز متصل ويعمل في ويندوز."
        )

    selected = device_name or devices[0].name
    raw_name = selected.replace("[WIA] ", "", 1)

    manager = _dispatch("WIA.DeviceManager")
    info = None
    for index in range(1, int(manager.DeviceInfos.Count) + 1):
        candidate = manager.DeviceInfos(index)
        try:
            if int(candidate.Type) != WIA_DEVICE_SCANNER:
                continue
        except Exception:
            continue
        if (_prop(candidate, "Name") or "") == raw_name:
            info = candidate
            break

    if info is None:
        for index in range(1, int(manager.DeviceInfos.Count) + 1):
            candidate = manager.DeviceInfos(index)
            try:
                if int(candidate.Type) == WIA_DEVICE_SCANNER:
                    info = candidate
                    break
            except Exception:
                continue

    if info is None:
        raise ScannerError("تعذر الاتصال بالسكنر عبر WIA.")
    return info


def _configure_document_handling(device, use_feeder: bool) -> None:
    if use_feeder:
        # FEEDER + FRONT_ONLY شائع لـ ADF أحادي الوجه
        for value in (
            WIA_FEEDER | WIA_FRONT_ONLY,
            WIA_FEEDER,
            1,
        ):
            if _set_prop(device, "Document Handling Select", value):
                break
        _set_prop(device, "Pages", 0)  # ALL_PAGES إن وُجد
        _set_prop(device, "Sheet Feeder Registration", 0)
    else:
        for value in (WIA_FLATBED, 2):
            if _set_prop(device, "Document Handling Select", value):
                break
        _set_prop(device, "Pages", 1)


def _scan_feeder_continuous(device, item, dpi: int, show_ui: bool) -> List[ScannedImage]:
    """يسحب الصفحات واحدة تلو الأخرى حتى يفرغ ADF."""
    images: List[ScannedImage] = []
    dialog = None
    if show_ui:
        try:
            dialog = _dispatch("WIA.CommonDialog")
        except Exception:
            dialog = None

    max_pages = 200
    for page in range(1, max_pages + 1):
        # إن لم يعد هناك ورق في المغذي — توقف بهدوء بعد أول صفحة ناجحة
        if page > 1 and not _feeder_has_paper(device):
            break

        try:
            item = device.Items[1]
            _set_item_dpi(item, dpi)
            # بعض الأجهزة تحتاج إعادة تفعيل NEXT_PAGE بين الصفحات
            if page > 1:
                current = _get_prop_int(device, "Document Handling Select")
                if current is not None:
                    _set_prop(device, "Document Handling Select", current | WIA_NEXT_PAGE)
        except Exception:
            if page == 1:
                raise
            break

        try:
            if dialog is not None and page == 1 and show_ui:
                # واجهة اختيار/معاينة لأول صفحة فقط ثم نستمر تلقائياً
                image = dialog.ShowTransfer(item, WIA_FORMAT_JPEG, False)
            else:
                image = _transfer_image(item)
        except Exception as exc:
            if _is_paper_empty(exc):
                break
            if page == 1:
                # إن فشلت الدفعة الصامتة مع واجهة، لا نرجع لصفحة واحدة فقط
                raise ScannerError(
                    "فشل بدء المسح المستمر من ADF.\n"
                    "ضع رزمة الأوراق في المغذي وتأكد أن السكنر جاهز.\n"
                    f"التفاصيل: {exc}"
                ) from exc
            break

        if image is None:
            break

        data = _wia_image_to_jpeg_bytes(image)
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        images.append(
            ScannedImage(
                data=data,
                mime_type="image/jpeg",
                file_name=f"wia-{stamp}-{page}.jpg",
            )
        )

    return images


def _scan_single_page(device, item, dpi: int, show_ui: bool) -> List[ScannedImage]:
    _set_item_dpi(item, dpi)
    try:
        if show_ui:
            dialog = _dispatch("WIA.CommonDialog")
            image = dialog.ShowTransfer(item, WIA_FORMAT_JPEG, False)
        else:
            image = _transfer_image(item)
    except Exception as exc:
        if _is_cancelled(exc):
            raise ScannerError("تم إلغاء المسح.") from exc
        raise ScannerError(f"فشل مسح الصفحة: {exc}") from exc

    if image is None:
        return []
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    return [
        ScannedImage(
            data=_wia_image_to_jpeg_bytes(image),
            mime_type="image/jpeg",
            file_name=f"wia-{stamp}-1.jpg",
        )
    ]


def _transfer_image(item):
    try:
        return item.Transfer(WIA_FORMAT_JPEG)
    except Exception:
        return item.Transfer(WIA_FORMAT_BMP)


def _feeder_has_paper(device) -> bool:
    status = _get_prop_int(device, "Document Handling Status")
    if status is None:
        # إن لم تُعرف الحالة نفترض احتمال وجود ورق ونترك Transfer يقرر
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


def _is_paper_empty(exc: Exception) -> bool:
    text = str(exc).lower()
    if "empty" in text or "no paper" in text or "out of paper" in text:
        return True
    for code in PAPER_EMPTY_CODES:
        if code.lower() in text:
            return True
    # winerror / hresult
    hr = getattr(exc, "hresult", None) or getattr(exc, "args", [None])[0]
    try:
        if int(hr) in (-2145320957, -2145320958, -2145320955):  # paper empty / jam-ish
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


def _set_item_dpi(item, dpi: int) -> None:
    for name in (WIA_HORIZONTAL_RESOLUTION, WIA_VERTICAL_RESOLUTION):
        try:
            item.Properties(name).Value = int(dpi)
        except Exception:
            pass
    try:
        item.Properties(WIA_CURRENT_INTENT).Value = WIA_INTENT_COLOR
    except Exception:
        pass
