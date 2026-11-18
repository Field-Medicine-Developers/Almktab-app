"""مسح مباشر عبر TWAIN على ويندوز."""

from __future__ import annotations

import io
import platform
import tempfile
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Sequence

from PIL import Image


@dataclass
class ScannerDevice:
    name: str
    product_family: str = ""


@dataclass
class ScannedImage:
    data: bytes
    mime_type: str
    file_name: str


class ScannerError(Exception):
    pass


def is_windows() -> bool:
    return platform.system().lower() == "windows"


def _import_twain():
    if not is_windows():
        raise ScannerError(
            "المسح المباشر متاح على ويندوز فقط. شغّل التطبيق على جهاز ويندوز متصل بالسكنر."
        )
    try:
        import twain  # type: ignore
    except ImportError as exc:
        raise ScannerError(
            "مكتبة TWAIN غير مثبتة. نفّذ: pip install pytwain"
        ) from exc
    return twain


def list_devices() -> List[ScannerDevice]:
    twain = _import_twain()
    source_manager = None
    try:
        source_manager = twain.SourceManager(0)
        names = list(source_manager.GetSourceList() or [])
        devices = [ScannerDevice(name=name) for name in names]
        devices.sort(key=lambda d: d.name.lower())
        return devices
    except ScannerError:
        raise
    except Exception as exc:
        raise ScannerError(f"تعذر قراءة قائمة السكنرات: {exc}") from exc
    finally:
        _safe_destroy(source_manager)


def prefer_device_name(devices: Sequence[ScannerDevice]) -> str:
    if not devices:
        return ""
    for device in devices:
        if "canon" in device.name.lower():
            return device.name
    return devices[0].name


def scan(
    device_name: Optional[str] = None,
    dpi: int = 300,
    use_feeder: bool = True,
    show_ui: bool = True,
) -> List[ScannedImage]:
    """
    يفتح مصدر TWAIN ويمسح صفحة أو أكثر (ADF إن وُجد).
    يعيد قائمة صور JPEG.
    """
    twain = _import_twain()
    source_manager = None
    source = None
    images: List[ScannedImage] = []

    try:
        source_manager = twain.SourceManager(0)
        names = list(source_manager.GetSourceList() or [])
        if not names:
            raise ScannerError(
                "لم يتم العثور على أي سكنر TWAIN. تأكد من تثبيت التعريف."
            )

        selected = device_name if device_name in names else None
        if not selected:
            preferred = prefer_device_name([ScannerDevice(n) for n in names])
            selected = preferred or names[0]

        source = source_manager.OpenSource(selected)
        _configure_source(twain, source, dpi=dpi, use_feeder=use_feeder)

        # RequestAcquire(show_ui, modal)
        source.RequestAcquire(1 if show_ui else 0, 1)

        index = 0
        while True:
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
                more = bool(result[1])

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
                            file_name=f"scan-{stamp}-{index}.jpg",
                        )
                    )
            finally:
                if bmp_path and bmp_path.exists():
                    try:
                        bmp_path.unlink()
                    except OSError:
                        pass

            if not use_feeder or not more:
                break

        if not images:
            raise ScannerError("لم يتم استلام أي صورة من السكنر.")
        return images
    except ScannerError:
        raise
    except Exception as exc:
        raise ScannerError(f"فشل المسح: {exc}") from exc
    finally:
        _safe_destroy(source)
        _safe_destroy(source_manager)


def _configure_source(twain, source, dpi: int, use_feeder: bool) -> None:
    # الصيغ تختلف قليلاً بين إصدارات pytwain — نجرب أكثر من أسلوب
    attempts = [
        lambda: source.SetCapability(
            twain.ICAP_PIXELTYPE, twain.TWTY_UINT16, twain.TWPT_RGB
        ),
        lambda: source.SetCapability("ICAP_PIXELTYPE", twain.TWPT_RGB),
    ]
    for attempt in attempts:
        try:
            attempt()
            break
        except Exception:
            continue

    for attempt in (
        lambda: source.SetCapability(
            twain.ICAP_XRESOLUTION, twain.TWTY_FIX32, float(dpi)
        ),
        lambda: source.SetCapability("ICAP_XRESOLUTION", float(dpi)),
    ):
        try:
            attempt()
            break
        except Exception:
            continue

    for attempt in (
        lambda: source.SetCapability(
            twain.ICAP_YRESOLUTION, twain.TWTY_FIX32, float(dpi)
        ),
        lambda: source.SetCapability("ICAP_YRESOLUTION", float(dpi)),
    ):
        try:
            attempt()
            break
        except Exception:
            continue

    if use_feeder:
        for attempt in (
            lambda: source.SetCapability(
                twain.CAP_FEEDERENABLED, twain.TWTY_BOOL, True
            ),
            lambda: source.SetCapability("CAP_FEEDERENABLED", True),
        ):
            try:
                attempt()
                break
            except Exception:
                continue
        for attempt in (
            lambda: source.SetCapability(twain.CAP_AUTOFEED, twain.TWTY_BOOL, True),
            lambda: source.SetCapability("CAP_AUTOFEED", True),
        ):
            try:
                attempt()
                break
            except Exception:
                continue


def _safe_destroy(obj) -> None:
    if obj is None:
        return
    try:
        obj.destroy()
    except Exception:
        pass
