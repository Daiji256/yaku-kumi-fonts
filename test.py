# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "fonttools[woff]==4.67.0",
#     "pillow==13.0.0",
# ]
# ///

"""Test suite and visual specimen generator for yaku-kumi-fonts."""

from __future__ import annotations

import itertools
import re
import sys
from datetime import datetime
from pathlib import Path

from fontTools.misc import timeTools
from fontTools.ttLib import TTFont
from PIL import Image, ImageChops, ImageDraw, ImageFont

YAKUMONO_CHARS = "、。，．・：；（）「」『』［］｛｝【】〈〉《》〔〕〝〟　"
YAKUMONO_SET = set(YAKUMONO_CHARS)
EXPECTED_CHAR_CODES = {ord(c) for c in YAKUMONO_CHARS}

FONTS_DIR = Path("fonts")
CSS_DIR = Path("css")
SOURCES_DIR = Path("tmp/sources")
SPECIMENS_DIR = Path("specimens")
SPECIMENS_DIFF_DIR = Path("tmp/specimens_diff")

BUILD_DATE = "2026-10-27T00:00:00Z"
BUILD_TIMESTAMP = timeTools.timestampSinceEpoch(
    datetime.fromisoformat(BUILD_DATE).timestamp()
)

SIZE_RANGES = {
    ".ttf": (8000, 15000),
    ".woff": (5000, 10000),
    ".woff2": (3500, 7000),
}

FONTS_INFO: list[tuple[str, str, str]] = [
    (
        "yaku-kumi-sans-thin",
        "NotoSansJP-Thin.ttf",
        "Yaku Kumi Sans Thin",
    ),
    (
        "yaku-kumi-sans-extra-light",
        "NotoSansJP-ExtraLight.ttf",
        "Yaku Kumi Sans ExtraLight",
    ),
    (
        "yaku-kumi-sans-light",
        "NotoSansJP-Light.ttf",
        "Yaku Kumi Sans Light",
    ),
    (
        "yaku-kumi-sans-regular",
        "NotoSansJP-Regular.ttf",
        "Yaku Kumi Sans Regular",
    ),
    (
        "yaku-kumi-sans-medium",
        "NotoSansJP-Medium.ttf",
        "Yaku Kumi Sans Medium",
    ),
    (
        "yaku-kumi-sans-semi-bold",
        "NotoSansJP-SemiBold.ttf",
        "Yaku Kumi Sans SemiBold",
    ),
    (
        "yaku-kumi-sans-bold",
        "NotoSansJP-Bold.ttf",
        "Yaku Kumi Sans Bold",
    ),
    (
        "yaku-kumi-sans-extra-bold",
        "NotoSansJP-ExtraBold.ttf",
        "Yaku Kumi Sans ExtraBold",
    ),
    (
        "yaku-kumi-sans-black",
        "NotoSansJP-Black.ttf",
        "Yaku Kumi Sans Black",
    ),
    (
        "yaku-kumi-serif-extra-light",
        "NotoSerifJP-ExtraLight.ttf",
        "Yaku Kumi Serif ExtraLight",
    ),
    (
        "yaku-kumi-serif-light",
        "NotoSerifJP-Light.ttf",
        "Yaku Kumi Serif Light",
    ),
    (
        "yaku-kumi-serif-regular",
        "NotoSerifJP-Regular.ttf",
        "Yaku Kumi Serif Regular",
    ),
    (
        "yaku-kumi-serif-medium",
        "NotoSerifJP-Medium.ttf",
        "Yaku Kumi Serif Medium",
    ),
    (
        "yaku-kumi-serif-semi-bold",
        "NotoSerifJP-SemiBold.ttf",
        "Yaku Kumi Serif SemiBold",
    ),
    (
        "yaku-kumi-serif-bold",
        "NotoSerifJP-Bold.ttf",
        "Yaku Kumi Serif Bold",
    ),
    (
        "yaku-kumi-serif-extra-bold",
        "NotoSerifJP-ExtraBold.ttf",
        "Yaku Kumi Serif ExtraBold",
    ),
    (
        "yaku-kumi-serif-black",
        "NotoSerifJP-Black.ttf",
        "Yaku Kumi Serif Black",
    ),
]

SAMPLE_LINE1 = "「『吾輩は猫である』、名前はまだ無い。」"
SAMPLE_LINE2 = "【夏目漱石】　これは〝美しい〟文字組み。（注：テスト）"


def find_source(filename: str) -> Path:
    """Find source instantiated Noto CJK font path in tmp/sources/."""
    p = SOURCES_DIR / filename
    if not p.exists():
        raise RuntimeError(
            f"Source font '{filename}' not found in {SOURCES_DIR}. Please run 'uv run build.py' first."
        )
    return p


def test_file_completeness_and_sizes() -> None:
    """Verify that all font families exist in TTF, WOFF, and WOFF2 within expected size ranges."""
    print("\n--- Test 1: File Completeness, Sizes & Format Parity ---")
    assert FONTS_DIR.is_dir(), f"{FONTS_DIR} directory does not exist"

    for prefix, _, _ in FONTS_INFO:
        ttf = TTFont(FONTS_DIR / f"{prefix}.ttf")
        ttf_cmap = ttf.getBestCmap()
        ttf_glyphs = ttf.getGlyphOrder()

        for ext, (min_sz, max_sz) in SIZE_RANGES.items():
            p = FONTS_DIR / f"{prefix}{ext}"
            assert p.exists(), f"Missing font file: {p}"
            sz = p.stat().st_size
            assert min_sz <= sz <= max_sz, (
                f"{p} size {sz} out of range ({min_sz}-{max_sz})"
            )
            if ext in (".woff", ".woff2"):
                w = TTFont(p)
                assert w.getBestCmap() == ttf_cmap, f"[{p.name}] cmap differs from TTF"
                assert w.getGlyphOrder() == ttf_glyphs, (
                    f"[{p.name}] glyph order differs from TTF"
                )

    print(
        f"  All {len(FONTS_INFO) * len(SIZE_RANGES)} font files verified (sizes and TTF/WOFF/WOFF2 parity)."
    )


def test_character_coverage_and_glyphs() -> None:
    """Verify character coverage, glyph outlines, and advance metrics."""
    print("\n--- Test 2: Character, Glyph & Advance Coverage ---")
    for prefix, _, _ in FONTS_INFO:
        font = TTFont(FONTS_DIR / f"{prefix}.ttf")
        cmap = font.getBestCmap()
        actual_codes = set(cmap.keys())
        assert actual_codes == EXPECTED_CHAR_CODES, (
            f"[{prefix}] Character mismatch: diff={actual_codes ^ EXPECTED_CHAR_CODES}"
        )

        glyf = font["glyf"]
        hmtx = font["hmtx"]
        for code in EXPECTED_CHAR_CODES:
            gid = cmap[code]
            adv, _ = hmtx[gid]
            assert adv == 1000, f"[{prefix}] Non-1000 advance ({adv}) for {chr(code)!r}"

            contours = glyf[gid].numberOfContours
            if chr(code) == "　":
                assert contours == 0, (
                    f"[{prefix}] Fullwidth space should have 0 contours"
                )
            else:
                assert contours != 0, (
                    f"[{prefix}] Character {chr(code)!r} has empty glyph"
                )

    print(
        f"  Character coverage verified: Exactly {len(EXPECTED_CHAR_CODES)} characters at 1000 advance in all fonts."
    )


def test_metadata_validity() -> None:
    """Verify metadata fields across all fonts."""
    print("\n--- Test 3: Metadata & OpenType Tables ---")
    for prefix, _, display_name in FONTS_INFO:
        font = TTFont(FONTS_DIR / f"{prefix}.ttf")

        assert font["head"].fontRevision == 3.0
        assert font["head"].modified == BUILD_TIMESTAMP
        assert font["OS/2"].achVendID == "YKMI"

        gpos_features = {
            r.FeatureTag for r in font["GPOS"].table.FeatureList.FeatureRecord
        }
        assert {"chws", "vchw", "halt", "vhal"}.issubset(gpos_features)

        gsub_features = {
            r.FeatureTag for r in font["GSUB"].table.FeatureList.FeatureRecord
        }
        assert {"vert", "vrt2"}.issubset(gsub_features)

        names = {
            r.nameID: r.toUnicode()
            for r in font["name"].names
            if r.platformID == 3 and r.langID == 1033
        }
        assert "Copyright 2026 Daiji256." in names[0]
        assert names[1].startswith("Yaku Kumi")
        assert names[3] == f"3.000;YKMI;{names[6]}"
        assert names[4] == display_name
        assert names[5] == "Version 3.000"
        assert names[6].startswith("YakuKumi") and " " not in names[6]
        assert names[8] == "Adobe"
        assert (
            "subset web font for Japanese punctuation marks based on Noto" in names[10]
        )
        if 16 in names:
            assert names[16].startswith("Yaku Kumi")

    print(
        "  Metadata verified: Version 3.000, Vendor YKMI, proper copyright, and complete credits."
    )


def segment_text(text: str) -> list[tuple[str, bool]]:
    """Segment a string into alternating chunks of punctuation (Yaku Kumi) and general chars (Noto)."""
    return [
        ("".join(group), is_y)
        for is_y, group in itertools.groupby(text, lambda c: c in YAKUMONO_SET)
    ]


def draw_text_run(
    draw: ImageDraw.ImageDraw,
    pos: tuple[float, float],
    text: str,
    yaku_font: ImageFont.FreeTypeFont,
    noto_font: ImageFont.FreeTypeFont,
    enable_chws: bool,
    fill: tuple[int, int, int],
) -> float:
    """Draw a text string with fallback: Yaku Kumi for punctuation, Noto for general characters."""
    x, y = pos
    features = ["chws"] if enable_chws else ["-chws"]
    for seg, is_y in segment_text(text):
        f = yaku_font if is_y else noto_font
        draw.text((x, y), seg, font=f, fill=fill, features=features)
        x += f.getlength(seg, features=features)
    return x - pos[0]


def test_chws_feature_compaction() -> None:
    """Verify that chws feature reduces advance width across all fonts and weights."""
    print("\n--- Test 4: chws Feature Compaction ---")
    dummy_draw = ImageDraw.Draw(Image.new("RGB", (1, 1)))
    for prefix, source_file, _ in FONTS_INFO:
        y_font = ImageFont.truetype(
            str(FONTS_DIR / f"{prefix}.ttf"), 32, layout_engine=ImageFont.Layout.RAQM
        )
        n_font = ImageFont.truetype(
            str(find_source(source_file)), 32, layout_engine=ImageFont.Layout.RAQM
        )

        w_off = draw_text_run(
            dummy_draw, (0, 0), SAMPLE_LINE1, y_font, n_font, False, (0, 0, 0)
        )
        w_on = draw_text_run(
            dummy_draw, (0, 0), SAMPLE_LINE1, y_font, n_font, True, (0, 0, 0)
        )

        reduction_px = w_off - w_on
        reduction_pct = (reduction_px / w_off) * 100
        assert reduction_px == 48.0, (
            f"[{prefix}] Expected 48.0px compaction, got {reduction_px:.1f}px"
        )
        print(
            f"  [{prefix:30}] -{reduction_px:.1f}px (-{reduction_pct:.1f}%) | OFF: {w_off:.1f}px -> ON: {w_on:.1f}px"
        )

    print(
        "  chws feature compaction verified: All fonts tighten punctuation pairs reliably."
    )


def generate_specimen_card(
    yaku_prefix: str,
    source_filename: str,
    display_name: str,
) -> Image.Image:
    """Generate a clean visual specimen card (720x280) comparing chws OFF vs ON."""
    yaku_path = FONTS_DIR / f"{yaku_prefix}.ttf"
    source_path = find_source(source_filename)

    raqm = ImageFont.Layout.RAQM
    f_y_body = ImageFont.truetype(str(yaku_path), 24, layout_engine=raqm)
    f_n_body = ImageFont.truetype(str(source_path), 24, layout_engine=raqm)
    f_n_title = ImageFont.truetype(str(source_path), 18, layout_engine=raqm)
    f_n_label = ImageFont.truetype(str(source_path), 13, layout_engine=raqm)

    w, h = 720, 280
    img = Image.new("RGB", (w, h), (255, 255, 255))
    draw = ImageDraw.Draw(img)

    c_text = (17, 24, 39)
    c_label = (107, 114, 128)
    c_line = (229, 231, 235)
    pad_x = 32

    draw.text((pad_x, 20), display_name, font=f_n_title, fill=c_text)
    draw.line([(pad_x, 48), (w - pad_x, 48)], fill=c_line, width=1)

    for label, enable_chws, label_y in [
        ("chws OFF", False, 64),
        ("chws ON", True, 172),
    ]:
        draw.text((pad_x, label_y), label, font=f_n_label, fill=c_label)
        draw_text_run(
            draw,
            (pad_x, label_y + 22),
            SAMPLE_LINE1,
            f_y_body,
            f_n_body,
            enable_chws,
            c_text,
        )
        draw_text_run(
            draw,
            (pad_x, label_y + 54),
            SAMPLE_LINE2,
            f_y_body,
            f_n_body,
            enable_chws,
            c_text,
        )

    return img


def _save_diff_report(
    old_img: Image.Image,
    new_img: Image.Image,
    diff: Image.Image,
    dest: Path,
    display_name: str,
) -> None:
    """Save an annotated side-by-side comparison report with differences highlighted."""
    diff_mask = diff.convert("L").point(lambda p: 255 if p > 0 else 0)
    red_layer = Image.new("RGB", old_img.size, (255, 0, 0))
    diff_colored = Image.composite(red_layer, new_img, diff_mask)

    w, h = old_img.size
    rep_w = w
    rep_h = h * 3 + 120
    rep_img = Image.new("RGB", (rep_w, rep_h), (255, 255, 255))
    draw = ImageDraw.Draw(rep_img)

    draw.text((24, 8), f"Baseline (Accepted): {display_name}", fill=(80, 80, 80))
    rep_img.paste(old_img, (0, 28))
    draw.text((24, h + 38), f"Candidate (Current): {display_name}", fill=(80, 80, 80))
    rep_img.paste(new_img, (0, h + 58))
    draw.text(
        (24, h * 2 + 68),
        "[3] Pixel Difference Highlight (Changed Pixels)",
        fill=(220, 20, 60),
    )
    rep_img.paste(diff_colored, (0, h * 2 + 88))
    rep_img.save(dest)


def test_visual_specimens_and_regression() -> None:
    """Generate visual specimens in specimens/ and run visual regression testing."""
    print("\n--- Test 5: Visual Specimens (specimens/) & Regression Testing ---")
    SPECIMENS_DIR.mkdir(parents=True, exist_ok=True)
    SPECIMENS_DIFF_DIR.mkdir(parents=True, exist_ok=True)

    update_mode = "--update" in sys.argv or "-u" in sys.argv
    matches = created = updated = diff_count = missing_count = 0

    for prefix, source_file, display_name in FONTS_INFO:
        specimen_file = SPECIMENS_DIR / f"{prefix}.png"
        new_img = generate_specimen_card(prefix, source_file, display_name)

        if not specimen_file.exists():
            if update_mode:
                new_img.save(specimen_file)
                created += 1
                print(f"  [CREATED]  {specimen_file.name}")
            else:
                missing_count += 1
                print(
                    f"  [MISSING]  {specimen_file.name} (run with '--update' to generate)"
                )
            continue

        old_img = Image.open(specimen_file).convert("RGB")
        diff = ImageChops.difference(old_img, new_img)
        if diff.getbbox() is None:
            matches += 1
            print(f"  [MATCH]    {specimen_file.name}")
        else:
            diff_file = SPECIMENS_DIFF_DIR / f"{prefix}_diff.png"
            _save_diff_report(old_img, new_img, diff, diff_file, display_name)
            if update_mode:
                new_img.save(specimen_file)
                updated += 1
                print(f"  [UPDATED]  {specimen_file.name} (diff saved to {diff_file})")
            else:
                diff_count += 1
                print(f"  [DIFF]     {specimen_file.name} (diff saved to {diff_file})")

    print(
        f"\n  Visual Specimen Summary: {created} created, {matches} matched, {updated} updated, "
        f"{diff_count} diffs, {missing_count} missing."
    )
    if not update_mode:
        assert missing_count == 0, (
            f"Baseline specimen(s) missing for {missing_count} font(s). Run with '--update' to generate baselines."
        )
        assert diff_count == 0, (
            f"Visual regression detected in {diff_count} specimen(s). Run with '--update' to accept changes."
        )


def test_css_files() -> None:
    """Verify that CSS files exist, and that all referenced font URLs resolve to existing files."""
    print("\n--- Test 6: CSS Distribution Files ---")
    assert CSS_DIR.is_dir(), f"{CSS_DIR} directory does not exist"

    expected_slugs = {
        "yaku-kumi",
        "yaku-kumi-sans",
        "yaku-kumi-serif",
    }
    actual_css = {
        p.stem for p in CSS_DIR.glob("*.css") if not p.name.endswith(".min.css")
    }
    assert actual_css == expected_slugs, (
        f"Unexpected CSS files: {actual_css ^ expected_slugs}"
    )

    for slug in expected_slugs:
        for ext in (".css", ".min.css"):
            css_path = CSS_DIR / f"{slug}{ext}"
            assert css_path.exists(), f"Missing CSS file: {css_path}"
            assert css_path.stat().st_size > 0, f"Empty CSS file: {css_path}"

    url_pattern = re.compile(r'url\("([^"]+)"\)')
    referenced_fonts: set[str] = set()

    for css_file in CSS_DIR.glob("*.css"):
        content = css_file.read_text(encoding="utf-8")
        for match in url_pattern.finditer(content):
            rel_url = match.group(1)
            target = (CSS_DIR / rel_url).resolve()
            assert target.exists(), (
                f"Broken URL in {css_file.name}: {rel_url} -> {target}"
            )
            referenced_fonts.add(target.name)

    assert len(referenced_fonts) == len(FONTS_INFO) * len(SIZE_RANGES), (
        f"Not all font files are referenced in CSS: {len(referenced_fonts)}"
    )
    print(
        f"  All {len(expected_slugs) * 2} CSS files verified with {len(referenced_fonts)} valid font references."
    )


def main() -> None:
    print("=== Yaku Kumi Fonts Test Suite ===")
    test_file_completeness_and_sizes()
    test_character_coverage_and_glyphs()
    test_metadata_validity()
    test_chws_feature_compaction()
    test_visual_specimens_and_regression()
    test_css_files()
    print("\n==================================================")
    print("       ALL TESTS PASSED SUCCESSFULLY!       ")
    print("==================================================")


if __name__ == "__main__":
    main()
