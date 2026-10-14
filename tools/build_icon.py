"""Regenerate the WinNAT UI icon set from the SVG sources in assets/.

Development-only (needs: pip install cairosvg pillow). The generated files are
committed, so the Windows build does not depend on these packages.

  python tools/build_icon.py
"""
import io
import pathlib

import cairosvg
from PIL import Image

ASSETS = pathlib.Path(__file__).resolve().parent.parent / "assets"
SIZES = [16, 20, 24, 32, 40, 48, 64, 96, 128, 256]


def source(size):
    # Three drawings tuned for legibility: bolder/simpler shapes at small sizes.
    name = "winnat-ui-small.svg" if size <= 20 else "winnat-ui-medium.svg" if size <= 48 else "winnat-ui.svg"
    return str(ASSETS / name)


def render(size):
    png = cairosvg.svg2png(url=source(size), output_width=size, output_height=size)
    return Image.open(io.BytesIO(png)).convert("RGBA")


def main():
    images = [render(s) for s in SIZES]
    images[-1].save(ASSETS / "winnat-ui.ico", format="ICO", sizes=[(s, s) for s in SIZES],
                    append_images=images[:-1])
    for size in (32, 48, 64, 256):
        render(size).save(ASSETS / ("winnat-ui-%d.png" % size))
    cairosvg.svg2png(url=source(512), write_to=str(ASSETS / "winnat-ui-512.png"), output_width=512, output_height=512)
    print("Icone rigenerate in", ASSETS)


if __name__ == "__main__":
    main()
