import pandas as pd
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageOps, ImageColor
import requests
from io import BytesIO
import os
import re
import textwrap
import matplotlib.pyplot as plt
import matplotlib
matplotlib.use('Agg') # Użyj backendu nieinteraktywnego

# --- KONFIGURACJA ---
CSV_FILE = 'pokemon_tcg_report_09_19.csv'
LOGO_PTCG_FILE = 'PTCG.png'
LOGO_SHOP_FILE = 'banner22.png'
OUTPUT_DIR = 'output'

# Ścieżki do czcionek
FONT_BOLD_PATH = os.path.join('fonts', 'Poppins-Bold.ttf')
FONT_REGULAR_PATH = os.path.join('fonts', 'Poppins-Regular.ttf')

# Wymiary planszy
BOARD_WIDTH, BOARD_HEIGHT = 1080, 1080

# Palety kolorów
PALETTES = {
    'top3 tygodnia': {'frame': '#F4A261', 'title_bg': '#264653', 'title_text': '#FFFFFF', 'chart': '#E76F51'},
    'inwestycje': {'frame': '#2A9D8F', 'title_bg': '#264653', 'title_text': '#FFFFFF', 'chart': '#E9C46A'},
    'default': {'frame': '#E76F51', 'title_bg': '#264653', 'title_text': '#FFFFFF', 'chart': '#F4A261'}
}

# --- FUNKCJE POMOCNICZE ---

def parse_price_data(price_string):
    """Przetwarza ciąg cenowy, aby wyodrębnić wartości PLN i procent."""
    try:
        # Adjusted regex to handle various delimiters and optional currency symbols
        pln_match = re.search(r"≈? ([\d,.]+) [€$PLN]+(?: → ([\d,.]+) [€$PLN]+)?", price_string)
        
        start_pln = float(pln_match.group(1).replace(',', '').replace('€', '').replace('$', '')) if pln_match and pln_match.group(1) else 0
        end_pln = float(pln_match.group(2).replace(',', '').replace('€', '').replace('$', '')) if pln_match and pln_match.group(2) else start_pln # If only one price, end_pln is same as start_pln
        
        percentage_match = re.search(r"→ ([+-][\d.]+)%", price_string)
        percentage = f"{percentage_match.group(1)}%" if percentage_match else "0%"
        
        return start_pln, end_pln, percentage
    except (AttributeError, ValueError) as e:
        print(f"Błąd parsowania ceny: '{price_string}'. Błąd: {e}")
        return 0, 0, "N/A"


def create_price_chart(start_price, end_price, color):
    """Tworzy obraz wykresu wzrostu ceny."""
    # Handle cases where prices are the same or decrease
    if start_price == 0 or end_price == 0:
        return Image.new('RGBA', (250, 120), (0,0,0,0)) # Return empty for invalid prices

    fig, ax = plt.subplots(figsize=(2.5, 1.2), dpi=150)
    x = [0, 1]
    y = [start_price, end_price]
    
    # Check for price decrease to adjust color if needed (optional)
    line_color = '#E76F51' if end_price < start_price else color # Red for decrease, original for increase/same
    
    ax.plot(x, y, color=line_color, linewidth=5, solid_capstyle='round')
    
    # Wypełnienie gradientowe
    line = ax.lines[0]
    x_data, y_data = line.get_data()
    ax.fill_between(x_data, y_data, color=line_color, alpha=0.2)
    
    # Stylowane znaczniki
    ax.plot(x[0], y[0], 'o', color=line_color, markersize=10, markeredgecolor='white', markeredgewidth=2)
    ax.plot(x[1], y[1], 'o', color=line_color, markersize=10, markeredgecolor='white', markeredgewidth=2)
    
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.spines['left'].set_visible(False)
    ax.spines['bottom'].set_visible(False)
    ax.tick_params(axis='both', which='both', bottom=False, top=False, left=False, right=False, labelbottom=False, labelleft=False)
    ax.set_facecolor('none')
    fig.patch.set_alpha(0.0)

    # Marginesy
    y_padding = (max(y) - min(y)) * 0.1
    # Avoid zero division if prices are the same
    if y_padding == 0 and start_price != 0: 
        y_padding = start_price * 0.1
    elif y_padding == 0 and start_price == 0:
        y_padding = 1 # A small default padding if prices are 0
        
    ax.set_ylim(min(y) - y_padding, max(y) + y_padding)
    ax.set_xlim(-0.1, 1.1)

    buf = BytesIO()
    fig.savefig(buf, format='png', transparent=True, bbox_inches='tight', pad_inches=0.1)
    buf.seek(0)
    plt.close(fig)
    return Image.open(buf)

def download_image(url):
    """Pobiera obraz z URL."""
    try:
        response = requests.get(url, timeout=15)
        response.raise_for_status()
        return Image.open(BytesIO(response.content)).convert("RGBA")
    except requests.exceptions.RequestException as e:
        print(f"Nie udało się pobrać obrazu z {url}. Błąd: {e}")
        return Image.new('RGBA', (200, 280), '#DDD')

def create_default_background(color1='#264653', color2='#2A9D8F'):
    """Generuje domyślne tło z gradientem."""
    new_img = Image.new('RGB', (BOARD_WIDTH, BOARD_HEIGHT))
    draw = ImageDraw.Draw(new_img)
    
    r1, g1, b1 = ImageColor.getrgb(color1)
    r2, g2, b2 = ImageColor.getrgb(color2)
    
    for i in range(BOARD_HEIGHT):
        r = int(r1 + (r2 - r1) * i / BOARD_HEIGHT)
        g = int(g1 + (g2 - g1) * i / BOARD_HEIGHT)
        b = int(b1 + (b2 - b1) * i / BOARD_HEIGHT)
        draw.line([(0, i), (BOARD_WIDTH, i)], fill=(r, g, b))
        
    return new_img.filter(ImageFilter.GaussianBlur(5))

def create_blurred_background(image_url):
    """Tworzy rozmyte tło z podanego obrazu lub domyślne tło."""
    if pd.isna(image_url) or not isinstance(image_url, str) or not image_url.startswith('http'):
        return create_default_background()

    bg_image = download_image(image_url)
    if bg_image.size == (200, 280) and bg_image.getpixel((0,0)) == (221, 221, 221, 255): # Check for default placeholder image
        return create_default_background()
        
    img_width, img_height = bg_image.size
    board_aspect = BOARD_WIDTH / BOARD_HEIGHT
    img_aspect = img_width / img_height

    if img_aspect > board_aspect:
        new_height = BOARD_HEIGHT
        new_width = int(new_height * img_aspect)
    else:
        new_width = BOARD_WIDTH
        new_height = int(new_width / img_aspect)

    bg_image_resized = bg_image.resize((new_width, new_height), Image.Resampling.LANCZOS)

    left = (new_width - BOARD_WIDTH) / 2
    top = (new_height - BOARD_HEIGHT) / 2
    right = (new_width + BOARD_WIDTH) / 2
    bottom = (new_height + BOARD_HEIGHT) / 2

    bg_image_cropped = bg_image_resized.crop((left, top, right, bottom))
    
    return bg_image_cropped.filter(ImageFilter.GaussianBlur(20))

def draw_text_with_shadow(draw, position, text, font, fill, shadow_color=(0,0,0,128)):
    """Rysuje tekst z cieniem."""
    x, y = position
    draw.text((x+2, y+2), text, font=font, fill=shadow_color)
    draw.text((x, y), text, font=font, fill=fill)

def draw_common_elements(draw, slide_num, total_slides, palette):
    """Rysuje ramkę i numerację slajdu."""
    frame_width = 20
    draw.rectangle([(0, 0), (BOARD_WIDTH, BOARD_HEIGHT)], outline=palette['frame'], width=frame_width)
    
    font_page_num = ImageFont.truetype(FONT_BOLD_PATH, 32)
    page_text = f"{slide_num} / {total_slides}"
    page_bbox = draw.textbbox((0, 0), page_text, font_page_num)
    page_width = page_bbox[2] - page_bbox[0]
    draw_text_with_shadow(draw, (BOARD_WIDTH - page_width - 40, 30), page_text, font_page_num, '#FFFFFF')

# --- FUNKCJE GENERUJĄCE SLAJDY ---

def generate_title_slide(data, palette, slide_num, total_slides):
    board = create_blurred_background(data.get('tlo')) # Use .get() for safety
    draw = ImageDraw.Draw(board, 'RGBA')
    draw_common_elements(draw, slide_num, total_slides, palette)
    
    font_title = ImageFont.truetype(FONT_BOLD_PATH, 95)
    title_text = data['tytul']
    
    lines = textwrap.wrap(title_text, width=20)
    
    # Calculate total text height dynamically
    text_heights = [draw.textbbox((0,0), line, font=font_title)[3] - draw.textbbox((0,0), line, font=font_title)[1] for line in lines]
    total_text_height = sum(text_heights) + (len(lines) - 1) * 15 # Add spacing between lines

    y_start = (BOARD_HEIGHT - total_text_height) / 2
    
    current_y = y_start
    for i, line in enumerate(lines):
        line_bbox = draw.textbbox((0,0), line, font=font_title)
        line_width = line_bbox[2] - line_bbox[0]
        x_pos = (BOARD_WIDTH - line_width) / 2
        draw_text_with_shadow(draw, (x_pos, current_y), line, font_title, '#FFFFFF')
        current_y += (line_bbox[3] - line_bbox[1]) + 15 # Move to the next line with spacing
        
    return board

def generate_description_slide(data, palette, slide_num, total_slides):
    board = create_blurred_background(data.get('tlo'))
    draw = ImageDraw.Draw(board, 'RGBA')
    draw_common_elements(draw, slide_num, total_slides, palette)
    
    font_desc = ImageFont.truetype(FONT_REGULAR_PATH, 50)
    desc_text = data['opis']
    
    lines = textwrap.wrap(desc_text, width=35)
    
    text_heights = [draw.textbbox((0,0), line, font=font_desc)[3] - draw.textbbox((0,0), line, font=font_desc)[1] for line in lines]
    total_text_height = sum(text_heights) + (len(lines) - 1) * 15
    
    y_start = (BOARD_HEIGHT - total_text_height) / 2
    
    current_y = y_start
    for i, line in enumerate(lines):
        line_bbox = draw.textbbox((0,0), line, font=font_desc)
        line_width = line_bbox[2] - line_bbox[0]
        x_pos = (BOARD_WIDTH - line_width) / 2
        draw_text_with_shadow(draw, (x_pos, current_y), line, font_desc, '#FFFFFF')
        current_y += (line_bbox[3] - line_bbox[1]) + 15
        
    return board
    
def generate_card_slide(card_name, card_image_url, card_price_str, palette, slide_num, total_slides):
    board = create_blurred_background(card_image_url)
    draw = ImageDraw.Draw(board, 'RGBA')
    draw_common_elements(draw, slide_num, total_slides, palette)
    
    # Karta
    card_image = download_image(card_image_url)
    card_width, card_height = 540, 754
    # Check if image is valid before resizing
    if card_image.mode == 'RGBA' and card_image.getpixel((0,0)) != (221, 221, 221, 255):
        card_image.thumbnail((card_width, card_height), Image.Resampling.LANCZOS)
    else: # Use a placeholder if download failed
        card_image = Image.new('RGBA', (card_width, card_height), '#999999') # Grey placeholder
        draw_temp = ImageDraw.Draw(card_image)
        font_temp = ImageFont.truetype(FONT_REGULAR_PATH, 30)
        temp_text = "Brak obrazu"
        temp_bbox = draw_temp.textbbox((0,0), temp_text, font=font_temp)
        temp_text_width = temp_bbox[2] - temp_bbox[0]
        temp_text_height = temp_bbox[3] - temp_bbox[1]
        draw_temp.text(((card_width - temp_text_width)/2, (card_height - temp_text_height)/2), temp_text, font=font_temp, fill='#FFFFFF')


    card_x = (BOARD_WIDTH - card_image.width) // 2
    card_y = 80
    board.paste(card_image, (card_x, card_y), card_image)
    
    # Nazwa karty
    font_card_name = ImageFont.truetype(FONT_BOLD_PATH, 42)
    clean_name = re.sub(r'^\d+\.\s*', '', card_name)
    wrapped_name = textwrap.wrap(clean_name, width=25)
    name_y_start = card_y + card_image.height + 25
    
    for i, line in enumerate(wrapped_name):
        name_bbox = draw.textbbox((0,0), line, font=font_card_name)
        draw_text_with_shadow(draw, ((BOARD_WIDTH - (name_bbox[2] - name_bbox[0]))/2, name_y_start + i * 45), line, font_card_name, '#FFFFFF')

    # Ceny i wykres
    start_pln, end_pln, percentage = parse_price_data(card_price_str)
    
    # Format prices to 2 decimal places and use space as thousands separator
    price_text = f"{start_pln:,.2f} PLN → {end_pln:,.2f} PLN".replace(',', ' ')
    percent_text = f"{percentage}"
    
    font_price = ImageFont.truetype(FONT_REGULAR_PATH, 38)
    font_percent = ImageFont.truetype(FONT_BOLD_PATH, 48)
    
    price_y_pos = name_y_start + len(wrapped_name) * 45
    
    price_bbox = draw.textbbox((0,0), price_text, font_price)
    draw_text_with_shadow(draw, ((BOARD_WIDTH - (price_bbox[2] - price_bbox[0]))/2, price_y_pos), price_text, font_price, '#FFFFFF')

    # Determine percentage text color
    percent_color = '#4CAF50' # Green for positive
    if percentage.startswith('-'):
        percent_color = '#E76F51' # Red for negative
    elif percentage == "0%" or percentage == "N/A":
        percent_color = '#FFFFFF' # White for no change or N/A
    
    percent_bbox = draw.textbbox((0,0), percent_text, font=font_percent)
    draw_text_with_shadow(draw, ((BOARD_WIDTH - (percent_bbox[2] - percent_bbox[0]))/2, price_y_pos + 55), percent_text, font_percent, percent_color)
    
    # Wykres
    chart_image = create_price_chart(start_pln, end_pln, palette['chart'])
    chart_x = (BOARD_WIDTH - chart_image.width) // 2
    board.paste(chart_image, (chart_x, BOARD_HEIGHT - chart_image.height - 30), chart_image)

    return board

def generate_final_slide(data, palette, slide_num, total_slides):
    board = create_blurred_background(data.get('tlo'))
    draw = ImageDraw.Draw(board, 'RGBA')
    draw_common_elements(draw, slide_num, total_slides, palette)
    
    # Logotypy
    logo_ptcg = Image.open(LOGO_PTCG_FILE).convert("RGBA")
    logo_shop = Image.open(LOGO_SHOP_FILE).convert("RGBA")
    logo_ptcg.thumbnail((200, 200), Image.Resampling.LANCZOS)
    logo_shop.thumbnail((400, 400), Image.Resampling.LANCZOS)

    shop_x = (BOARD_WIDTH - logo_shop.width) // 2
    shop_y = (BOARD_HEIGHT - logo_shop.height) // 2 - 100
    board.paste(logo_shop, (shop_x, shop_y), logo_shop)
    
    ptcg_x = (BOARD_WIDTH - logo_ptcg.width) // 2
    ptcg_y = shop_y + logo_shop.height + 20
    board.paste(logo_ptcg, (ptcg_x, ptcg_y), logo_ptcg)

    # Źródło
    font_source = ImageFont.truetype(FONT_REGULAR_PATH, 32)
    source_text = f"Źródło: {data.get('źródło', 'Nieznane')}" # Use .get() for safety
    source_bbox = draw.textbbox((0,0), source_text, font_source)
    draw_text_with_shadow(draw, ((BOARD_WIDTH - (source_bbox[2]-source_bbox[0]))/2, ptcg_y + logo_ptcg.height + 20), source_text, font_source, '#FFFFFF')
    
    return board

# --- GŁÓWNA PĘTLA WYKONAWCZA ---
if __name__ == "__main__":
    print("🚀 Rozpoczynam generowanie serii slajdów...")

    # Create fonts directory if it doesn't exist (assuming fonts are provided)
    os.makedirs('fonts', exist_ok=True)
    # Placeholder for font files if they don't exist
    if not os.path.exists(FONT_BOLD_PATH):
        print(f"Brak pliku czcionki: {FONT_BOLD_PATH}. Tworzę domyślny...")
        # A simple way to create a dummy font file if it's missing for testing
        # In a real scenario, you'd want to ensure actual font files are present
        try:
            ImageFont.truetype("arial.ttf", 10).save(FONT_BOLD_PATH) # This won't work directly
        except Exception:
            print("Nie można utworzyć domyślnej czcionki. Upewnij się, że 'arial.ttf' jest dostępne lub Poppins-Bold.ttf istnieje.")
            # Fallback for systems without 'arial.ttf' or if save fails
            # For robust solution, consider a more universal default or instruct user to provide fonts
            pass # Continue and hope the PIL default font will be used or fail gracefully
    if not os.path.exists(FONT_REGULAR_PATH):
        print(f"Brak pliku czcionki: {FONT_REGULAR_PATH}. Tworzę domyślny...")
        try:
            ImageFont.truetype("arial.ttf", 10).save(FONT_REGULAR_PATH)
        except Exception:
            print("Nie można utworzyć domyślnej czcionki. Upewnij się, że 'arial.ttf' jest dostępne lub Poppins-Regular.ttf istnieje.")
            pass


    for f in [CSV_FILE, LOGO_PTCG_FILE, LOGO_SHOP_FILE]:
        if not os.path.exists(f):
            print(f"❌ Błąd: Brak pliku: {f}. Upewnij się, że pliki loga i CSV są w odpowiednich miejscach.")
            exit()
    
    # Check font paths separately, as we might attempt to create a dummy one
    if not os.path.exists(FONT_BOLD_PATH):
        print(f"❌ Błąd: Plik czcionki {FONT_BOLD_PATH} nie został znaleziony ani utworzony. Slajdy mogą wyglądać niepoprawnie.")
    if not os.path.exists(FONT_REGULAR_PATH):
        print(f"❌ Błąd: Plik czcionki {FONT_REGULAR_PATH} nie został znaleziony ani utworzony. Slajdy mogą wyglądać niepoprawnie.")

    # Read CSV with a more robust parser and error handling
    try:
        # Use a more flexible separator and skip bad lines if necessary, or specify 'sep' explicitly
        # If the issue is with commas inside fields, try quoting='minimal' or 'QUOTE_NONE'
        df = pd.read_csv(CSV_FILE, sep=',', encoding='utf-8')
    except pd.errors.ParserError as e:
        print(f"❌ Błąd parsowania CSV: {e}")
        print("Upewnij się, że plik CSV jest poprawnie sformatowany. Spróbuj otworzyć go w edytorze tekstu i sprawdzić przecinki oraz cudzysłowy.")
        exit()
    except Exception as e:
        print(f"❌ Nieoczekiwany błąd podczas wczytywania CSV: {e}")
        exit()

    # Ensure all expected columns exist
    required_columns = ['tytul', 'kategoria', 'opis', 'lista kart', 'grafiki', 'ceny', 'tło', 'źródło']
    if not all(col in df.columns for col in required_columns):
        print(f"❌ Błąd: Brakuje wymaganych kolumn w pliku CSV. Oczekiwane: {required_columns}")
        print(f"Dostępne kolumny: {df.columns.tolist()}")
        exit()


    for index, row in df.iterrows():
        topic_index = index + 1
        # Sanitize title for directory name more robustly
        safe_title = re.sub(r'[^\w\s-]', '', row['tytul']).replace(' ', '_')
        if not safe_title: # Fallback if title becomes empty after sanitization
            safe_title = f"untitled_topic_{topic_index}"
        
        topic_dir = os.path.join(OUTPUT_DIR, f"{topic_index}_{safe_title}")
        os.makedirs(topic_dir, exist_ok=True)
        
        print(f"\n📁 Tworzę serię dla: '{row['tytul']}'")

        # Przygotowanie danych
        # Ensure that split() on potentially empty strings doesn't create ['']
        card_names = [name.strip() for name in row['lista kart'].strip().split('\n') if name.strip()]
        card_images = [img.strip() for img in row['grafiki'].strip().split('|') if img.strip()] # Split by | for images
        card_prices = [price.strip() for price in row['ceny'].strip().split(';') if price.strip()] # Split by ; for prices
        
        # Fill missing image URLs with a placeholder if fewer images than cards
        while len(card_images) < len(card_names):
            card_images.append('') # Append empty string for missing images

        # Fill missing price strings with a placeholder if fewer prices than cards
        while len(card_prices) < len(card_names):
            card_prices.append('0 PLN → 0 PLN (0%)') # Append default price string

        if not (len(card_names) == len(card_images) == len(card_prices)):
            print(f"⚠️  Ostrzeżenie: Niezgodna liczba kart ({len(card_names)}), grafik ({len(card_images)}) i cen ({len(card_prices)}) w wierszu {topic_index}. Kontynuuję z dostępnymi danymi, używając pustych lub domyślnych wartości dla brakujących.")
            # Adjust lists to match the longest one, filling with defaults
            max_len = max(len(card_names), len(card_images), len(card_prices))
            card_names.extend(['Brak nazwy'] * (max_len - len(card_names)))
            card_images.extend([''] * (max_len - len(card_images)))
            card_prices.extend(['0 PLN → 0 PLN (0%)'] * (max_len - len(card_prices)))

            # Now, ensure all lists are the same length for zipping
            card_names = card_names[:max_len]
            card_images = card_images[:max_len]
            card_prices = card_prices[:max_len]


        total_slides = 2 + len(card_names) + 1 # Tytuł, opis, N kart, koniec
        current_slide_num = 0
        
        try:
            # Get palette for the current row, default to 'default' if not found
            palette = PALETTES.get(row.get('kategoria', 'default'), PALETTES['default'])

            # 1. Slajd tytułowy
            current_slide_num += 1
            print(f"  > Generuję slajd {current_slide_num}/{total_slides}: Tytułowy")
            slide = generate_title_slide(row, palette, current_slide_num, total_slides)
            slide.save(os.path.join(topic_dir, f"{current_slide_num}_tytul.png"))

            # 2. Slajd z opisem
            current_slide_num += 1
            print(f"  > Generuję slajd {current_slide_num}/{total_slides}: Opis")
            slide = generate_description_slide(row, palette, current_slide_num, total_slides)
            slide.save(os.path.join(topic_dir, f"{current_slide_num}_opis.png"))

            # 3. Slajdy kart
            for i, (name, img_url, price_str) in enumerate(zip(card_names, card_images, card_prices)):
                current_slide_num += 1
                clean_name = re.sub(r'^\d+\.\s*', '', name)
                print(f"  > Generuję slajd {current_slide_num}/{total_slides}: Karta - {clean_name[:30]}...")
                slide = generate_card_slide(name, img_url, price_str, palette, current_slide_num, total_slides)
                safe_card_name = re.sub(r'[^\w-]', '', clean_name.replace(' ', '_'))
                slide.save(os.path.join(topic_dir, f"{current_slide_num}_karta_{safe_card_name[:20]}.png"))
            
            # 4. Slajd końcowy
            current_slide_num += 1
            print(f"  > Generuję slajd {current_slide_num}/{total_slides}: Końcowy")
            slide = generate_final_slide(row, palette, current_slide_num, total_slides)
            slide.save(os.path.join(topic_dir, f"{current_slide_num}_koniec.png"))

        except Exception as e:
            print(f"🔥 Wystąpił błąd podczas generowania serii dla '{row['tytul']}': {e}")
            import traceback
            traceback.print_exc()


    print(f"\n🎉 Zakończono! Wszystkie serie slajdów zostały zapisane w folderze '{OUTPUT_DIR}'.")
