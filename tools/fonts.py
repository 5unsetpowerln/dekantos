#!/usr/bin/env python3
"""Install stand-ins for the Windows core fonts Arial, Times New Roman and Courier New.

Liberation Sans, Serif and Mono share the metrics of these fonts. Each style is renamed to the Windows
family, full and PostScript names and written under the Windows file name, and a .reg file registers
them, since DirectWrite only uses the fonts listed in the registry.

Usage:
  fonts.py <liberation ttf dir> <prefix Fonts dir> <out .reg>
"""
import pathlib
import sys

from fontTools.ttLib import TTFont

# (Liberation family, Windows family, file name stem, PostScript name stem)
FAMILIES = [
    ("LiberationSans", "Arial", "arial", "Arial"),
    ("LiberationSerif", "Times New Roman", "times", "TimesNewRomanPS"),
    ("LiberationMono", "Courier New", "cour", "CourierNewPS"),
]
# (Liberation style, Windows style, file name suffix)
STYLES = [
    ("Regular", "", ""),
    ("Bold", "Bold", "bd"),
    ("Italic", "Italic", "i"),
    ("BoldItalic", "Bold Italic", "bi"),
]
FAMILY, FULL_NAME, POSTSCRIPT_NAME = 1, 4, 6


def main():
    source, fonts, reg = map(pathlib.Path, sys.argv[1:4])
    entries = []
    for liberation, family, stem, ps_stem in FAMILIES:
        for liberation_style, style, suffix in STYLES:
            full = f"{family} {style}".strip()
            names = {
                FAMILY: family,
                FULL_NAME: full,
                POSTSCRIPT_NAME: f"{ps_stem}-{style.replace(' ', '')}MT" if style else f"{ps_stem}MT",
            }
            font = TTFont(source / f"{liberation}-{liberation_style}.ttf")
            for record in font["name"].names:
                if record.nameID in names:
                    record.string = names[record.nameID]
            font.save(fonts / f"{stem}{suffix}.ttf")
            entries.append(f'"{full} (TrueType)"="{stem}{suffix}.ttf"')
    reg.write_text("REGEDIT4\n\n[HKEY_LOCAL_MACHINE\\Software\\Microsoft\\Windows NT\\CurrentVersion\\Fonts]\n"
                   + "\n".join(entries) + "\n")


if __name__ == "__main__":
    main()
