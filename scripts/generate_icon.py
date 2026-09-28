"""Generate JARVIS application icon.

Creates a simple .ico file for the JARVIS desktop application.
Run this script to generate the icon before building.
"""

from __future__ import annotations

import sys
from pathlib import Path


def generate_icon(output_path: Path | None = None) -> Path:
    """Generate a JARVIS application icon."""
    try:
        from PIL import Image, ImageDraw, ImageFont
    except ImportError:
        print("ERROR: Pillow not installed. Run: pip install pillow")
        sys.exit(1)

    if output_path is None:
        output_path = Path(__file__).resolve().parent / "assets" / "icons" / "jarvis.ico"

    output_path.parent.mkdir(parents=True, exist_ok=True)

    sizes = [16, 32, 48, 64, 128, 256]
    images = []

    for size in sizes:
        # Create RGBA image
        img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)

        # Draw circle background (dark)
        margin = max(1, size // 16)
        draw.ellipse(
            [margin, margin, size - margin, size - margin],
            fill=(20, 20, 30, 255),
        )

        # Draw accent circle
        accent_margin = max(2, size // 8)
        draw.ellipse(
            [accent_margin, accent_margin, size - accent_margin, size - accent_margin],
            fill=(61, 255, 176, 255),  # #3dffb0
        )

        # Draw inner dark circle
        inner_margin = max(4, size // 5)
        draw.ellipse(
            [inner_margin, inner_margin, size - inner_margin, size - inner_margin],
            fill=(20, 20, 30, 255),
        )

        # Draw "J" letter
        text_size = max(8, size // 3)
        try:
            font = ImageFont.truetype("arial.ttf", text_size)
        except (IOError, OSError):
            font = ImageFont.load_default()

        # Center the text
        bbox = draw.textbbox((0, 0), "J", font=font)
        text_w = bbox[2] - bbox[0]
        text_h = bbox[3] - bbox[1]
        x = (size - text_w) // 2
        y = (size - text_h) // 2

        draw.text((x, y), "J", fill=(61, 255, 176, 255), font=font)

        images.append(img)

    # Save as .ico with multiple sizes
    if images:
        # Use the largest image as the base
        images[0].save(
            output_path,
            format="ICO",
            sizes=[(s, s) for s in sizes],
            append_images=images[1:],
        )
        print(f"Icon generated: {output_path}")
        return output_path

    raise RuntimeError("Failed to generate icon")


if __name__ == "__main__":
    generate_icon()
