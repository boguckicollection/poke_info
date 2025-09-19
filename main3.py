# generator_instagram.py
import os
import csv
from PIL import Image, ImageDraw, ImageFont, ImageFilter
import re
import requests
import io
import unicodedata
from datetime import datetime
from urllib.parse import urlparse

# --- Konfiguracja ---
WIDTH, HEIGHT = 1080, 1350
PADDING = 80
FOOTER_HEIGHT = 160
FONT_PATH = "Montserrat-SemiBold.ttf"
HEADER_FONT_PATH = "Montserrat-ExtraBold.ttf"
HIGHLIGHT_FONT_PATH = "Montserrat-ExtraBold.ttf"
BANNER_PATH = "banner22.png"
OUTPUT_DIR = "output"

try:
    from rembg import remove
    REMBG_AVAILABLE = True
except ImportError:
    REMBG_AVAILABLE = False

CATEGORY_STYLES = {
    "Trendy cen": {"colors": [(255, 165, 0), (255, 215, 0)], "emoji": "📈"},
    "Rekordy": {"colors": [(255, 60, 60), (255, 100, 100)], "emoji": "💥"},
    "Nowe zestawy": {"colors": [(0, 174, 239), (100, 220, 255)], "emoji": "📦"},
    "Inwestycje": {"colors": [(80, 200, 120), (130, 255, 160)], "emoji": "🔮"},
    "Top 10": {"colors": [(255, 215, 0), (255, 230, 100)], "emoji": "🏆"},
    "Promocje": {"colors": [(155, 89, 182), (200, 130, 230)], "emoji": "🎉"},
    "Domyślny": {"colors": [(200, 200, 200), (230, 230, 230)], "emoji": "ℹ️"}
}

_CATEGORY_KEY_VARIANTS = ("Kategoria", "kategoria")
_DESCRIPTION_KEY_VARIANTS = ("Opis", "opis")
_SOURCE_KEY_VARIANTS = ("Źródło", "Zrodlo", "źródło", "zrodlo")
_BACKGROUND_KEY_VARIANTS = ("Tło", "Tlo", "tło", "tlo")
_GRAPHICS_KEY_VARIANTS = ("Grafika", "Grafiki", "grafika", "grafiki")

HIGHLIGHT_PROPER_NAMES = [
    "Lost Origin",
    "151 ETB",
    "Kingdra ex",
    "Greninja ex",
    "Prismatic Pokémon Center ETB",
    "Mewtwo SVP052",
    "Magneton PC",
    "Noctowl PC",
    "Celebration Fanfare",
    "PSA 10",
]
HIGHLIGHT_PRICE_PATTERN = r'(\d[\d\s,.]*\s?(?:USD|dolarów|zł|PLN|eur|euro|£|GBP))'
HIGHLIGHT_DATE_PATTERN = r'(\d{1,2}\s(?:stycznia|lutego|marca|kwietnia|maja|czerwca|lipca|sierpnia|września|października|listopada|grudnia)\s\d{4}\s?r?\.)'
_proper_names_pattern = "|".join(re.escape(name) for name in HIGHLIGHT_PROPER_NAMES)
HIGHLIGHT_PATTERN = re.compile(
    f"({HIGHLIGHT_PRICE_PATTERN}|{HIGHLIGHT_DATE_PATTERN}|{_proper_names_pattern})",
    re.IGNORECASE,
)

CONTENT_PANEL_HORIZONTAL_GAP = 40
CONTENT_PANEL_TOP_OFFSET = PADDING + 30
CONTENT_PANEL_BOTTOM_OFFSET = FOOTER_HEIGHT + 30
CONTENT_PANEL_RADIUS = 65
CONTENT_PANEL_INNER_PADDING = 70
CONTENT_PANEL_IMAGE_INSET = 30
CONTENT_PANEL_IMAGE_MAX_HEIGHT = 520
CONTENT_PANEL_IMAGE_TEXT_GAP = 48
PRICE_COMPONENT_SPACING = 26
PRICE_BLOCK_TO_TEXT_GAP = 36
SPARKLINE_HEIGHT = 140
SPARKLINE_MIN_WIDTH = 240
SPARKLINE_MAX_WIDTH = 720

def _extract_extension_from_source(source):
    if not source or not isinstance(source, str):
        return ""
    parsed = urlparse(source)
    path = parsed.path if parsed.scheme else source
    _, ext = os.path.splitext(path)
    return ext.lower()


def _get_row_title(row_data, default=""):
    """Return the title value supporting both accented and unaccented keys."""
    return _get_row_value_with_variants(
        row_data,
        ("Tytuł", "Tytul", "tytuł", "tytul"),
        default,
    )


def _normalize_key_name(key):
    if not isinstance(key, str):
        return ""

    normalized = unicodedata.normalize("NFKD", key)
    normalized = "".join(
        char for char in normalized if not unicodedata.combining(char)
    )
    return re.sub(r"[\s_]", "", normalized).lower()


def _get_row_value_with_variants(row_data, keys, default=""):
    if not row_data:
        return default

    if isinstance(keys, str):
        keys = (keys,)

    normalized_map = {}
    for existing_key in row_data.keys():
        normalized_key = _normalize_key_name(existing_key)
        if normalized_key and normalized_key not in normalized_map:
            normalized_map[normalized_key] = existing_key

    for key in keys:
        if key in row_data:
            value = row_data.get(key)
            if value not in (None, ""):
                return value

    for key in keys:
        normalized_key = _normalize_key_name(key)
        original_key = normalized_map.get(normalized_key)
        if original_key:
            value = row_data.get(original_key)
            if value not in (None, ""):
                return value

    for key in keys:
        if key in row_data:
            value = row_data.get(key)
            if value is not None:
                return value

    for key in keys:
        normalized_key = _normalize_key_name(key)
        original_key = normalized_map.get(normalized_key)
        if original_key:
            value = row_data.get(original_key)
            if value is not None:
                return value

    return default


_NUMBERING_SPLIT_RE = re.compile(r"\d+\.\s*")
_NUMERIC_EXTRACTION_RE = re.compile(r"-?\d[\d\s]*(?:[.,]\d+)?")


def _extract_numbered_items(raw_value):
    if not raw_value or not isinstance(raw_value, str):
        return []

    normalized = raw_value.replace("\r\n", "\n")
    matches = list(_NUMBERING_SPLIT_RE.finditer(normalized))
    if not matches:
        return []

    segments = _NUMBERING_SPLIT_RE.split(normalized)
    if segments:
        segments = segments[1:]

    items = []
    for segment in segments[:len(matches)]:
        text = segment.strip()
        if text:
            items.append(text)

    return items


def _measure_text_height(font, text):
    if not font or not text:
        return 0
    bbox = font.getbbox(str(text))
    return max(0, bbox[3] - bbox[1])


def _split_series_groups(raw_value, expected_groups=None):
    if not raw_value or not isinstance(raw_value, str):
        return []

    normalized = raw_value.replace("\r\n", "\n").replace("\r", "\n").strip()
    if not normalized:
        return []

    candidate_groups = []

    double_newline_groups = [seg.strip() for seg in re.split(r"\n{2,}", normalized) if seg.strip()]
    if double_newline_groups:
        candidate_groups.append(double_newline_groups)

    pipe_groups = [seg.strip() for seg in normalized.split("|") if seg.strip()]
    if len(pipe_groups) > 1:
        candidate_groups.append(pipe_groups)

    double_semicolon_groups = [seg.strip() for seg in re.split(r";{2,}", normalized) if seg.strip()]
    if len(double_semicolon_groups) > 1:
        candidate_groups.append(double_semicolon_groups)

    newline_groups = [seg.strip() for seg in normalized.split("\n") if seg.strip()]
    if len(newline_groups) > 1:
        candidate_groups.append(newline_groups)

    if not candidate_groups:
        return [normalized]

    if expected_groups:
        candidate_groups = sorted(
            candidate_groups,
            key=lambda g: (abs(len(g) - expected_groups), -len(g)),
        )
        return candidate_groups[0]

    return max(candidate_groups, key=len)


def _split_segment_entries(segment):
    if not segment:
        return []

    normalized = str(segment).replace("\r", "\n")
    normalized = normalized.replace("|", ";")
    normalized = normalized.replace("\n", ";")
    entries = [entry.strip() for entry in re.split(r";{1,}", normalized) if entry.strip()]
    return entries


def _ensure_series_length(groups, expected_length):
    if expected_length is None:
        return list(groups)

    result = list(groups)
    while len(result) < expected_length:
        result.append("")
    if len(result) > expected_length:
        result = result[:expected_length]
    return result


def _parse_price_series(raw_value, expected_length=None):
    groups = _split_series_groups(raw_value, expected_length)
    target_length = expected_length if expected_length is not None else len(groups)
    groups = _ensure_series_length(groups, target_length)

    parsed = []
    for group in groups:
        numeric_values = []
        for entry in _split_segment_entries(group):
            match = _NUMERIC_EXTRACTION_RE.search(entry)
            if not match:
                continue
            normalized = match.group(0).replace(" ", "").replace(",", ".")
            try:
                numeric_values.append(float(normalized))
            except ValueError:
                continue
        parsed.append(numeric_values)

    return parsed


def _parse_date_series(raw_value, expected_length=None):
    groups = _split_series_groups(raw_value, expected_length)
    target_length = expected_length if expected_length is not None else len(groups)
    groups = _ensure_series_length(groups, target_length)

    parsed = []
    for group in groups:
        parsed.append(_split_segment_entries(group))

    return parsed


def _format_price_value(value):
    formatted = f"{value:,.2f}".replace(",", " ")
    return formatted.replace(".", ",")


def _create_sparkline_image(prices, width, height=SPARKLINE_HEIGHT, padding=18):
    if not prices or len(prices) < 2:
        return None

    width = int(round(width))
    min_width = max(int(padding * 2 + 20), 120)
    if width < min_width:
        width = min_width
    if width > SPARKLINE_MAX_WIDTH:
        width = SPARKLINE_MAX_WIDTH
    height = max(int(round(height)), padding * 2 + 2)

    image = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle(
        [(0, 0), (width - 1, height - 1)],
        radius=16,
        fill=(0, 0, 0, 100),
    )

    min_price = min(prices)
    max_price = max(prices)
    price_range = max_price - min_price

    usable_height = max(height - 2 * padding, 1)
    usable_width = max(width - 2 * padding, 1)

    points = []
    if price_range == 0:
        y = height / 2
        line_color = (190, 190, 190, 255)
        draw.line((padding, y, width - padding, y), fill=line_color, width=6)
        for x in (padding, width - padding):
            draw.ellipse((x - 6, y - 6, x + 6, y + 6), fill=line_color)
        return image

    step = usable_width / (len(prices) - 1)
    for idx, price in enumerate(prices):
        x = padding + step * idx
        normalized = (price - min_price) / price_range if price_range else 0
        y = height - padding - normalized * usable_height
        points.append((x, y))

    for idx in range(len(points) - 1):
        start = points[idx]
        end = points[idx + 1]
        diff = prices[idx + 1] - prices[idx]
        if diff > 0:
            color = (90, 200, 130, 255)
        elif diff < 0:
            color = (220, 85, 90, 255)
        else:
            color = (200, 200, 200, 255)
        draw.line([start, end], fill=color, width=6)

    for x, y in points:
        draw.ellipse((x - 5, y - 5, x + 5, y + 5), fill=(245, 245, 245, 255))

    return image


def _prepare_price_components(prices, dates, font_price, font_small, content_width):
    prices = list(prices or [])
    dates = list(dates or [])

    current_price = prices[-1] if prices else None
    last_date = dates[-1] if dates else ""

    components = []

    if current_price is not None:
        price_text = f"Aktualna cena: {_format_price_value(current_price)} PLN"
        components.append({
            "type": "text",
            "text": price_text,
            "font": font_price,
            "fill": "white",
            "shadow": True,
            "height": _measure_text_height(font_price, price_text),
        })

    sparkline_img = None
    if prices and len(prices) >= 2 and content_width:
        sparkline_width = min(
            max(int(content_width * 0.9), SPARKLINE_MIN_WIDTH),
            SPARKLINE_MAX_WIDTH,
        )
        max_available_width = max(int(content_width - 20), 120)
        sparkline_width = min(sparkline_width, max_available_width)
        sparkline_img = _create_sparkline_image(prices, sparkline_width)
        if sparkline_img:
            components.append({
                "type": "image",
                "image": sparkline_img,
                "height": sparkline_img.height,
            })

    if not sparkline_img:
        if current_price is not None:
            fallback_text = "Brak historii zmian cen"
        else:
            fallback_text = "Brak danych cenowych"
        components.append({
            "type": "text",
            "text": fallback_text,
            "font": font_small,
            "fill": (225, 225, 225),
            "shadow": False,
            "height": _measure_text_height(font_small, fallback_text),
        })

    if last_date:
        legend_text = f"Raport: {last_date}"
        components.append({
            "type": "text",
            "text": legend_text,
            "font": font_small,
            "fill": (210, 210, 210),
            "shadow": False,
            "height": _measure_text_height(font_small, legend_text),
        })

    total_height = sum(component["height"] for component in components)
    if components:
        total_height += PRICE_COMPONENT_SPACING * (len(components) - 1)

    return components, total_height


def _strip_leading_numbering(text):
    if not text or not isinstance(text, str):
        return ""
    return re.sub(r"^\s*\d+\.\s*", "", text).strip()


_PORTAL_NAME_ALIASES = {
    "allegro.pl": "Allegro",
    "cardmarket.com": "Cardmarket",
    "cardmarket.eu": "Cardmarket",
    "ebay.com": "eBay",
    "ebay.co.uk": "eBay",
    "ebay.de": "eBay",
    "facebook.com": "Facebook",
    "instagram.com": "Instagram",
    "pokebeach.com": "PokeBeach",
    "pwcc.com": "PWCC",
    "pwccmarketplace.com": "PWCC",
    "tcgplayer.com": "TCGplayer",
    "youtube.com": "YouTube",
}


def _extract_portal_name(source_text):
    """Parse source URL and return a concise portal name."""
    if not source_text or not isinstance(source_text, str):
        return ""

    raw_text = source_text.strip()
    if not raw_text:
        return ""

    parsed = urlparse(raw_text)
    if not parsed.scheme and not parsed.netloc:
        parsed = urlparse(f"//{raw_text}")

    host = parsed.netloc or ""
    if not host and parsed.path:
        potential_host = parsed.path.split("/")[0]
        if "." in potential_host:
            host = potential_host

    if not host:
        return ""

    host = host.split("@")[-1].split(":")[0].lower()
    if not host or " " in host or "." not in host:
        return ""

    host_without_www = host[4:] if host.startswith("www.") else host
    host_parts = [part for part in host_without_www.split(".") if part]
    if not host_parts:
        return ""

    candidate_hosts = [host_without_www, host]
    if len(host_parts) >= 2:
        base_domain = ".".join(host_parts[-2:])
        if len(host_parts) >= 3 and len(host_parts[-1]) <= 2 and len(host_parts[-2]) <= 3:
            base_domain = ".".join(host_parts[-3:])
        candidate_hosts.append(base_domain)

    for candidate in candidate_hosts:
        alias = _PORTAL_NAME_ALIASES.get(candidate)
        if alias:
            return alias

    if len(host_parts) == 1:
        main_part = host_parts[0]
    else:
        tld = host_parts[-1]
        second_level = host_parts[-2]
        if len(host_parts) >= 3 and len(tld) <= 2 and len(second_level) <= 3:
            main_part = host_parts[-3]
        else:
            main_part = second_level

    if not main_part:
        return ""

    cleaned = main_part.replace("-", " ").replace("_", " ").strip()
    if not cleaned:
        return ""

    return cleaned.title()


def _has_visible_alpha(image):
    if image is None or image.mode not in ("RGBA", "LA"):
        return False
    try:
        extrema = image.getchannel("A").getextrema()
    except Exception:
        return False
    if not extrema:
        return False
    return extrema[0] < 255


def _is_transparent_png(image, source_hint=None):
    if image is None:
        return False

    has_alpha = getattr(image, "_has_transparency", None)
    if has_alpha is None:
        has_alpha = _has_visible_alpha(image)
    if not has_alpha:
        return False

    format_hint = getattr(image, "_source_format", "") or ""
    extension_hint = getattr(image, "_source_extension", "") or ""
    if source_hint and not extension_hint:
        extension_hint = _extract_extension_from_source(source_hint)

    is_png = False
    if format_hint:
        is_png = format_hint.upper() == "PNG"
    if not is_png and extension_hint:
        is_png = extension_hint.lower() == ".png"

    return is_png and has_alpha


def fetch_image_from_url(url):
    if not url or not url.startswith('http'):
        return None
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        response = requests.get(url, headers=headers, timeout=15)
        response.raise_for_status()

        image_bytes = io.BytesIO(response.content)
        with Image.open(image_bytes) as source_image:
            source_format = (source_image.format or "").upper()
            converted = source_image.convert("RGBA")

        converted._source_format = source_format
        converted._source_extension = _extract_extension_from_source(url)
        converted._has_transparency = _has_visible_alpha(converted)

        return converted
    except Exception as e:
        print(f"Błąd pobierania obrazu z URL {url}: {e}")
        return None

def draw_text_with_shadow(draw, position, text, font, fill_color, shadow_color=(0,0,0,128), shadow_offset=(5,5)):
    x, y = position
    draw.text((x + shadow_offset[0], y + shadow_offset[1]), text, font=font, fill=shadow_color)
    draw.text(position, text, font=font, fill=fill_color)

def _calculate_panel_bounds():
    panel_left = max(20, PADDING - CONTENT_PANEL_HORIZONTAL_GAP)
    panel_right = min(WIDTH - 20, WIDTH - (PADDING - CONTENT_PANEL_HORIZONTAL_GAP))
    panel_top = max(PADDING, CONTENT_PANEL_TOP_OFFSET)
    panel_bottom = HEIGHT - max(FOOTER_HEIGHT, CONTENT_PANEL_BOTTOM_OFFSET)

    panel_bounds = (
        int(panel_left),
        int(panel_top),
        int(panel_right),
        int(panel_bottom),
    )

    content_bounds = (
        panel_bounds[0] + CONTENT_PANEL_INNER_PADDING,
        panel_bounds[1] + CONTENT_PANEL_INNER_PADDING,
        panel_bounds[2] - CONTENT_PANEL_INNER_PADDING,
        panel_bounds[3] - CONTENT_PANEL_INNER_PADDING,
    )

    return panel_bounds, content_bounds


def apply_modern_layout(img, row_data, transparent_background=False):
    """Rysuje półtransparentny panel tła dla głównej treści."""

    panel_bounds, content_bounds = _calculate_panel_bounds()

    panel_width = panel_bounds[2] - panel_bounds[0]
    panel_height = panel_bounds[3] - panel_bounds[1]
    if panel_width <= 0 or panel_height <= 0:
        return content_bounds

    if transparent_background:
        return content_bounds

    category_value = _get_row_value_with_variants(
        row_data,
        _CATEGORY_KEY_VARIANTS,
        "Domyślny",
    )
    styl = CATEGORY_STYLES.get(category_value, CATEGORY_STYLES["Domyślny"])
    c1, c2 = styl["colors"]

    # Miękki cień
    shadow = Image.new("RGBA", (panel_width + 80, panel_height + 80), (0, 0, 0, 0))
    shadow_draw = ImageDraw.Draw(shadow)
    shadow_draw.rounded_rectangle(
        (40, 40, panel_width + 40, panel_height + 40),
        radius=CONTENT_PANEL_RADIUS + 20,
        fill=(0, 0, 0, 140),
    )
    shadow = shadow.filter(ImageFilter.GaussianBlur(45))
    img.alpha_composite(shadow, dest=(panel_bounds[0] - 40, panel_bounds[1] - 20))

    # Podstawowe wypełnienie panelu
    panel_base = Image.new("RGBA", (panel_width, panel_height), (18, 18, 26, 220))
    panel_mask = Image.new("L", (panel_width, panel_height), 0)
    mask_draw = ImageDraw.Draw(panel_mask)
    mask_draw.rounded_rectangle(
        (0, 0, panel_width, panel_height),
        radius=CONTENT_PANEL_RADIUS,
        fill=255,
    )

    # Gradient akcentowy
    gradient = Image.new("RGBA", (panel_width, panel_height), (0, 0, 0, 0))
    gradient_draw = ImageDraw.Draw(gradient)
    for y in range(panel_height):
        ratio = y / max(panel_height - 1, 1)
        r = int(c1[0] * (1 - ratio) + c2[0] * ratio)
        g = int(c1[1] * (1 - ratio) + c2[1] * ratio)
        b = int(c1[2] * (1 - ratio) + c2[2] * ratio)
        gradient_draw.line([(0, y), (panel_width, y)], fill=(r, g, b, 85))

    gradient = gradient.filter(ImageFilter.GaussianBlur(8))
    panel_base = Image.alpha_composite(panel_base, gradient)

    # Delikatna obwódka w kolorze akcentu
    border = Image.new("RGBA", (panel_width, panel_height), (0, 0, 0, 0))
    border_draw = ImageDraw.Draw(border)
    border_draw.rounded_rectangle(
        (4, 4, panel_width - 4, panel_height - 4),
        radius=CONTENT_PANEL_RADIUS - 4,
        outline=(c1[0], c1[1], c1[2], 140),
        width=3,
    )

    panel_combined = Image.alpha_composite(panel_base, border)
    panel_combined.putalpha(panel_mask)
    img.alpha_composite(panel_combined, dest=panel_bounds[:2])

    # Połysk górnej krawędzi
    highlight = Image.new("RGBA", (panel_width, panel_height), (0, 0, 0, 0))
    highlight_draw = ImageDraw.Draw(highlight)
    highlight_draw.rounded_rectangle(
        (0, 0, panel_width, panel_height // 2),
        radius=CONTENT_PANEL_RADIUS,
        fill=(255, 255, 255, 35),
    )
    highlight = highlight.filter(ImageFilter.GaussianBlur(25))
    highlight.putalpha(panel_mask)
    img.alpha_composite(highlight, dest=panel_bounds[:2])

    return content_bounds

def generate_gradient_frame(draw, colors):
    c1, c2 = colors
    for i in range(20):
        ratio = i / 20
        r = int(c1[0] * (1 - ratio) + c2[0] * ratio)
        g = int(c1[1] * (1 - ratio) + c2[1] * ratio)
        b = int(c1[2] * (1 - ratio) + c2[2] * ratio)
        alpha = 180
        draw.rectangle((i, i, WIDTH - i, HEIGHT - i), outline=(r, g, b, alpha), width=1)


def _normalize_url_value(value):
    if not value:
        return ""
    if isinstance(value, str):
        return value.strip()
    return str(value).strip()


def _get_graphics_entries(row_data):
    if not row_data:
        return []

    raw_value = _get_row_value_with_variants(
        row_data,
        _GRAPHICS_KEY_VARIANTS,
        "",
    )

    entries = []

    def add_candidate(candidate):
        normalized = _normalize_url_value(candidate)
        if normalized:
            entries.append(normalized)

    if isinstance(raw_value, str):
        normalized_value = raw_value.replace("\r\n", "\n").replace("\r", "\n")
        for part in re.split(r"[;\n]+", normalized_value):
            add_candidate(part)
    elif isinstance(raw_value, (list, tuple, set)):
        for item in raw_value:
            add_candidate(item)
    else:
        add_candidate(raw_value)

    return entries


def _resolve_background_source(row_data):
    if not row_data:
        return ""

    background_candidate = _get_row_value_with_variants(
        row_data,
        _BACKGROUND_KEY_VARIANTS,
        "",
    )
    normalized_background = _normalize_url_value(background_candidate)
    if normalized_background:
        return normalized_background

    normalized_fallback = _normalize_url_value(row_data.get("_background_url"))
    if normalized_fallback:
        return normalized_fallback

    for graphic_source in _get_graphics_entries(row_data):
        if graphic_source:
            return graphic_source

    return ""


def _prepare_row_with_background(row_data):
    prepared = dict(row_data) if row_data else {}
    background_url = _resolve_background_source(prepared)
    if background_url:
        prepared["_background_url"] = background_url
        current_background = _normalize_url_value(prepared.get("Tło"))
        if not current_background:
            prepared["Tło"] = background_url
    return prepared, background_url


def create_base_image(row_data):
    # Priorytet źródła tła: "Tło" > `_background_url` > pierwszy wpis z "Grafika".
    image_source = _resolve_background_source(row_data)
    kategoria = _get_row_value_with_variants(
        row_data,
        _CATEGORY_KEY_VARIANTS,
        "Domyślny",
    )
    styl = CATEGORY_STYLES.get(kategoria, CATEGORY_STYLES['Domyślny'])
    base_image = fetch_image_from_url(image_source)
    is_transparent_background = _is_transparent_png(base_image, image_source) if base_image else False
    if base_image:
        scale = max(WIDTH / base_image.width, HEIGHT / base_image.height)
        new_size = (int(base_image.width * scale), int(base_image.height * scale))
        resized_background = base_image.resize(new_size, Image.Resampling.LANCZOS)
        left, top = (resized_background.width - WIDTH) / 2, (resized_background.height - HEIGHT) / 2
        img = resized_background.crop((left, top, left + WIDTH, top + HEIGHT))

        alpha_channel = None
        if "A" in img.getbands():
            try:
                alpha_channel = img.getchannel("A")
            except Exception:
                alpha_channel = None

        img_rgb = img.convert("RGB")
        img_rgb = img_rgb.filter(ImageFilter.GaussianBlur(30))

        overlay_alpha = 160
        overlay_strength = overlay_alpha / 255
        if overlay_strength > 0:
            dark_overlay = Image.new("RGB", (WIDTH, HEIGHT), (0, 0, 0))
            img_rgb = Image.blend(img_rgb, dark_overlay, overlay_strength)

        img = img_rgb.convert("RGBA")
        if alpha_channel is not None:
            img.putalpha(alpha_channel)
    else:
        img = Image.new("RGBA", (WIDTH, HEIGHT), (30, 30, 30, 255))
    draw = ImageDraw.Draw(img)
    generate_gradient_frame(draw, styl['colors'])
    return img, is_transparent_background

def add_common_elements(img, row_data, page_num, total_pages):
    draw = ImageDraw.Draw(img)
    font_footer = ImageFont.truetype(FONT_PATH, 28)
    font_number = ImageFont.truetype(FONT_PATH, 26)
    source_text = _get_row_value_with_variants(
        row_data,
        _SOURCE_KEY_VARIANTS,
        "",
    )

    if source_text:
        draw.text((PADDING, HEIGHT - 120), "Źródło:", font=font_footer, fill=(180, 180, 180))
        portal_name = _extract_portal_name(source_text) or source_text
        draw.text((PADDING, HEIGHT - 90), portal_name, font=font_footer, fill="white")

    page_info = f"{page_num}/{total_pages}"
    page_width = draw.textbbox((0, 0), page_info, font=font_number)[2]
    draw.text((WIDTH - PADDING - page_width, PADDING - 20), page_info, font=font_number, fill="gray")

    if os.path.exists(BANNER_PATH):
        banner = Image.open(BANNER_PATH).convert("RGBA")
        banner.thumbnail((300, 80), Image.Resampling.LANCZOS)
        img.paste(banner, (WIDTH - PADDING - banner.width, HEIGHT - FOOTER_HEIGHT + 40), banner)

    logo_path = "PTCG.png"
    logo_img = None

    if os.path.exists(logo_path):
        try:
            logo_img = Image.open(logo_path).convert("RGBA")
        except Exception as exc:
            print(f"Błąd podczas ładowania logo z {logo_path}: {exc}")
    else:
        print(f"Ostrzeżenie: Brak pliku logo {logo_path}, pomijam wyświetlanie logo.")

    if logo_img:
        logo_img.thumbnail((200, 60), Image.Resampling.LANCZOS)
        logo_x = (WIDTH - logo_img.width) // 2
        img.paste(logo_img, (logo_x, HEIGHT - 70), logo_img)

    return img

# --- Główne funkcje generujące ---

def generate_title_card(row_data, index, total_pages):
    """Generuje planszę tytułową z idealnie wyśrodkowanym tekstem."""
    img, _ = create_base_image(row_data)
    draw = ImageDraw.Draw(img)
    
    tytul = _get_row_title(row_data, 'Brak tytułu')
    font_title = ImageFont.truetype(HEADER_FONT_PATH, 90)
    
    words = tytul.split()
    lines = []
    current_line = ""
    for word in words:
        if draw.textbbox((0,0), (current_line + " " + word).strip(), font=font_title)[2] <= WIDTH - 2 * PADDING:
            current_line += " " + word
        else:
            lines.append(current_line.strip())
            current_line = word
    lines.append(current_line.strip())
    
    total_text_height = sum(draw.textbbox((0,0), line, font=font_title)[3] for line in lines) + (len(lines) - 1) * 20
    y_pos = (HEIGHT - total_text_height) / 2
    
    for line in lines:
        line_width = draw.textbbox((0,0), line, font=font_title)[2]
        x_pos = (WIDTH - line_width) / 2
        draw_text_with_shadow(draw, (x_pos, y_pos), line, font_title, "white")
        y_pos += draw.textbbox((0,0), line, font=font_title)[3] + 20

    img = add_common_elements(img, row_data, 1, total_pages)
    
    filename = f"{OUTPUT_DIR}/infografika_{index}_01_tytul.png"
    img.save(filename)
    print(f"Zapisano planszę tytułową: {filename}")


def _build_wrapped_rich_text_lines(draw, text, font, highlight_font, usable_width):
    if usable_width is None:
        usable_width = WIDTH - 2 * PADDING

    whitespace_pattern = re.compile(r"\S+|\s+")
    wrapped_lines = []

    for raw_line in text.split("\n"):
        highlight_spans = [match.span() for match in HIGHLIGHT_PATTERN.finditer(raw_line)]

        line_tokens = []
        pending_whitespace = ""

        def add_token(token_text, highlighted):
            nonlocal pending_whitespace
            if not token_text:
                return

            current_font = highlight_font if highlighted else font

            if pending_whitespace:
                if line_tokens:
                    prev_token = line_tokens[-1]
                    space_width = draw.textbbox((0, 0), pending_whitespace, font=prev_token["font"])[2]
                    prev_token["space_after"] += space_width
                else:
                    token_text = pending_whitespace + token_text
                pending_whitespace = ""

            word_width = draw.textbbox((0, 0), token_text, font=current_font)[2]
            line_tokens.append({
                "text": token_text,
                "font": current_font,
                "is_highlighted": highlighted,
                "word_width": word_width,
                "space_after": 0,
            })

        def add_whitespace(ws_text):
            nonlocal pending_whitespace
            if ws_text:
                pending_whitespace += ws_text

        def process_normal_chunk(chunk_text):
            for match in whitespace_pattern.finditer(chunk_text):
                segment = match.group(0)
                if segment.isspace():
                    add_whitespace(segment)
                else:
                    add_token(segment, False)

        def process_highlight_chunk(chunk_text):
            if not chunk_text:
                return

            leading_len = len(chunk_text) - len(chunk_text.lstrip())
            trailing_len = len(chunk_text) - len(chunk_text.rstrip())

            core_start = leading_len
            core_end = len(chunk_text) - trailing_len if trailing_len else len(chunk_text)

            if leading_len:
                add_whitespace(chunk_text[:core_start])

            core_text = chunk_text[core_start:core_end]
            if core_text:
                add_token(core_text, True)

            if trailing_len:
                add_whitespace(chunk_text[core_end:])

        cursor = 0
        for span_start, span_end in highlight_spans:
            if cursor < span_start:
                process_normal_chunk(raw_line[cursor:span_start])
            process_highlight_chunk(raw_line[span_start:span_end])
            cursor = span_end

        if cursor < len(raw_line):
            process_normal_chunk(raw_line[cursor:])

        if pending_whitespace and line_tokens:
            space_width = draw.textbbox((0, 0), pending_whitespace, font=line_tokens[-1]["font"])[2]
            line_tokens[-1]["space_after"] += space_width
            pending_whitespace = ""

        if not line_tokens:
            wrapped_lines.append([])
            continue

        current_line = []
        current_width = 0

        for token in line_tokens:
            if current_line and usable_width and current_width + token["word_width"] > usable_width:
                wrapped_lines.append(current_line)
                current_line = []
                current_width = 0

            current_line.append(token)
            current_width += token["word_width"] + token["space_after"]

        wrapped_lines.append(current_line)

    return wrapped_lines


def draw_rich_text(draw, start_y, text, font, highlight_font, highlight_color, content_left, usable_width):
    """Rysuje tekst, wyróżniając kluczowe słowa, ceny i daty."""
    if not text.strip():
        return

    y = start_y
    line_height = font.getbbox("A")[3] + 15
    if usable_width is None:
        usable_width = WIDTH - 2 * PADDING

    wrapped_lines = _build_wrapped_rich_text_lines(draw, text, font, highlight_font, usable_width)

    for line_tokens in wrapped_lines:
        line_width = 0
        cursor = 0
        for idx, token in enumerate(line_tokens):
            if idx > 0:
                cursor += line_tokens[idx - 1]["space_after"]
            token_end = cursor + token["word_width"]
            line_width = max(line_width, token_end)
            cursor += token["word_width"]

        if usable_width and usable_width > 0:
            start_x = content_left + (usable_width - line_width) / 2
        else:
            start_x = content_left

        current_x = start_x
        for idx, token in enumerate(line_tokens):
            if idx > 0:
                current_x += line_tokens[idx - 1]["space_after"]

            color = highlight_color if token["is_highlighted"] else "white"
            draw_text_with_shadow(
                draw,
                (int(round(current_x)), y),
                token["text"],
                token["font"],
                color,
                shadow_offset=(2, 2),
            )
            current_x += token["word_width"]

        y += line_height


def get_text_block_height(draw, text_block, font, highlight_font, usable_width):
    """Oblicza wysokość bloku tekstu."""
    if not text_block.strip():
        return 0

    line_height = font.getbbox("A")[3] + 15
    wrapped_lines = _build_wrapped_rich_text_lines(draw, text_block, font, highlight_font, usable_width)
    num_lines = max(len(wrapped_lines), 1)
    return num_lines * line_height


def generate_content_cards(row_data, index):
    """Generuje plansze treści w stałej sekwencji.

    Kolejność slajdów:
        1. Strona tytułowa
        2. Plansza z opisem (wyśrodkowany tekst)
        3. Jedna plansza na kartę z listy "Lista kart" wraz z ceną i grafiką
        4. Plansza końcowa prezentująca źródło i baner
    """

    row_data_with_bg, _ = _prepare_row_with_background(row_data)

    opis_raw = _get_row_value_with_variants(
        row_data_with_bg,
        _DESCRIPTION_KEY_VARIANTS,
        "",
    )
    opis_normalized = str(opis_raw or "").replace("\\r\\n", "\\n").replace("\\r", "\\n").strip()
    if not opis_normalized:
        opis_normalized = "Brak opisu."
    opis_normalized = re.sub(r"\\n{3,}", "\\n\\n", opis_normalized)

    list_value = _get_row_value_with_variants(
        row_data_with_bg,
        ("Lista kart", "Lista Kart", "Lista_kart", "ListaKart"),
        "",
    )
    card_entries = _extract_numbered_items(list_value)
    if not card_entries and list_value:
        normalized_list = str(list_value).replace("\\r\\n", "\\n").replace("\\r", "\\n")
        card_entries = [
            entry.strip()
            for entry in re.split(r"[\\n;]+", normalized_list)
            if entry.strip()
        ]
    card_entries = [_strip_leading_numbering(entry) for entry in card_entries]

    price_value_raw = _get_row_value_with_variants(
        row_data_with_bg,
        ("Ceny w PLN", "CenywPLN", "CenyPLN", "CenywPln", "Ceny wPLN", "Ceny"),
        "",
    )
    price_entries = _extract_numbered_items(price_value_raw)
    if not price_entries and price_value_raw:
        normalized_prices = str(price_value_raw).replace("\\r\\n", "\\n").replace("\\r", "\\n")
        price_entries = [
            entry.strip()
            for entry in re.split(r"[\\n;]+", normalized_prices)
            if entry.strip()
        ]
    price_entries = [_strip_leading_numbering(entry) for entry in price_entries]

    graphics_entries = _get_graphics_entries(row_data_with_bg)

    card_slides_data = []
    for idx, card_text in enumerate(card_entries):
        clean_title = card_text.strip()
        if not clean_title:
            continue
        card_slides_data.append({
            "title": clean_title,
            "price": price_entries[idx].strip() if idx < len(price_entries) else "",
            "graphic": graphics_entries[idx] if idx < len(graphics_entries) else None,
        })

    font_body = ImageFont.truetype(FONT_PATH, 42)
    highlight_font = ImageFont.truetype(HIGHLIGHT_FONT_PATH, 44)
    highlight_color = (255, 223, 100)
    font_price_label = ImageFont.truetype(FONT_PATH, 36)
    font_price_value = ImageFont.truetype(HEADER_FONT_PATH, 76)
    font_source_label = ImageFont.truetype(HEADER_FONT_PATH, 72)
    font_source_body = ImageFont.truetype(FONT_PATH, 44)

    measurement_draw = ImageDraw.Draw(Image.new("RGBA", (10, 10)))
    price_label_text = "CENA"
    price_block_padding_x = 48
    price_block_padding_y = 32
    price_block_gap = 14

    def compute_price_metrics(price_text):
        if not price_text:
            return None
        label_bbox = measurement_draw.textbbox((0, 0), price_label_text, font=font_price_label)
        value_bbox = measurement_draw.textbbox((0, 0), price_text, font=font_price_value)
        label_width = label_bbox[2] - label_bbox[0]
        label_height = label_bbox[3] - label_bbox[1]
        value_width = value_bbox[2] - value_bbox[0]
        value_height = value_bbox[3] - value_bbox[1]
        block_width = max(label_width, value_width) + price_block_padding_x * 2
        block_height = label_height + value_height + price_block_gap + price_block_padding_y * 2
        return {
            "label_width": label_width,
            "label_height": label_height,
            "value_width": value_width,
            "value_height": value_height,
            "block_width": block_width,
            "block_height": block_height,
        }

    card_graphics = []
    for slide_data in card_slides_data:
        graphic_url = slide_data.get("graphic")
        card_img = None
        is_transparent = False
        if graphic_url:
            card_img = fetch_image_from_url(graphic_url)
            if card_img:
                is_transparent = _is_transparent_png(card_img, graphic_url)
        card_graphics.append({"image": card_img, "is_transparent": is_transparent})

    card_slide_count = len(card_slides_data)
    total_pages = 1 + 1 + card_slide_count + 1
    generate_title_card(row_data_with_bg, index, total_pages)

    current_page = 2

    opis_img, opis_transparent = create_base_image(row_data_with_bg)
    opis_bounds = apply_modern_layout(opis_img, row_data_with_bg, transparent_background=opis_transparent)
    opis_left, opis_top, opis_right, opis_bottom = opis_bounds
    opis_width = max(opis_right - opis_left, 1)
    opis_space = max(opis_bottom - opis_top, 1)
    opis_draw = ImageDraw.Draw(opis_img)
    opis_height = get_text_block_height(opis_draw, opis_normalized, font_body, highlight_font, opis_width)
    opis_y = opis_top + max(0, (opis_space - opis_height) / 2)
    draw_rich_text(
        opis_draw,
        int(round(opis_y)),
        opis_normalized,
        font_body,
        highlight_font,
        highlight_color,
        opis_left,
        opis_width,
    )
    opis_img = add_common_elements(opis_img, row_data_with_bg, current_page, total_pages)
    opis_filename = f"{OUTPUT_DIR}/infografika_{index}_{current_page:02d}_opis.png"
    opis_img.save(opis_filename)
    print(f"Zapisano planszę opisu: {opis_filename}")
    current_page += 1

    for idx, slide_data in enumerate(card_slides_data):
        card_text = slide_data.get("title", "")
        price_text = slide_data.get("price", "")
        graphic_entry = card_graphics[idx] if idx < len(card_graphics) else {"image": None, "is_transparent": False}
        card_img_source = graphic_entry.get("image")
        card_is_transparent = graphic_entry.get("is_transparent", False)

        img, background_transparent = create_base_image(row_data_with_bg)
        content_bounds = apply_modern_layout(
            img,
            row_data_with_bg,
            transparent_background=background_transparent or card_is_transparent,
        )
        content_left, content_top, content_right, content_bottom = content_bounds
        content_width = max(content_right - content_left, 1)
        available_space = max(content_bottom - content_top, 1)
        draw = ImageDraw.Draw(img)

        card_img = None
        card_image_height = 0
        if card_img_source:
            card_img = card_img_source.copy()
            max_image_width = max(1, content_width - 2 * CONTENT_PANEL_IMAGE_INSET)
            card_img.thumbnail((max_image_width, CONTENT_PANEL_IMAGE_MAX_HEIGHT), Image.Resampling.LANCZOS)
            card_image_height = card_img.height

        clean_text = card_text.strip()
        price_text_clean = price_text.strip()
        price_metrics = compute_price_metrics(price_text_clean) if price_text_clean else None
        text_height = get_text_block_height(draw, clean_text, font_body, highlight_font, content_width) if clean_text else 0
        image_gap = CONTENT_PANEL_IMAGE_TEXT_GAP if card_img and (price_metrics or clean_text) else 0
        after_price_gap = PRICE_BLOCK_TO_TEXT_GAP if price_metrics and clean_text else 0
        price_block_height = price_metrics["block_height"] if price_metrics else 0
        total_height = card_image_height + image_gap + price_block_height + after_price_gap + text_height
        y_pos = content_top + max(0, (available_space - total_height) / 2)

        if card_img:
            img_x = content_left + (content_width - card_img.width) // 2
            img.paste(card_img, (int(round(img_x)), int(round(y_pos))), card_img)
            y_pos += card_img.height
            if price_metrics or clean_text:
                y_pos += CONTENT_PANEL_IMAGE_TEXT_GAP

        if price_metrics:
            block_width = price_metrics["block_width"]
            block_height = price_metrics["block_height"]
            block_x = content_left + (content_width - block_width) / 2
            block_y = y_pos
            block_rect = (
                int(round(block_x)),
                int(round(block_y)),
                int(round(block_x + block_width)),
                int(round(block_y + block_height)),
            )
            draw.rounded_rectangle(
                block_rect,
                radius=42,
                fill=(15, 15, 24, 220),
                outline=(highlight_color[0], highlight_color[1], highlight_color[2], 170),
                width=3,
            )
            label_x = block_rect[0] + (block_width - price_metrics["label_width"]) / 2
            label_y = block_rect[1] + price_block_padding_y
            draw.text(
                (int(round(label_x)), int(round(label_y))),
                price_label_text,
                font=font_price_label,
                fill=(210, 210, 210),
            )
            value_x = block_rect[0] + (block_width - price_metrics["value_width"]) / 2
            value_y = label_y + price_metrics["label_height"] + price_block_gap
            draw_text_with_shadow(
                draw,
                (int(round(value_x)), int(round(value_y))),
                price_text_clean,
                font_price_value,
                "white",
                shadow_offset=(4, 4),
            )
            y_pos += block_height
            if clean_text:
                y_pos += PRICE_BLOCK_TO_TEXT_GAP

        if clean_text:
            draw_rich_text(
                draw,
                int(round(y_pos)),
                clean_text,
                font_body,
                highlight_font,
                highlight_color,
                content_left,
                content_width,
            )

        img = add_common_elements(img, row_data_with_bg, current_page, total_pages)
        filename = f"{OUTPUT_DIR}/infografika_{index}_{current_page:02d}_karta_{idx+1:02d}.png"
        img.save(filename)
        print(f"Zapisano planszę karty #{idx + 1}: {filename}")
        current_page += 1

    source_value = _get_row_value_with_variants(
        row_data_with_bg,
        _SOURCE_KEY_VARIANTS,
        "",
    )
    normalized_source = _normalize_url_value(source_value)
    if not normalized_source:
        normalized_source = "Brak danych o źródle."

    final_img, final_transparent = create_base_image(row_data_with_bg)
    final_bounds = apply_modern_layout(final_img, row_data_with_bg, transparent_background=final_transparent)
    final_left, final_top, final_right, final_bottom = final_bounds
    final_width = max(final_right - final_left, 1)
    final_space = max(final_bottom - final_top, 1)
    final_draw = ImageDraw.Draw(final_img)

    banner_display = None
    if os.path.exists(BANNER_PATH):
        try:
            banner_display = Image.open(BANNER_PATH).convert("RGBA")
            banner_display.thumbnail(
                (max(1, final_width - 2 * CONTENT_PANEL_IMAGE_INSET), 360),
                Image.Resampling.LANCZOS,
            )
        except Exception as exc:
            print(f"Błąd podczas ładowania banera {BANNER_PATH}: {exc}")
            banner_display = None

    label_text = "Źródło"
    label_bbox = final_draw.textbbox((0, 0), label_text, font=font_source_label)
    label_width = label_bbox[2] - label_bbox[0]
    label_height = label_bbox[3] - label_bbox[1]
    source_text_height = get_text_block_height(final_draw, normalized_source, font_source_body, highlight_font, final_width)

    gap_after_banner = 40 if banner_display and (label_height or source_text_height) else 0
    gap_after_label = 24 if label_height and source_text_height else 0
    banner_height = banner_display.height if banner_display else 0
    total_height = banner_height + gap_after_banner + label_height + gap_after_label + source_text_height
    y_pos = final_top + max(0, (final_space - total_height) / 2)

    if banner_display:
        banner_x = final_left + (final_width - banner_display.width) // 2
        final_img.paste(banner_display, (int(round(banner_x)), int(round(y_pos))), banner_display)
        y_pos += banner_height + gap_after_banner

    if label_height:
        label_x = final_left + (final_width - label_width) / 2
        draw_text_with_shadow(
            final_draw,
            (int(round(label_x)), int(round(y_pos))),
            label_text,
            font_source_label,
            "white",
            shadow_offset=(6, 6),
        )
        y_pos += label_height + gap_after_label

    if source_text_height:
        draw_rich_text(
            final_draw,
            int(round(y_pos)),
            normalized_source,
            font_source_body,
            highlight_font,
            highlight_color,
            final_left,
            final_width,
        )

    final_img = add_common_elements(final_img, row_data_with_bg, current_page, total_pages)
    final_filename = f"{OUTPUT_DIR}/infografika_{index}_{current_page:02d}_zrodlo.png"
    final_img.save(final_filename)
    print(f"Zapisano planszę źródłową: {final_filename}")
# --- NOWOŚĆ: Funkcja do generowania plansz dla rankingu ---
def generate_ranking_cards(row_data, index):
    """Generuje specjalne plansze dla kategorii 'Trendy cen'.

    Tło planszy pobierane jest z kolumny "Tło" (z obsługą wartości
    zastępczych jak w `generate_content_cards`). Wszystkie adresy z
    kolumn "Grafika"/"Grafiki" traktowane są jako kolejne grafiki kart,
    niezależnie od tego, czy rozdzielono je średnikami, czy nowymi liniami.
    """

    row_data_with_bg, _ = _prepare_row_with_background(row_data)

    list_value = _get_row_value_with_variants(
        row_data_with_bg,
        ("Lista kart", "Lista Kart", "Lista_kart", "ListaKart"),
        "",
    )
    ranking_items = _extract_numbered_items(list_value)

    if not ranking_items:
        opis = _get_row_value_with_variants(
            row_data_with_bg,
            _DESCRIPTION_KEY_VARIANTS,
            "",
        )
        fallback_items = [
            _strip_leading_numbering(item)
            for item in re.findall(r'(\d+\.\s.*)', opis)
        ]
        ranking_items = [item for item in fallback_items if item]

    ranking_items = ranking_items[:3]
    if not ranking_items:
        print("Nie znaleziono listy numerowanej w kolumnie 'Lista kart' ani w opisie dla rankingu. Generowanie standardowe.")
        generate_content_cards(row_data_with_bg, index)
        return

    price_values_raw = _get_row_value_with_variants(
        row_data_with_bg,
        ("Ceny w PLN", "CenywPLN", "CenyPLN", "CenywPln", "Ceny wPLN", "Ceny"),
        "",
    )
    price_series = _parse_price_series(price_values_raw, len(ranking_items))

    date_values_raw = _get_row_value_with_variants(
        row_data_with_bg,
        (
            "Daty w PLN",
            "DatywPLN",
            "Daty wPLN",
            "Daty raportu",
            "Daty raportów",
            "Daty kart",
            "DatyKart",
            "Daty",
        ),
        "",
    )
    date_series = _parse_date_series(date_values_raw, len(ranking_items))

    pricing_data = []
    for idx in range(len(ranking_items)):
        card_prices = price_series[idx] if idx < len(price_series) else []
        card_dates = date_series[idx] if idx < len(date_series) else []

        if card_dates and card_prices and len(card_dates) != len(card_prices):
            sync_len = min(len(card_prices), len(card_dates))
            if sync_len > 0:
                card_prices = card_prices[-sync_len:]
                card_dates = card_dates[-sync_len:]
            else:
                card_dates = []
        elif card_dates and not card_prices:
            card_dates = []

        pricing_data.append({
            "prices": card_prices,
            "dates": card_dates,
        })

    graphics_urls = _get_graphics_entries(row_data_with_bg)

    total_pages = 1 + len(ranking_items)
    generate_title_card(row_data_with_bg, index, total_pages)

    font_rank = ImageFont.truetype(HEADER_FONT_PATH, 150)
    font_text = ImageFont.truetype(FONT_PATH, 44)
    font_highlight = ImageFont.truetype(HIGHLIGHT_FONT_PATH, 54)
    font_price = ImageFont.truetype(HEADER_FONT_PATH, 90)
    font_small = ImageFont.truetype(FONT_PATH, 36)
    highlight_color = (255, 223, 100)

    for i, item_text in enumerate(ranking_items):
        card_img_url = graphics_urls[i] if i < len(graphics_urls) else None
        card_img_source = None
        card_is_transparent = False
        if card_img_url:
            card_img_source = fetch_image_from_url(card_img_url)
            if card_img_source:
                card_is_transparent = _is_transparent_png(card_img_source, card_img_url)

        img, background_transparent = create_base_image(row_data_with_bg)
        content_bounds = apply_modern_layout(
            img,
            row_data_with_bg,
            transparent_background=background_transparent or card_is_transparent,
        )
        content_left, content_top, content_right, content_bottom = content_bounds
        content_width = max(content_right - content_left, 1)
        available_space = max(content_bottom - content_top, 1)

        draw = ImageDraw.Draw(img)

        card_img = None
        if card_img_source:
            card_img = card_img_source.copy()
            card_img.thumbnail((
                max(1, content_width - 2 * CONTENT_PANEL_IMAGE_INSET),
                int(CONTENT_PANEL_IMAGE_MAX_HEIGHT * 1.25),
            ), Image.Resampling.LANCZOS)

        clean_text = _strip_leading_numbering(item_text)

        card_price_info = pricing_data[i] if i < len(pricing_data) else {"prices": [], "dates": []}
        price_components, price_block_height = _prepare_price_components(
            card_price_info.get("prices", []),
            card_price_info.get("dates", []),
            font_price,
            font_small,
            content_width,
        )
        after_price_gap = PRICE_BLOCK_TO_TEXT_GAP if price_components and clean_text else 0

        rank_text = str(i + 1)
        rank_height = font_rank.getbbox("A")[3]
        image_block_height = card_img.height + CONTENT_PANEL_IMAGE_TEXT_GAP if card_img else 0
        text_height = get_text_block_height(draw, clean_text, font_text, font_highlight, content_width) if clean_text else 0
        stack_height = rank_height + 30 + image_block_height + price_block_height + after_price_gap + text_height
        y_pos = content_top + max(0, (available_space - stack_height) / 2)

        rank_width = draw.textbbox((0, 0), rank_text, font=font_rank)[2]
        rank_x = content_left + (content_width - rank_width) / 2
        draw_text_with_shadow(draw, (int(round(rank_x)), int(round(y_pos))), rank_text, font_rank, "white", shadow_offset=(8, 8))
        y_pos += rank_height + 30

        if card_img:
            img_x = content_left + (content_width - card_img.width) // 2
            img.paste(card_img, (img_x, int(round(y_pos))), card_img)
            y_pos += card_img.height + CONTENT_PANEL_IMAGE_TEXT_GAP

        if price_components:
            for component_index, component in enumerate(price_components):
                if component.get("type") == "text":
                    text_bbox = draw.textbbox((0, 0), component["text"], font=component["font"])
                    text_width = text_bbox[2] - text_bbox[0]
                    text_x = content_left + (content_width - text_width) / 2
                    position = (int(round(text_x)), int(round(y_pos)))
                    if component.get("shadow"):
                        draw_text_with_shadow(
                            draw,
                            position,
                            component["text"],
                            component["font"],
                            component.get("fill", "white"),
                            shadow_offset=(4, 4),
                        )
                    else:
                        draw.text(position, component["text"], font=component["font"], fill=component.get("fill", "white"))
                    y_pos += component["height"]
                elif component.get("type") == "image" and component.get("image") is not None:
                    spark_image = component["image"]
                    spark_x = content_left + (content_width - spark_image.width) // 2
                    img.paste(spark_image, (int(round(spark_x)), int(round(y_pos))), spark_image)
                    y_pos += spark_image.height

                if component_index < len(price_components) - 1:
                    y_pos += PRICE_COMPONENT_SPACING

            if after_price_gap:
                y_pos += after_price_gap

        if clean_text:
            draw_rich_text(
                draw,
                int(round(y_pos)),
                clean_text,
                font_text,
                font_highlight,
                highlight_color,
                content_left,
                content_width,
            )

        img = add_common_elements(img, row_data_with_bg, i + 2, total_pages)
        filename = f"{OUTPUT_DIR}/infografika_{index}_{i+2:02d}_ranking.png"
        img.save(filename)
        print(f"Zapisano planszę rankingu: {filename}")

def select_csv_file():
    from tkinter import Tk, filedialog
    root = Tk()
    root.withdraw()
    file_path = filedialog.askopenfilename(
        title="Wybierz plik CSV",
        filetypes=[("CSV files", "*.csv")]
    )
    return file_path

# --- Główna funkcja ---
def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    csv_file = select_csv_file()
    if not csv_file:
        print("Nie wybrano pliku CSV. Kończę działanie.")
        return

    try:
        with open(csv_file, mode='r', newline='', encoding='utf-8-sig') as f:
            reader = csv.DictReader(row for row in f if row.strip())
            for i, row in enumerate(reader):
                row = {
                    key: value.replace('\\n', '\n') if isinstance(value, str) else value
                    for key, value in row.items()
                }
                title_for_log = _get_row_title(row, "")
                print(f"\n--- Przetwarzanie artykułu #{i}: {title_for_log} ---")
                category_value = _get_row_value_with_variants(
                    row,
                    _CATEGORY_KEY_VARIANTS,
                    "",
                )
                normalized_category = str(category_value or "").strip().lower()
                if normalized_category == 'trendy cen':
                    generate_ranking_cards(row, i)
                else:
                    generate_content_cards(row, i)
    except FileNotFoundError:
        print("Błąd krytyczny: Nie znaleziono pliku CSV.")
    except Exception as e:
        print(f"Wystąpił nieoczekiwany błąd: {e}")

if __name__ == "__main__":
    main()
