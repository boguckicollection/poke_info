# generator_instagram.py
import os
import csv
from PIL import Image, ImageDraw, ImageFont, ImageFilter
import re
import requests
import io
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

def _extract_extension_from_source(source):
    if not source or not isinstance(source, str):
        return ""
    parsed = urlparse(source)
    path = parsed.path if parsed.scheme else source
    _, ext = os.path.splitext(path)
    return ext.lower()


def _get_row_title(row_data, default=""):
    """Return the title value supporting both accented and unaccented keys."""
    if not row_data:
        return default

    title_keys = ("Tytuł", "Tytul")

    for key in title_keys:
        if key in row_data:
            value = row_data.get(key)
            if value not in (None, ""):
                return value

    for key in title_keys:
        if key in row_data:
            value = row_data.get(key)
            if value is not None:
                return value

    return default


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

    styl = CATEGORY_STYLES.get(row_data.get("Kategoria", ""), CATEGORY_STYLES["Domyślny"])
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


def _resolve_background_source(row_data):
    if not row_data:
        return ""

    for key in ("Tło", "_background_url"):
        candidate = _normalize_url_value(row_data.get(key))
        if candidate:
            return candidate

    grafika_value = row_data.get("Grafika")
    if isinstance(grafika_value, str):
        for part in grafika_value.split(';'):
            candidate = _normalize_url_value(part)
            if candidate:
                return candidate
    else:
        candidate = _normalize_url_value(grafika_value)
        if candidate:
            return candidate

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
    kategoria = row_data.get('Kategoria', 'Domyślny')
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
    source_text = row_data.get('Źródło', '')

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
    """Generuje standardowe plansze z treścią.

    Kolumna "Tło" określa grafikę tła planszy. Kolumna "Grafika" może
    zawierać wiele adresów URL oddzielonych średnikiem – każdy z nich
    traktowany jest jako grafika karty przypisywana kolejno do stron
    z treścią.
    """

    row_data_with_bg, _ = _prepare_row_with_background(row_data)

    graphics_entries = [
        part.strip() for part in (row_data_with_bg.get("Grafika") or "").split(';') if part.strip()
    ]
    card_image_urls = graphics_entries

    opis = row_data_with_bg.get('Opis', "")
    font_text = ImageFont.truetype(FONT_PATH, 42)
    highlight_font = ImageFont.truetype(HIGHLIGHT_FONT_PATH, 44)
    highlight_color = (255, 223, 100)

    _, content_bounds_preview = _calculate_panel_bounds()
    content_left_preview, content_top_preview, content_right_preview, content_bottom_preview = content_bounds_preview
    content_width_preview = max(content_right_preview - content_left_preview, 1)
    available_space_preview = max(content_bottom_preview - content_top_preview, 1)
    image_max_width = max(1, content_width_preview - 2 * CONTENT_PANEL_IMAGE_INSET)

    opis_formatted = re.sub(r'(\s)(?=\d+\.)', '\n', opis)
    text_blocks = [block.strip() for block in opis_formatted.split('\n') if block.strip()]

    temp_draw = ImageDraw.Draw(Image.new('RGBA', (1, 1)))

    card_images = []
    for url in card_image_urls:
        card_img = fetch_image_from_url(url)
        is_transparent_card = False
        if card_img:
            is_transparent_card = _is_transparent_png(card_img, url)
            card_img.thumbnail((image_max_width, CONTENT_PANEL_IMAGE_MAX_HEIGHT), Image.Resampling.LANCZOS)
        card_images.append({
            "image": card_img,
            "is_transparent": is_transparent_card,
        })

    def card_at(idx):
        return card_images[idx] if 0 <= idx < len(card_images) else None

    def get_image_block_height(card_image):
        return card_image.height + CONTENT_PANEL_IMAGE_TEXT_GAP if card_image else 0

    pages = []
    current_blocks = []
    current_text_height = 0
    card_pointer = 0
    current_card_entry = card_at(card_pointer)
    current_card_image = current_card_entry["image"] if current_card_entry else None
    current_image_block_height = get_image_block_height(current_card_image)

    for block in text_blocks:
        block_height = get_text_block_height(temp_draw, block, font_text, highlight_font, content_width_preview)
        projected_height = current_image_block_height + current_text_height + block_height
        if current_blocks and projected_height > available_space_preview:
            pages.append({
                "text": "\n".join(current_blocks),
                "card": current_card_entry,
            })
            card_pointer += 1
            current_card_entry = card_at(card_pointer)
            current_card_image = current_card_entry["image"] if current_card_entry else None
            current_image_block_height = get_image_block_height(current_card_image)
            current_blocks = []
            current_text_height = 0

        current_blocks.append(block)
        current_text_height += block_height

    if current_blocks or current_card_entry:
        pages.append({
            "text": "\n".join(current_blocks),
            "card": current_card_entry,
        })
        card_pointer += 1

    while card_pointer < len(card_images):
        pages.append({
            "text": "",
            "card": card_at(card_pointer),
        })
        card_pointer += 1

    if not pages:
        pages.append({
            "text": "",
            "card": None,
        })

    total_pages = 1 + len(pages)
    generate_title_card(row_data_with_bg, index, total_pages)

    for p, page_data in enumerate(pages):
        card_entry = page_data.get("card")
        card_img_source = card_entry["image"] if card_entry else None
        card_is_transparent = card_entry["is_transparent"] if card_entry else False

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

        text_chunk = page_data["text"]
        card_img = None
        if card_img_source:
            card_img = card_img_source.copy()
            card_img.thumbnail((max(1, content_width - 2 * CONTENT_PANEL_IMAGE_INSET), CONTENT_PANEL_IMAGE_MAX_HEIGHT), Image.Resampling.LANCZOS)

        image_block_height = get_image_block_height(card_img)
        text_height = get_text_block_height(draw, text_chunk, font_text, highlight_font, content_width) if text_chunk else 0
        content_height = image_block_height + text_height

        y_pos = content_top + max(0, (available_space - content_height) / 2)

        if card_img:
            img_x = content_left + (content_width - card_img.width) // 2
            img.paste(card_img, (img_x, int(round(y_pos))), card_img)
            y_pos += card_img.height + CONTENT_PANEL_IMAGE_TEXT_GAP

        if text_chunk:
            draw_rich_text(
                draw,
                int(round(y_pos)),
                text_chunk,
                font_text,
                highlight_font,
                highlight_color,
                content_left,
                content_width,
            )

        img = add_common_elements(img, row_data_with_bg, p + 2, total_pages)

        filename = f"{OUTPUT_DIR}/infografika_{index}_{p+2:02d}_tresc.png"
        img.save(filename)
        print(f"Zapisano planszę z treścią: {filename}")

# --- NOWOŚĆ: Funkcja do generowania plansz dla rankingu ---
def generate_ranking_cards(row_data, index):
    """Generuje specjalne plansze dla kategorii 'Trendy cen'.

    Tło planszy pobierane jest z kolumny "Tło" (z obsługą wartości
    zastępczych jak w `generate_content_cards`). Wszystkie adresy z
    kolumny "Grafika" traktowane są jako kolejne grafiki kart.
    """

    row_data_with_bg, _ = _prepare_row_with_background(row_data)

    opis = row_data_with_bg.get('Opis', "")
    graphics_urls = [
        u.strip() for u in (row_data_with_bg.get('Grafika') or "").split(';') if u.strip()
    ]

    list_items = re.findall(r'(\d+\.\s.*)', opis)
    if not list_items:
        print("Nie znaleziono listy numerowanej w opisie dla rankingu. Generowanie standardowe.")
        generate_content_cards(row_data_with_bg, index)
        return

    total_pages = 1 + len(list_items)
    generate_title_card(row_data_with_bg, index, total_pages)

    font_rank = ImageFont.truetype(HEADER_FONT_PATH, 150)
    font_text = ImageFont.truetype(FONT_PATH, 44)
    font_highlight = ImageFont.truetype(HIGHLIGHT_FONT_PATH, 54)
    highlight_color = (255, 223, 100)

    for i, item_text in enumerate(list_items):
        card_img_url = graphics_urls[i].strip() if i < len(graphics_urls) else None
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

        clean_text = re.sub(r'^\d+\.\s*', '', item_text).strip()
        rank_text = str(i + 1)
        rank_height = font_rank.getbbox("A")[3]
        image_block_height = card_img.height + CONTENT_PANEL_IMAGE_TEXT_GAP if card_img else 0
        text_height = get_text_block_height(draw, clean_text, font_text, font_highlight, content_width) if clean_text else 0
        stack_height = rank_height + 30 + image_block_height + text_height
        y_pos = content_top + max(0, (available_space - stack_height) / 2)

        rank_width = draw.textbbox((0, 0), rank_text, font=font_rank)[2]
        rank_x = content_left + (content_width - rank_width) / 2
        draw_text_with_shadow(draw, (int(round(rank_x)), int(round(y_pos))), rank_text, font_rank, "white", shadow_offset=(8, 8))
        y_pos += rank_height + 30

        if card_img:
            img_x = content_left + (content_width - card_img.width) // 2
            img.paste(card_img, (img_x, int(round(y_pos))), card_img)
            y_pos += card_img.height + CONTENT_PANEL_IMAGE_TEXT_GAP

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
                if row.get('Kategoria') == 'Trendy cen':
                    generate_ranking_cards(row, i)
                else:
                    generate_content_cards(row, i)
    except FileNotFoundError:
        print("Błąd krytyczny: Nie znaleziono pliku CSV.")
    except Exception as e:
        print(f"Wystąpił nieoczekiwany błąd: {e}")

if __name__ == "__main__":
    main()
