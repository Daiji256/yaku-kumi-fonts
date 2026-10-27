# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "chws-tool==1.4.5",
#     "fonttools==4.67.0",
# ]
# ///

"""Build script for yaku-kumi-fonts: instancing, OpenType chws verification/injection, subsetting, and export."""

from __future__ import annotations

import asyncio
import re
import shutil
import tempfile
import urllib.request
from datetime import datetime
from pathlib import Path

from east_asian_spacing import Builder, Config
from fontTools.misc import timeTools
from fontTools.subset import Options, Subsetter
from fontTools.ttLib import TTFont
from fontTools.varLib.instancer import instantiateVariableFont

YAKUMONO_CHARS = (
    "、。，．・：；（）｟｠「」『』［］〚〛｛｝【】〖〗〈〉《》〔〕〘〙〝〟　"
)

SOURCES_DIR = Path("tmp/sources")
OUTPUT_DIR = Path("fonts")
CSS_DIR = Path("css")

FONT_VERSION = "3.000"
FONT_REVISION = float(FONT_VERSION)
VENDOR_ID = "YKMI"
AUTHOR_COPYRIGHT = "Copyright 2026 Daiji256."

BUILD_DATE = "2026-10-27T00:00:00Z"
BUILD_TIMESTAMP = timeTools.timestampSinceEpoch(
    datetime.fromisoformat(BUILD_DATE).timestamp()
)

FONTS_CONFIG = [
    {
        "name": "NotoSansJP",
        "vf_filename": "NotoSansJP-VF.ttf",
        "url": "https://github.com/notofonts/noto-cjk/raw/9241cec4a41a3832dfaaa75cd61d8f3be9c906fc/google-fonts/NotoSansJP%5Bwght%5D.ttf",
        "family_name": "Yaku Kumi Sans",
        "base_family": "Noto Sans JP",
        "prefix": "yaku-kumi-sans",
        "weights": [
            (100, "thin", "Thin"),
            (200, "extra-light", "ExtraLight"),
            (300, "light", "Light"),
            (400, "regular", "Regular"),
            (500, "medium", "Medium"),
            (600, "semi-bold", "SemiBold"),
            (700, "bold", "Bold"),
            (800, "extra-bold", "ExtraBold"),
            (900, "black", "Black"),
        ],
    },
    {
        "name": "NotoSerifJP",
        "vf_filename": "NotoSerifJP-VF.ttf",
        "url": "https://github.com/notofonts/noto-cjk/raw/985fa52c81c1d6692ccdd82bc3656e8fb932fd89/google-fonts/NotoSerifJP%5Bwght%5D.ttf",
        "family_name": "Yaku Kumi Serif",
        "base_family": "Noto Serif JP",
        "prefix": "yaku-kumi-serif",
        "weights": [
            (200, "extra-light", "ExtraLight"),
            (300, "light", "Light"),
            (400, "regular", "Regular"),
            (500, "medium", "Medium"),
            (600, "semi-bold", "SemiBold"),
            (700, "bold", "Bold"),
            (800, "extra-bold", "ExtraBold"),
            (900, "black", "Black"),
        ],
    },
]


def download_source_fonts() -> None:
    """Download source Noto CJK Variable Fonts if not already cached."""
    SOURCES_DIR.mkdir(parents=True, exist_ok=True)
    for cfg in FONTS_CONFIG:
        dest = SOURCES_DIR / cfg["vf_filename"]
        if not dest.exists():
            print(f"Downloading {cfg['vf_filename']}...")
            tmp = dest.with_suffix(".tmp")
            req = urllib.request.Request(
                cfg["url"], headers={"User-Agent": "yaku-kumi-fonts-build/3.0"}
            )
            with (
                urllib.request.urlopen(req, timeout=60) as resp,
                open(tmp, "wb") as f,
            ):
                f.write(resp.read())
            tmp.replace(dest)


def update_metadata(
    font: TTFont,
    family_name: str,
    base_family: str,
    weight_value: int,
    weight_display: str,
) -> None:
    """Update font metadata (name, head, OS/2 tables) for Yaku Kumi release."""
    font["head"].fontRevision = FONT_REVISION
    font["head"].modified = BUILD_TIMESTAMP
    font["OS/2"].achVendID = VENDOR_ID
    font["OS/2"].usWeightClass = weight_value

    if weight_display == "Bold":
        font["OS/2"].fsSelection = (font["OS/2"].fsSelection & ~0x40) | 0x20
        font["head"].macStyle |= 0x01
    else:
        font["OS/2"].fsSelection = (font["OS/2"].fsSelection & ~0x20) | 0x40
        font["head"].macStyle &= ~0x01

    name_table = font["name"]

    ps_family = family_name.replace(" ", "")
    ps_name = f"{ps_family}-{weight_display}"
    full_name = f"{family_name} {weight_display}"
    win_family = family_name if weight_display in ("Regular", "Bold") else full_name
    win_subfamily = "Bold" if weight_display == "Bold" else "Regular"
    description = (
        f"{family_name} is a subset web font for Japanese punctuation marks based on "
        f"{base_family}, with OpenType chws features retained and optimized."
    )

    name_table.names = [
        r for r in name_table.names if r.nameID < 256 and r.nameID != 25
    ]

    for record in name_table.names:
        nid = record.nameID
        val = record.toUnicode()
        if nid == 0 and AUTHOR_COPYRIGHT not in val:
            record.string = f"{val.rstrip('.')}. {AUTHOR_COPYRIGHT}"
        elif nid == 3:
            record.string = f"{FONT_VERSION};{VENDOR_ID};{ps_name}"
        elif nid == 5:
            record.string = f"Version {FONT_VERSION}"

    name_table.setName(win_family, 1, 3, 1, 1033)
    name_table.setName(win_subfamily, 2, 3, 1, 1033)
    name_table.setName(f"{FONT_VERSION};{VENDOR_ID};{ps_name}", 3, 3, 1, 1033)
    name_table.setName(full_name, 4, 3, 1, 1033)
    name_table.setName(f"Version {FONT_VERSION}", 5, 3, 1, 1033)
    name_table.setName(ps_name, 6, 3, 1, 1033)
    name_table.setName(description, 10, 3, 1, 1033)
    name_table.setName(family_name, 16, 3, 1, 1033)
    name_table.setName(weight_display, 17, 3, 1, 1033)


def normalize_font_metrics(src_path: Path, dest_path: Path) -> Path:
    """Normalize non-1000 advance widths of fullwidth characters to 1000."""
    font = TTFont(src_path, recalcTimestamp=False)
    cmap = font.getBestCmap()
    hmtx = font["hmtx"]
    glyf = font["glyf"]

    needs_normalization = False
    for c in YAKUMONO_CHARS:
        code = ord(c)
        if code in cmap and hmtx[cmap[code]][0] != 1000:
            needs_normalization = True
            break

    if not needs_normalization:
        return src_path

    left_aligned = set("、。，．・：；）」』］｝】〉》〕｠〛〗〙〟")
    right_aligned = set("（「『［｛【〈《〔｟〚〖〘〝")

    def shift_fn(delta: int, char: str) -> int:
        if char in left_aligned:
            return 0
        if char in right_aligned:
            return delta
        return delta // 2

    for c in YAKUMONO_CHARS:
        code = ord(c)
        if code in cmap:
            gid = cmap[code]
            adv, lsb = hmtx[gid]
            if adv != 1000:
                shift = shift_fn(1000 - adv, c)
                hmtx[gid] = (1000, lsb + shift)
                if shift:
                    g = glyf[gid]
                    g.xMin += shift
                    g.xMax += shift
                    g.coordinates.translate((shift, 0))

    font["head"].modified = BUILD_TIMESTAMP
    font.save(dest_path)
    return dest_path


async def add_chws_features(src_path: Path, dest_path: Path) -> None:
    """Inject chws, vchw, halt, vhal features into font, preserving if already present."""
    config = Config.default.clone()
    config.fullwidth_advance = 1000
    builder = Builder(str(src_path), config=config)
    res = await builder.build_and_save(dest_path)
    if not res:
        shutil.copyfile(src_path, dest_path)


def subset_and_export(
    chws_ttf_path: Path,
    output_base_path: Path,
    family_name: str,
    base_family: str,
    weight_value: int,
    weight_display: str,
) -> None:
    """Subset font to YAKUMONO_CHARS and export TTF, WOFF, and WOFF2 formats."""
    font = TTFont(chws_ttf_path, recalcTimestamp=False)

    options = Options()
    options.layout_features = ["*"]
    options.name_IDs = ["*"]
    options.notdef_outline = True
    options.recalc_bounds = True
    options.recalc_timestamp = False
    options.canonical_order = True

    subsetter = Subsetter(options=options)
    subsetter.populate(text=YAKUMONO_CHARS)
    subsetter.subset(font)

    update_metadata(
        font,
        family_name=family_name,
        base_family=base_family,
        weight_value=weight_value,
        weight_display=weight_display,
    )

    for tbl in ("STAT", "fvar"):
        if tbl in font:
            del font[tbl]

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    for ext, flavor in [(".ttf", None), (".woff", "woff"), (".woff2", "woff2")]:
        font.flavor = flavor
        font.save(output_base_path.with_suffix(ext))


def generate_css() -> None:
    """Generate family and all-in-one CSS files for jsDelivr distribution."""
    CSS_DIR.mkdir(parents=True, exist_ok=True)
    families: dict[str, list[tuple[str, int, str]]] = {}

    for p in sorted(OUTPUT_DIR.glob("*.ttf")):
        font = TTFont(p)
        names = {
            r.nameID: r.toUnicode()
            for r in font["name"].names
            if r.platformID == 3 and r.langID == 1033
        }
        fam = names.get(16) or names[1]
        weight = font["OS/2"].usWeightClass
        slug = fam.lower().replace(" ", "-")
        families.setdefault(slug, []).append((fam, weight, p.stem))

    all_css_blocks: list[str] = []

    for slug, entries in sorted(families.items()):
        entries.sort(key=lambda e: e[1])
        blocks = [
            f"@font-face {{\n"
            f'  font-family: "{fam}";\n'
            f"  font-style: normal;\n"
            f"  font-weight: {weight};\n"
            f"  font-display: swap;\n"
            f"  src:\n"
            f'    url("../fonts/{stem}.woff2") format("woff2"),\n'
            f'    url("../fonts/{stem}.woff") format("woff"),\n'
            f'    url("../fonts/{stem}.ttf") format("truetype");\n'
            f"}}"
            for fam, weight, stem in entries
        ]
        family_css = "\n\n".join(blocks) + "\n"
        (CSS_DIR / f"{slug}.css").write_text(family_css, encoding="utf-8")
        minified = (
            re.sub(r"\s+", " ", re.sub(r"\s*([{:;,])\s*", r"\1", family_css)).strip()
            + "\n"
        )
        (CSS_DIR / f"{slug}.min.css").write_text(minified, encoding="utf-8")
        all_css_blocks.extend(blocks)

    combined_css = "\n\n".join(all_css_blocks) + "\n"
    (CSS_DIR / "yaku-kumi.css").write_text(combined_css, encoding="utf-8")
    minified_combined = (
        re.sub(r"\s+", " ", re.sub(r"\s*([{:;,])\s*", r"\1", combined_css)).strip()
        + "\n"
    )
    (CSS_DIR / "yaku-kumi.min.css").write_text(minified_combined, encoding="utf-8")


async def main() -> None:
    download_source_fonts()

    print("Building yaku-kumi-fonts...")
    with tempfile.TemporaryDirectory() as tmp_dir:
        work_dir = Path(tmp_dir)
        for cfg in FONTS_CONFIG:
            vf_path = SOURCES_DIR / cfg["vf_filename"]
            print(f"Loading {cfg['name']} variable font...")
            vf = TTFont(vf_path)

            for weight_value, weight_suffix, weight_display in cfg["weights"]:
                output_stem = f"{cfg['prefix']}-{weight_suffix}"
                inst_dest = work_dir / f"{cfg['name']}-{weight_display}.ttf"
                norm_dest = work_dir / f"norm_{inst_dest.name}"
                chws_dest = work_dir / f"chws_{inst_dest.name}"

                # Instantiate variable font at target weight
                inst_font = instantiateVariableFont(
                    vf, {"wght": weight_value}, inplace=False
                )
                inst_font.save(inst_dest)

                # Also cache instantiated full font in SOURCES_DIR for tests and specimen generation
                cached_source = SOURCES_DIR / f"{cfg['name']}-{weight_display}.ttf"
                if not cached_source.exists():
                    shutil.copyfile(inst_dest, cached_source)

                # Normalize, add/verify chws, subset, and export
                norm_src = normalize_font_metrics(inst_dest, norm_dest)
                await add_chws_features(norm_src, chws_dest)
                print(f"  {cfg['name']} wght={weight_value} -> {output_stem}")
                subset_and_export(
                    chws_dest,
                    OUTPUT_DIR / output_stem,
                    family_name=cfg["family_name"],
                    base_family=cfg["base_family"],
                    weight_value=weight_value,
                    weight_display=weight_display,
                )

    generate_css()
    print(f"Build complete: fonts in {OUTPUT_DIR}/, CSS in {CSS_DIR}/")


if __name__ == "__main__":
    asyncio.run(main())
