#!/usr/bin/env python3
"""Generate PNG favicons from SVG using cairosvg."""

import sys
from pathlib import Path

try:
    import cairosvg
except ImportError:
    print("Error: cairosvg not installed.")
    print("Install with: pip install cairosvg")
    print("\nAlternatively, use one of these methods:")
    print("1. ImageMagick: convert -background none favicon.svg -resize 32x32 favicon-32x32.png")
    print("2. Online converter: https://cloudconvert.com/svg-to-png")
    sys.exit(1)

def generate_favicon(svg_path: Path, output_path: Path, size: int):
    """Generate PNG favicon from SVG."""
    print(f"Generating {output_path.name} ({size}x{size})...")

    cairosvg.svg2png(
        url=str(svg_path),
        write_to=str(output_path),
        output_width=size,
        output_height=size
    )
    print(f"✓ Created {output_path}")

def main():
    """Generate all favicon sizes."""
    img_dir = Path(__file__).parent / "static" / "img"
    svg_path = img_dir / "favicon.svg"

    if not svg_path.exists():
        print(f"Error: {svg_path} not found")
        sys.exit(1)

    # Generate different sizes
    sizes = [
        (16, "favicon-16x16.png"),
        (32, "favicon-32x32.png"),
    ]

    for size, filename in sizes:
        output_path = img_dir / filename
        generate_favicon(svg_path, output_path, size)

    print("\n✓ All favicons generated successfully!")
    print("\nYou can now build and deploy the application.")

if __name__ == "__main__":
    main()
