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

def draw_rich_text(draw, start_y, text, font, highlight_font, highlight_color):
    """Rysuje tekst, wyróżniając kluczowe słowa, ceny i daty."""
    y = start_y
    max_x = WIDTH - PADDING
    line_height = font.getbbox("A")[3] + 15
    
    price_pattern = r'(\d[\d\s,.]*\s?(?:USD|dolarów|zł|PLN|eur|euro|£|GBP))'
    date_pattern = r'(\d{1,2}\s(?:stycznia|lutego|marca|kwietnia|maja|czerwca|lipca|sierpnia|września|października|listopada|grudnia)\s\d{4}\s?r?\.)'
    proper_names = ['Lost Origin', '151 ETB', 'Kingdra ex', 'Greninja ex', 'Prismatic Pokémon Center ETB', 'Mewtwo SVP052', 'Magneton PC', 'Noctowl PC', 'Celebration Fanfare', 'PSA 10']
    proper_names_pattern = '|'.join(re.escape(name) for name in proper_names)
    full_pattern = re.compile(f'({price_pattern}|{date_pattern}|{proper_names_pattern})', re.IGNORECASE)
    
    lines = text.split('\n')
    for line in lines:
        x = PADDING
        words = line.split(' ')
        for word in words:
            clean_word = re.sub(r'[^\w\s-]', '', word)
            is_highlighted = full_pattern.fullmatch(clean_word)
            current_font = highlight_font if is_highlighted else font
            current_color = highlight_color if is_highlighted else "white"
            
            part_width = draw.textbbox((0,0), word, font=current_font)[2]

            if x + part_width > max_x:
                x = PADDING
                y += line_height

            draw_text_with_shadow(draw, (x, y), word, current_font, current_color, shadow_offset=(2,2))
            x += part_width + draw.textbbox((0,0), " ", font=current_font)[2]
        y += line_height

def get_text_block_height(draw, text_block, font):
    """Oblicza wysokość bloku tekstu."""
    y = 0
    x = PADDING
    max_x = WIDTH - PADDING
    line_height = font.getbbox("A")[3] + 15
    words = text_block.split()
    for word in words:
        part_width = draw.textbbox((0,0), word, font=font)[2]
        if x + part_width > max_x:
            x = PADDING
            y += line_height
        x += part_width + draw.textbbox((0,0), " ", font=font)[2]
    return y + line_height

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

    opis_formatted = re.sub(r'(\s)(?=\d+\.)', '\n', opis)
    text_blocks = [block.strip() for block in opis_formatted.split('\n') if block.strip()]

    temp_draw = ImageDraw.Draw(Image.new('RGB', (1,1)))
    MAX_Y = HEIGHT - FOOTER_HEIGHT - PADDING

    card_images = []
    for url in card_image_urls:
        card_img = fetch_image_from_url(url)
        if card_img:
            card_img.thumbnail((WIDTH - 3 * PADDING, 500), Image.Resampling.LANCZOS)
        card_images.append(card_img)

    def get_card_for_page(idx):
        return card_images[idx] if idx < len(card_images) else None

    def get_image_block_height(card_image):
        return card_image.height + 60 if card_image else 0

    pages = []
    current_blocks = []
    page_index = 0
    current_card_img = get_card_for_page(page_index)
    current_image_block_height = get_image_block_height(current_card_img)
    y_cursor = PADDING + 80 + current_image_block_height

    for block in text_blocks:
        block_height = get_text_block_height(temp_draw, block, font_text)
        if current_blocks and y_cursor + block_height > MAX_Y:
            pages.append({
                "text": "\n".join(current_blocks),
                "image": current_card_img,
                "image_block_height": current_image_block_height,
            })
            page_index += 1
            current_card_img = get_card_for_page(page_index)
            current_image_block_height = get_image_block_height(current_card_img)
            y_cursor = PADDING + 80 + current_image_block_height
            current_blocks = []

        current_blocks.append(block)
        y_cursor += block_height

    if current_blocks:
        pages.append({
            "text": "\n".join(current_blocks),
            "image": current_card_img,
            "image_block_height": current_image_block_height,
        })

    if not pages:
        first_card = get_card_for_page(0)
        pages.append({
            "text": "",
            "image": first_card,
            "image_block_height": get_image_block_height(first_card),
        })

    total_pages = 1 + len(pages)
    generate_title_card(row_data_with_bg, index, total_pages)

    for p, page_data in enumerate(pages):
        img = create_base_image(row_data_with_bg)
        draw = ImageDraw.Draw(img)

        text_chunk = page_data["text"]
        card_img = page_data["image"]
        image_block_height = page_data["image_block_height"]

        text_height = get_text_block_height(draw, text_chunk, font_text)
        content_height = image_block_height + text_height

        available_space = HEIGHT - PADDING - FOOTER_HEIGHT
        y_pos = PADDING + (available_space - content_height) / 2

        if card_img:
            img_x = (WIDTH - card_img.width) // 2
            img.paste(card_img, (img_x, int(y_pos)), card_img)
            y_pos += card_img.height + 60

        draw_rich_text(draw, int(y_pos), text_chunk, font_text, highlight_font, highlight_color)

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
    price_color = (255, 223, 100)

    price_pattern = re.compile(r'\d[\d\s,.]*(?:zł|PLN|eur|USD|GBP|€|\$|£)', re.IGNORECASE)

    for i, item_text in enumerate(list_items):
        img = create_base_image(row_data)
        draw = ImageDraw.Draw(img)

        card_img_url = graphics_urls[i].strip() if i < len(graphics_urls) else None
        content_y = PADDING

        # Numer rankingu
        draw_text_with_shadow(draw, (PADDING, content_y), str(i + 1), font_rank, "white", shadow_offset=(8, 8))
        content_y += font_rank.getbbox("A")[3] + 40

        # Grafika karty (powiększenie 2x)
        if card_img_url:
            card_img = fetch_image_from_url(card_img_url)
            if card_img:
                scale_factor = 2
                new_width = min(card_img.width * scale_factor, WIDTH - 2 * PADDING)
                scale = new_width / card_img.width
                new_height = int(card_img.height * scale)
                card_img = card_img.resize((new_width, new_height), Image.Resampling.LANCZOS)

                img_x = (WIDTH - new_width) // 2
                img.paste(card_img, (img_x, content_y), card_img)
                content_y += new_height + 40

        # Opis (bez numeru, z wyróżnionymi cenami)
        clean_text = re.sub(r'^\d+\.\s*', '', item_text)
        words = clean_text.split()
        x = PADDING
        y = content_y
        max_x = WIDTH - PADDING

        for word in words:
            is_price = price_pattern.fullmatch(word)
            current_font = font_highlight if is_price else font_text
            color = price_color if is_price else "white"
            w = draw.textbbox((0, 0), word, font=current_font)[2]

            if x + w > max_x:
                x = PADDING
                y += current_font.getbbox("A")[3] + 12

            draw_text_with_shadow(draw, (x, y), word, current_font, color, shadow_offset=(2, 2))
            x += w + draw.textbbox((0, 0), " ", font=current_font)[2]

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
