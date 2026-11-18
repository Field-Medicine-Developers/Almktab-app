"""مسح عبر WIA المدمج في ويندوز — لا يحتاج twaindsm.dll."""

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
    show_ui: bool = True,
) -> List[ScannedImage]:
    if show_ui:
        return _scan_with_common_dialog()

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

    device = info.Connect()
    if device.Items.Count < 1:
        raise ScannerError("السكنر لا يوفّر عنصر مسح عبر WIA.")

    item = device.Items[1]
    _set_item_dpi(item, dpi)
    _try_set_feeder(device, use_feeder)

    images: List[ScannedImage] = []
    page = 0
    while True:
        page += 1
        try:
            image = item.Transfer(WIA_FORMAT_JPEG)
        except Exception:
            try:
                image = item.Transfer(WIA_FORMAT_BMP)
            except Exception as exc:
                if page == 1:
                    raise ScannerError(f"فشل نقل الصورة من WIA: {exc}") from exc
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
        if not use_feeder:
            break
        try:
            item = device.Items[1]
            _set_item_dpi(item, dpi)
        except Exception:
            break
        if page >= 50:
            break

    if not images:
        raise ScannerError("لم يتم استلام أي صورة من WIA.")
    return images


def _scan_with_common_dialog() -> List[ScannedImage]:
    dialog = _dispatch("WIA.CommonDialog")
    images: List[ScannedImage] = []
    try:
        image = dialog.ShowAcquireImage(
            WIA_DEVICE_SCANNER,
            WIA_INTENT_COLOR,
            0,
            WIA_FORMAT_JPEG,
            False,
            True,
            False,
        )
    except Exception as exc:
        message = str(exc)
        if "cancel" in message.lower() or "0x80210064" in message.lower():
            raise ScannerError("تم إلغاء المسح.") from exc
        raise ScannerError(
            "تعذر فتح حوار المسح. تأكد أن السكنر متصل ويعمل في برامج أخرى.\n"
            f"التفاصيل: {exc}"
        ) from exc

    if image is None:
        raise ScannerError("لم يتم استلام أي صورة من حوار المسح.")

    data = _wia_image_to_jpeg_bytes(image)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    images.append(
        ScannedImage(
            data=data,
            mime_type="image/jpeg",
            file_name=f"wia-{stamp}-1.jpg",
        )
    )
    return images


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


def _try_set_feeder(device, use_feeder: bool) -> None:
    if not use_feeder:
        return
    for name in ("Document Handling Select", "Feeder", "Sheet Feeder"):
        try:
            device.Properties(name).Value = 1
        except Exception:
            pass
