# generator_instagram.py
import os
import csv
from PIL import Image, ImageDraw, ImageFont, ImageFilter
import re
import requests
import io
from datetime import datetime

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

def fetch_image_from_url(url):
    if not url or not url.startswith('http'):
        return None
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        response = requests.get(url, headers=headers, timeout=15)
        response.raise_for_status()
        return Image.open(io.BytesIO(response.content)).convert("RGBA")
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


def apply_modern_layout(img, row_data):
    """Rysuje półtransparentny panel tła dla głównej treści."""

    panel_bounds, content_bounds = _calculate_panel_bounds()

    panel_width = panel_bounds[2] - panel_bounds[0]
    panel_height = panel_bounds[3] - panel_bounds[1]
    if panel_width <= 0 or panel_height <= 0:
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

def create_base_image(row_data):
    # "Grafika" może zawierać wiele adresów URL oddzielonych średnikiem;
    # pierwszy z nich służy jako tło planszy. Jeśli w danych przekazano
    # klucz `_background_url`, traktujemy go jako nadrzędny (np. po
    # wcześniejszym parsowaniu pól w `generate_content_cards`).
    image_source = row_data.get("_background_url")
    if not image_source:
        image_source = (row_data.get("Grafika") or "").split(';')[0].strip()
    kategoria = row_data.get('Kategoria', 'Domyślny')
    styl = CATEGORY_STYLES.get(kategoria, CATEGORY_STYLES['Domyślny'])
    base_image = fetch_image_from_url(image_source)
    if base_image:
        scale = max(WIDTH / base_image.width, HEIGHT / base_image.height)
        new_size = (int(base_image.width * scale), int(base_image.height * scale))
        base_image = base_image.resize(new_size, Image.Resampling.LANCZOS)
        left, top = (base_image.width - WIDTH) / 2, (base_image.height - HEIGHT) / 2
        img = base_image.crop((left, top, left + WIDTH, top + HEIGHT))
        img = img.filter(ImageFilter.GaussianBlur(30))
        overlay = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 160))
        img = Image.alpha_composite(img, overlay)
    else:
        img = Image.new("RGBA", (WIDTH, HEIGHT), (30, 30, 30, 255))
    draw = ImageDraw.Draw(img)
    generate_gradient_frame(draw, styl['colors'])
    return img

def add_common_elements(img, row_data, page_num, total_pages):
    draw = ImageDraw.Draw(img)
    font_footer = ImageFont.truetype(FONT_PATH, 28)
    font_number = ImageFont.truetype(FONT_PATH, 26)
    source_text = row_data.get('Źródło', '')

    if source_text:
        draw.text((PADDING, HEIGHT - 120), "Źródło:", font=font_footer, fill=(180, 180, 180))
        draw.text((PADDING, HEIGHT - 90), source_text, font=font_footer, fill="white")

    page_info = f"{page_num}/{total_pages}"
    page_width = draw.textbbox((0, 0), page_info, font=font_number)[2]
    draw.text((WIDTH - PADDING - page_width, PADDING - 20), page_info, font=font_number, fill="gray")

    if os.path.exists(BANNER_PATH):
        banner = Image.open(BANNER_PATH).convert("RGBA")
        banner.thumbnail((300, 80), Image.Resampling.LANCZOS)
        img.paste(banner, (WIDTH - PADDING - banner.width, HEIGHT - FOOTER_HEIGHT + 40), banner)

    logo_source = (row_data.get("Logo") or "").strip()
    logo_img = None

    if logo_source:
        if logo_source.startswith("http"):
            logo_img = fetch_image_from_url(logo_source)
        elif os.path.exists(logo_source):
            logo_img = Image.open(logo_source).convert("RGBA")

    if logo_img is None and os.path.exists("PTCG.png"):
        logo_img = Image.open("PTCG.png").convert("RGBA")

    if logo_img:
        logo_img.thumbnail((200, 60), Image.Resampling.LANCZOS)
        logo_x = (WIDTH - logo_img.width) // 2
        img.paste(logo_img, (logo_x, HEIGHT - 70), logo_img)

    return img

# --- Główne funkcje generujące ---

def generate_title_card(row_data, index, total_pages):
    """Generuje planszę tytułową z idealnie wyśrodkowanym tekstem."""
    img = create_base_image(row_data)
    draw = ImageDraw.Draw(img)
    
    tytul = row_data.get('Tytuł', 'Brak tytułu')
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
    wrapped_lines = []

    for raw_line in text.split('\n'):
        words = raw_line.split(' ')
        current_line = []
        current_width = 0

        for word in words:
            clean_word = re.sub(r'[^\w\s-]', '', word)
            is_highlighted = bool(HIGHLIGHT_PATTERN.fullmatch(clean_word))
            current_font = highlight_font if is_highlighted else font

            word_width = draw.textbbox((0, 0), word, font=current_font)[2]
            space_after = draw.textbbox((0, 0), " ", font=current_font)[2]

            if current_line and usable_width and current_width + word_width > usable_width:
                wrapped_lines.append(current_line)
                current_line = []
                current_width = 0

            current_line.append({
                "text": word,
                "font": current_font,
                "is_highlighted": is_highlighted,
                "word_width": word_width,
                "space_after": space_after,
            })

            current_width += word_width + space_after

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

    W kolumnie "Grafika" można podać adresy URL oddzielone średnikiem;
    pierwszy z nich służy jako tło planszy, a kolejne – jako grafiki kart
    przypisywane kolejno do stron z treścią.
    """

    graphics_entries = [part.strip() for part in (row_data.get("Grafika") or "").split(';') if part.strip()]
    background_url = graphics_entries[0] if graphics_entries else ""
    card_image_urls = graphics_entries[1:]

    row_data_with_bg = dict(row_data)
    if background_url:
        row_data_with_bg["_background_url"] = background_url

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
        if card_img:
            card_img = card_img.convert("RGBA")
            card_img.thumbnail((image_max_width, CONTENT_PANEL_IMAGE_MAX_HEIGHT), Image.Resampling.LANCZOS)
        card_images.append(card_img)

    def card_at(idx):
        return card_images[idx] if 0 <= idx < len(card_images) else None

    def get_image_block_height(card_image):
        return card_image.height + CONTENT_PANEL_IMAGE_TEXT_GAP if card_image else 0

    pages = []
    current_blocks = []
    current_text_height = 0
    card_pointer = 0
    current_card_img = card_at(card_pointer)
    current_image_block_height = get_image_block_height(current_card_img)

    for block in text_blocks:
        block_height = get_text_block_height(temp_draw, block, font_text, highlight_font, content_width_preview)
        projected_height = current_image_block_height + current_text_height + block_height
        if current_blocks and projected_height > available_space_preview:
            pages.append({
                "text": "\n".join(current_blocks),
                "image": current_card_img,
            })
            card_pointer += 1
            current_card_img = card_at(card_pointer)
            current_image_block_height = get_image_block_height(current_card_img)
            current_blocks = []
            current_text_height = 0

        current_blocks.append(block)
        current_text_height += block_height

    if current_blocks or current_card_img:
        pages.append({
            "text": "\n".join(current_blocks),
            "image": current_card_img,
        })
        card_pointer += 1

    while card_pointer < len(card_images):
        pages.append({
            "text": "",
            "image": card_at(card_pointer),
        })
        card_pointer += 1

    if not pages:
        pages.append({
            "text": "",
            "image": None,
        })

    total_pages = 1 + len(pages)
    generate_title_card(row_data_with_bg, index, total_pages)

    for p, page_data in enumerate(pages):
        img = create_base_image(row_data_with_bg)
        content_bounds = apply_modern_layout(img, row_data_with_bg)
        content_left, content_top, content_right, content_bottom = content_bounds
        content_width = max(content_right - content_left, 1)
        available_space = max(content_bottom - content_top, 1)

        draw = ImageDraw.Draw(img)

        text_chunk = page_data["text"]
        card_img = page_data["image"]
        if card_img:
            card_img = card_img.copy()
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

    Dodatkowe grafiki kart są pobierane z kolumny "Grafika" –
    po pierwszym adresie tła można dodać kolejne URL-e oddzielone średnikiem.
    """
    opis = row_data.get('Opis', "")
    graphics_urls = [u.strip() for u in (row_data.get('Grafika') or "").split(';')[1:] if u.strip()]

    list_items = re.findall(r'(\d+\.\s.*)', opis)
    if not list_items:
        print("Nie znaleziono listy numerowanej w opisie dla rankingu. Generowanie standardowe.")
        generate_content_cards(row_data, index)
        return

    total_pages = 1 + len(list_items)
    generate_title_card(row_data, index, total_pages)

    font_rank = ImageFont.truetype(HEADER_FONT_PATH, 150)
    font_text = ImageFont.truetype(FONT_PATH, 44)
    font_highlight = ImageFont.truetype(HIGHLIGHT_FONT_PATH, 54)
    highlight_color = (255, 223, 100)

    for i, item_text in enumerate(list_items):
        img = create_base_image(row_data)
        content_bounds = apply_modern_layout(img, row_data)
        content_left, content_top, content_right, content_bottom = content_bounds
        content_width = max(content_right - content_left, 1)
        available_space = max(content_bottom - content_top, 1)

        draw = ImageDraw.Draw(img)

        card_img_url = graphics_urls[i].strip() if i < len(graphics_urls) else None
        card_img = None
        if card_img_url:
            card_img = fetch_image_from_url(card_img_url)
            if card_img:
                card_img = card_img.convert("RGBA")
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

        img = add_common_elements(img, row_data, i + 2, total_pages)
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
                print(f"\n--- Przetwarzanie artykułu #{i}: {row.get('Tytuł', '')} ---")
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
