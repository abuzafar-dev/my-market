"""Placeholder product photos for the demo seed commands.

Generated locally with Pillow (no network, no stock-photo licensing): a
category-coloured card with the product's name on it. One file per distinct
name is written under ``media/products/demo/`` and reused, so 500 seeded
products with ~100 base names only produce ~100 small JPEGs.
"""

import hashlib
import io
from pathlib import Path

from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.utils.text import slugify
from PIL import Image, ImageDraw, ImageFont

_SIZE = 480

# Background colours per category; anything unlisted gets a colour derived
# from its name so it's still stable between runs.
_CATEGORY_COLOURS = {
    "Oziq-ovqat": (214, 137, 16),
    "Ichimliklar": (33, 118, 199),
    "Non mahsulotlari": (176, 112, 58),
    "Sut mahsulotlari": (90, 160, 200),
    "Go'sht mahsulotlari": (178, 45, 48),
    "Meva-sabzavot": (56, 152, 70),
    "Maishiy kimyo": (120, 82, 190),
    "Gigiena": (40, 160, 160),
    "Shirinliklar": (210, 70, 140),
    "Boshqa": (95, 105, 120),
}

_FONT_CANDIDATES = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/noto/NotoSans-Bold.ttf",
    "/usr/share/fonts/TTF/DejaVuSans-Bold.ttf",
]


def _font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    for path in _FONT_CANDIDATES:
        if Path(path).exists():
            return ImageFont.truetype(path, size)
    # Pillow's bundled font — present even in a slim Docker image.
    return ImageFont.load_default(size=size)


def _colour(category: str) -> tuple[int, int, int]:
    if category in _CATEGORY_COLOURS:
        return _CATEGORY_COLOURS[category]
    digest = hashlib.md5(category.encode(), usedforsecurity=False).digest()
    return (60 + digest[0] % 150, 60 + digest[1] % 150, 60 + digest[2] % 150)


def _wrap(draw: ImageDraw.ImageDraw, text: str, font, max_width: int) -> list[str]:
    lines: list[str] = []
    current = ""
    for word in text.split():
        candidate = f"{current} {word}".strip()
        if draw.textlength(candidate, font=font) <= max_width or not current:
            current = candidate
        else:
            lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines


def _render(title: str, category: str) -> bytes:
    base = _colour(category)
    light = tuple(min(255, c + 70) for c in base)
    image = Image.new("RGB", (_SIZE, _SIZE), base)
    draw = ImageDraw.Draw(image)

    # Soft vertical gradient so the cards don't look like flat swatches.
    for y in range(_SIZE):
        t = y / _SIZE
        row = tuple(int(light[i] * (1 - t) + base[i] * t) for i in range(3))
        draw.line([(0, y), (_SIZE, y)], fill=row)

    # Big initial as a watermark-style "product icon".
    initial_font = _font(260)
    initial = title[:1].upper()
    box = draw.textbbox((0, 0), initial, font=initial_font)
    draw.text(
        ((_SIZE - (box[2] - box[0])) / 2 - box[0], 40 - box[1]),
        initial,
        font=initial_font,
        fill=tuple(min(255, c + 40) for c in base),
    )

    title_font = _font(44)
    lines = _wrap(draw, title, title_font, _SIZE - 60)[:3]
    y = _SIZE - 70 - len(lines) * 52
    for line in lines:
        width = draw.textlength(line, font=title_font)
        draw.text(((_SIZE - width) / 2, y), line, font=title_font, fill="white")
        y += 52

    category_font = _font(24)
    width = draw.textlength(category, font=category_font)
    draw.text(((_SIZE - width) / 2, _SIZE - 50), category, font=category_font, fill=(255, 255, 255))

    buffer = io.BytesIO()
    image.save(buffer, format="JPEG", quality=85)
    return buffer.getvalue()


def demo_image(title: str, category: str) -> str:
    """Return the storage path of the demo photo for ``title``, creating it
    on first use. Assign the result straight to ``Product.image``."""
    path = f"products/demo/{slugify(f'{category}-{title}') or 'item'}.jpg"
    if not default_storage.exists(path):
        default_storage.save(path, ContentFile(_render(title, category)))
    return path
