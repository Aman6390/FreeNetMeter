"""Generate multi-resolution app.ico for FreeNetMeter Windows packaging."""

from __future__ import annotations

import sys
from pathlib import Path

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from PIL import Image  # noqa: E402
from PyQt6.QtGui import QImage  # noqa: E402
from PyQt6.QtWidgets import QApplication  # noqa: E402

from ui.assets import create_app_pixmap  # noqa: E402


def generate_ico(output_path: Path | str = "app.ico") -> None:
    """Generate high-resolution Windows icon file containing all standard mipmaps."""
    _qapp = QApplication.instance() or QApplication(sys.argv)
    _ = _qapp
    sizes = [16, 24, 32, 48, 64, 128, 256]
    pil_images: list[Image.Image] = []

    for s in sizes:
        pix = create_app_pixmap(s)
        img = pix.toImage().convertToFormat(QImage.Format.Format_RGBA8888)
        ptr = img.bits()
        if ptr is not None:
            ptr.setsize(img.sizeInBytes())
            pil_images.append(Image.frombytes("RGBA", (s, s), bytes(ptr)))

    if pil_images:
        largest = pil_images[-1]
        largest.save(
            str(output_path),
            format="ICO",
            sizes=[(s, s) for s in sizes],
        )
        print(f"Generated {output_path} with sizes: {sizes}")


if __name__ == "__main__":
    generate_ico()
