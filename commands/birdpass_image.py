import io
import os

from PIL import Image, ImageDraw, ImageFont

_FONT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets", "fonts")
_FONT_REGULAR = os.path.join(_FONT_DIR, "DejaVuSans.ttf")
_FONT_BOLD = os.path.join(_FONT_DIR, "DejaVuSans-Bold.ttf")

_BG = (35, 39, 42)
_HEADER_BG = (43, 47, 51)
_ROW_BG = (54, 58, 63)
_NAME = (235, 237, 240)
_MUTED = (150, 154, 160)
_ACCENT = (88, 101, 242)
_GOLD = (255, 202, 40)
_SILVER = (203, 209, 217)
_BRONZE = (205, 127, 50)
_BAR_BG = (30, 33, 36)
_MEDAL_TEXT = (30, 33, 36)

_font_cache = {}


def _font(size, bold=False):
    key = (size, bold)
    cached = _font_cache.get(key)
    if cached is not None:
        return cached
    path = _FONT_BOLD if bold else _FONT_REGULAR
    try:
        font = ImageFont.truetype(path, size)
    except Exception:
        font = ImageFont.load_default()
    _font_cache[key] = font
    return font


def _fit_name(draw, name, font, max_width):
    name = str(name)
    if draw.textlength(name, font=font) <= max_width:
        return name
    while name and draw.textlength(name + "…", font=font) > max_width:
        name = name[:-1]
    return name + "…"


def _round_rect_pill(draw, x0, y0, x1, y1, radius, fill, outline=None):
    draw.rounded_rectangle([x0, y0, x1, y1], radius=radius, fill=fill, outline=outline)


def _avatar_circle(img, size):
    im = img.convert("RGB")
    w, h = im.size
    side = min(w, h)
    left = (w - side) // 2
    top = (h - side) // 2
    im = im.crop((left, top, left + side, top + side)).resize((size, size), Image.LANCZOS)
    mask = Image.new("L", (size, size), 0)
    ImageDraw.Draw(mask).ellipse((0, 0, size, size), fill=255)
    return im, mask


_avatar_masks = {}


def _mask_48():
    size = 48
    mask = _avatar_masks.get("48")
    if mask is None:
        mask = Image.new("L", (size, size), 0)
        ImageDraw.Draw(mask).ellipse((0, 0, size, size), fill=255)
        _avatar_masks["48"] = mask
    return mask


def render_birdpass_card(display_name, guild_name, av_img, level, xp, into, need,
                         next_reward, upcoming, top3):
    width = 880
    height = 660
    img = Image.new("RGB", (width, height), _BG)
    draw = ImageDraw.Draw(img)

    _round_rect_pill(draw, 24, 24, width - 24, height - 24, 24, _ROW_BG)
    _round_rect_pill(draw, 24, 24, width - 24, 150, 24, _HEADER_BG)

    draw.text((64, 40), "BirdPass", font=_font(36, True), fill=_ACCENT)
    draw.text((64, 98), str(guild_name), font=_font(20), fill=_MUTED)

    avatar_size = 130
    if av_img is not None:
        av, mask = _avatar_circle(av_img, avatar_size)
        img.paste(av, (64, 180), mask)
    else:
        draw.ellipse((64, 180, 64 + avatar_size, 180 + avatar_size), outline=_ACCENT, width=6)

    name_font = _font(38, True)
    name = _fit_name(draw, display_name, name_font, 520)
    draw.text((232, 184), name, font=name_font, fill=_NAME)

    level_str = f"LEVEL {level}"
    badge_font = _font(24, True)
    badge_w = draw.textlength(level_str, font=badge_font)
    badge_y = 246
    _round_rect_pill(draw, 232, badge_y, 232 + badge_w + 36, badge_y + 44, 12, _ACCENT)
    draw.text((232 + 18, badge_y + 8), level_str, font=badge_font, fill=(250, 251, 253))

    stat_x = 232 + badge_w + 36 + 24
    draw.text((stat_x, 254), f"{int(xp):,} XP", font=_font(21, True), fill=_NAME)
    draw.text((stat_x, 286), f"needs {int(need):,} for next level", font=_font(16), fill=_MUTED)

    bar_x0, bar_x1 = 232, width - 120
    bar_w = bar_x1 - bar_x0
    bar_top = 330
    bar_h = 16
    _round_rect_pill(draw, bar_x0, bar_top, bar_x1, bar_top + bar_h, 8, _BAR_BG)
    pct = max(0.0, min(1.0, (into / need) if need > 0 else 0.0))
    fill_w = int(bar_w * pct)
    if fill_w > 0:
        _round_rect_pill(draw, bar_x0, bar_top, bar_x0 + fill_w, bar_top + bar_h, 8, _ACCENT)
    next_str = f"{int(into):,}/{int(need):,} XP to Level {level + 1}" if need > 0 else f"Level {level + 1}"
    draw.text((bar_x0, bar_top + bar_h + 8), next_str, font=_font(16), fill=_MUTED)

    draw.text((64, 372), "NEXT REWARD", font=_font(15), fill=_MUTED)
    nr_font = _font(20, True)
    draw.text((64, 398), _fit_name(draw, next_reward, nr_font, width - 128), font=nr_font, fill=_NAME)
    draw.text((64, 430), "COMING UP", font=_font(15), fill=_MUTED)
    up_font = _font(16)
    for i, line in enumerate(upcoming[:5]):
        draw.text((64, 456 + i * 24), _fit_name(draw, line, up_font, width - 128), font=up_font, fill=_MUTED)

    top_y = 576
    _round_rect_pill(draw, 24, top_y, width - 24, top_y + 60, 16, _HEADER_BG)
    draw.text((64, top_y + 12), "TOP 3 THIS WEEK", font=_font(24, True), fill=_ACCENT)

    row_h = 74
    row_top = top_y + 72
    for i, (name_part, av_part, xp_part) in enumerate(top3[:3]):
        y = row_top + i * row_h
        _round_rect_pill(draw, 40, y, width - 40, y + row_h, 14, _BG)

        medal = [_GOLD, _SILVER, _BRONZE][i]
        bbox = (40 + 20, y + 19, 40 + 20 + 36, y + 19 + 36)
        draw.ellipse(bbox, fill=medal)
        draw.text((bbox[0] + 8, bbox[1] + 4), str(i + 1), font=_font(20, True), fill=_MEDAL_TEXT)

        if av_part is not None:
            av, _ = _avatar_circle(av_part, 48)
            img.paste(av, (40 + 20 + 52 + 6, y + 13), _mask_48())

        name_x = 40 + 20 + 52 + 6 + 48 + 14
        nf = _font(25, True)
        draw.text((name_x, y + 12), _fit_name(draw, name_part, nf, 420), font=nf, fill=_NAME)
        xp_font = _font(19, True)
        xp_str = f"{int(xp_part):,} XP"
        xp_w = draw.textlength(xp_str, font=xp_font)
        draw.text((width - 40 - 20 - xp_w, y + 24), xp_str, font=xp_font, fill=_ACCENT)

    buf = io.BytesIO()
    img.save(buf, "PNG")
    buf.seek(0)
    return buf


async def setup(bot):
    pass