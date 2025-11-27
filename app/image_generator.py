import os
import re
import textwrap
from io import BytesIO
from urllib.parse import urlparse
from dotenv import load_dotenv

import matplotlib
import matplotlib.pyplot as plt
import requests
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageOps, ImageColor

# --- Custom Modules ---
# Note: These are now relative imports if this file is inside the 'app' package
from . import pokemon_api

# --- Initial Setup ---
load_dotenv()
matplotlib.use('Agg') # Use non-interactive backend

# --- CONFIGURATION ---
# These paths might need to be adjusted to be absolute from the app's root
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
LOGO_PTCG_FILE = os.path.join(BASE_DIR, 'PTCG.png')
LOGO_SHOP_FILE = os.path.join(BASE_DIR, 'banner22.png')
OUTPUT_DIR = os.path.join(BASE_DIR, 'output')

# Font paths
FONT_BOLD_PATH = os.path.join(BASE_DIR, 'fonts', 'Poppins-Bold.ttf')
FONT_REGULAR_PATH = os.path.join(BASE_DIR, 'fonts', 'Poppins-Regular.ttf')


# Board dimensions
BOARD_WIDTH, BOARD_HEIGHT = 1080, 1080

# Color palettes
PALETTES = {
    'top3 tygodnia': {'frame': '#F4A261', 'title_bg': '#264653', 'title_text': '#FFFFFF', 'chart': '#E76F51'},
    'inwestycje': {'frame': '#2A9D8F', 'title_bg': '#264653', 'title_text': '#FFFFFF', 'chart': '#E9C46A'},
    'default': {'frame': '#E76F51', 'title_bg': '#264653', 'title_text': '#FFFFFF', 'chart': '#F4A261'}
}

# --- HELPER FUNCTIONS (Most of these can remain the same) ---

def parse_price_data(price_string):
    """Parses a price string to extract PLN and percentage values."""
    if not price_string or "→" not in price_string:
        return 0, 0, ""
        
    try:
        # Look for numbers, allowing for different currency symbols and formats
        numbers = re.findall(r"[\d,.]+", price_string)
        numbers = [float(n.replace(',', '')) for n in numbers]
        
        start_pln, end_pln = 0, 0
        if len(numbers) >= 2:
            start_pln, end_pln = numbers[0], numbers[1]
        
        percentage_match = re.search(r"(\+[\d.]+%)", price_string)
        percentage = percentage_match.group(1) if percentage_match else ""
        
        return start_pln, end_pln, percentage
    except (AttributeError, ValueError, IndexError) as e:
        print(f"Could not parse price string: '{price_string}'. Error: {e}")
        return 0, 0, "N/A"

def create_price_chart(start_price, end_price, color):
    """Creates a price growth chart image."""
    if start_price == 0 or end_price == 0 or start_price >= end_price:
        return Image.new('RGBA', (250, 120), (0,0,0,0)) # Return empty if no growth

    fig, ax = plt.subplots(figsize=(2.5, 1.2), dpi=150)
    x = [0, 1]
    y = [start_price, end_price]
    
    ax.plot(x, y, color=color, linewidth=5, solid_capstyle='round')
    
    # Gradient fill
    line = ax.lines[0]
    x_data, y_data = line.get_data()
    ax.fill_between(x_data, y_data, color=color, alpha=0.2)
    
    # Styled markers
    ax.plot(x[0], y[0], 'o', color=color, markersize=10, markeredgecolor='white', markeredgewidth=2)
    ax.plot(x[1], y[1], 'o', color=color, markersize=10, markeredgecolor='white', markeredgewidth=2)
    
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.spines['left'].set_visible(False)
    ax.spines['bottom'].set_visible(False)
    ax.tick_params(axis='both', which='both', bottom=False, top=False, left=False, right=False, labelbottom=False, labelleft=False)
    ax.set_facecolor('none')
    fig.patch.set_alpha(0.0)

    # Margins
    y_padding = (max(y) - min(y)) * 0.1
    ax.set_ylim(min(y) - y_padding, max(y) + y_padding)
    ax.set_xlim(-0.1, 1.1)

    buf = BytesIO()
    fig.savefig(buf, format='png', transparent=True, bbox_inches='tight', pad_inches=0.1)
    buf.seek(0)
    plt.close(fig)
    return Image.open(buf)

def download_image(url):
    """
    Downloads an image from a URL or generates a placeholder if the URL is invalid
    or a placeholder is requested.
    """
    if url == "PLACEHOLDER":
        print("    > Generating placeholder image.")
        img = Image.new('RGB', (540, 754), color = '#DDDDDD')
        d = ImageDraw.Draw(img)
        try:
            font = ImageFont.truetype(FONT_REGULAR_PATH, 40)
        except IOError:
            font = ImageFont.load_default()
        d.text((150, 350), "Image Not Found", fill=(0,0,0), font=font)
        return img.convert("RGBA")

    if not url or not url.startswith('http'):
        print(f"    > Invalid image URL: {url}. Using placeholder.")
        return download_image("PLACEHOLDER")
        
    try:
        response = requests.get(url, timeout=15)
        response.raise_for_status()
        return Image.open(BytesIO(response.content)).convert("RGBA")
    except requests.exceptions.RequestException as e:
        print(f"    > Failed to download image from {url}. Error: {e}. Using placeholder.")
        return download_image("PLACEHOLDER")

def create_default_background(color1='#264653', color2='#2A9D8F'):
    """Generates a default gradient background."""
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
    """Creates a blurred background from a given image URL or a default one."""
    if not isinstance(image_url, str) or not image_url.startswith('http'):
        return create_default_background()

    bg_image = download_image(image_url)
    # Check if the downloaded image is the placeholder
    if bg_image.size == (200, 280) and bg_image.getpixel((0,0)) == (221, 221, 221, 255):
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
    """Draws text with a shadow."""
    x, y = position
    draw.text((x+2, y+2), text, font=font, fill=shadow_color)
    draw.text((x, y), text, font=font, fill=fill)

def draw_common_elements(draw, slide_num, total_slides, palette):
    """Draws the frame and slide numbering."""
    frame_width = 20
    draw.rectangle([(0, 0), (BOARD_WIDTH, BOARD_HEIGHT)], outline=palette['frame'], width=frame_width)
    
    font_page_num = ImageFont.truetype(FONT_BOLD_PATH, 32)
    page_text = f"{slide_num} / {total_slides}"
    # Using textbbox to get width for right alignment
    page_bbox = draw.textbbox((0, 0), page_text, font=font_page_num)
    page_width = page_bbox[2] - page_bbox[0]
    draw_text_with_shadow(draw, (BOARD_WIDTH - page_width - 40, 30), page_text, font_page_num, '#FFFFFF')

# --- SLIDE GENERATION FUNCTIONS (These can remain the same) ---

def generate_title_slide(data, palette, slide_num, total_slides):
    board = create_blurred_background(data['tlo'])
    draw = ImageDraw.Draw(board, 'RGBA')
    draw_common_elements(draw, slide_num, total_slides, palette)
    
    font_title = ImageFont.truetype(FONT_BOLD_PATH, 95)
    title_text = data['tytul']
    
    lines = textwrap.wrap(title_text, width=20)
    # Calculate total height of the wrapped text block for vertical centering
    total_text_height = sum([draw.textbbox((0,0), line, font=font_title)[3] for line in lines])
    y_start = (BOARD_HEIGHT - total_text_height - (len(lines)-1)*15) / 2

    for i, line in enumerate(lines):
        line_bbox = draw.textbbox((0,0), line, font=font_title)
        line_width = line_bbox[2] - line_bbox[0]
        x_pos = (BOARD_WIDTH - line_width) / 2
        y_pos = y_start + i * 110 # Adjust line spacing
        draw_text_with_shadow(draw, (x_pos, y_pos), line, font_title, '#FFFFFF')
        
    return board

def generate_description_slide(data, palette, slide_num, total_slides):
    board = create_blurred_background(data['tlo'])
    draw = ImageDraw.Draw(board, 'RGBA')
    draw_common_elements(draw, slide_num, total_slides, palette)
    
    font_desc = ImageFont.truetype(FONT_REGULAR_PATH, 50)
    desc_text = data['opis']
    
    lines = textwrap.wrap(desc_text, width=35)
    total_text_height = sum([draw.textbbox((0,0), line, font_desc)[3] for line in lines])
    y_start = (BOARD_HEIGHT - total_text_height - (len(lines)-1)*15) / 2
    
    for i, line in enumerate(lines):
        line_bbox = draw.textbbox((0,0), line, font_desc)
        line_width = line_bbox[2] - line_bbox[0]
        x_pos = (BOARD_WIDTH - line_width) / 2
        y_pos = y_start + i * 65
        draw_text_with_shadow(draw, (x_pos, y_pos), line, font_desc, '#FFFFFF')
        
    return board
    
def generate_card_slide(card_name, card_image_url, card_price_str, palette, slide_num, total_slides):
    board = create_blurred_background(card_image_url)
    draw = ImageDraw.Draw(board, 'RGBA')
    draw_common_elements(draw, slide_num, total_slides, palette)
    
    # Card
    card_image = download_image(card_image_url)
    card_width, card_height = 540, 754
    card_image.thumbnail((card_width, card_height), Image.Resampling.LANCZOS)
    card_x = (BOARD_WIDTH - card_image.width) // 2
    card_y = 80
    board.paste(card_image, (card_x, card_y), card_image)
    
    # Card name
    font_card_name = ImageFont.truetype(FONT_BOLD_PATH, 42)
    clean_name = re.sub(r'^\d+\.\s*', '', card_name)
    wrapped_name = textwrap.wrap(clean_name, width=25)
    name_y_start = card_y + card_image.height + 25
    
    for i, line in enumerate(wrapped_name):
        name_bbox = draw.textbbox((0,0), line, font_card_name)
        draw_text_with_shadow(draw, ((BOARD_WIDTH - (name_bbox[2] - name_bbox[0]))/2, name_y_start + i * 45), line, font_card_name, '#FFFFFF')

    # Price and chart
    start_pln, end_pln, percentage = parse_price_data(card_price_str)
    
    # Only show price if data is available
    if start_pln > 0 or end_pln > 0:
        price_text = f"{start_pln:,.2f} → {end_pln:,.2f} PLN".replace(',', ' ')
        percent_text = f"{percentage}"
        
        font_price = ImageFont.truetype(FONT_REGULAR_PATH, 38)
        font_percent = ImageFont.truetype(FONT_BOLD_PATH, 48)
        
        price_y_pos = name_y_start + len(wrapped_name) * 45
        
        price_bbox = draw.textbbox((0,0), price_text, font_price)
        draw_text_with_shadow(draw, ((BOARD_WIDTH - (price_bbox[2] - price_bbox[0]))/2, price_y_pos), price_text, font_price, '#FFFFFF')

        if percentage:
            percent_bbox = draw.textbbox((0,0), percent_text, font_percent)
            draw_text_with_shadow(draw, ((BOARD_WIDTH - (percent_bbox[2] - percent_bbox[0]))/2, price_y_pos + 55), percent_text, font_percent, '#4CAF50')
    
        # Chart
        chart_image = create_price_chart(start_pln, end_pln, palette['chart'])
        chart_x = (BOARD_WIDTH - chart_image.width) // 2
        board.paste(chart_image, (chart_x, BOARD_HEIGHT - chart_image.height - 30), chart_image)

    return board

def generate_final_slide(data, palette, slide_num, total_slides):
    board = create_blurred_background(data['tlo'])
    draw = ImageDraw.Draw(board, 'RGBA')
    draw_common_elements(draw, slide_num, total_slides, palette)
    
    # Logos
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

    # Source
    font_source = ImageFont.truetype(FONT_REGULAR_PATH, 32)
    source_text = f"Źródło: {data['źródło']}"
    source_bbox = draw.textbbox((0,0), source_text, font_source)
    draw_text_with_shadow(draw, ((BOARD_WIDTH - (source_bbox[2]-source_bbox[0]))/2, ptcg_y + logo_ptcg.height + 20), source_text, font_source, '#FFFFFF')
    
    return board

# --- MAIN INFOGRAPHIC CREATION FUNCTION ---

def create_infographic(article):
    """
    Generates a series of infographic slides for a given article.
    
    Args:
        article (Article): An Article object from the database.
        
    Returns:
        str: The path to the directory where the images were saved.
    """
    print(f"🔥 Generating infographics for article: '{article.title}'")

    # 1. Prepare data
    card_names = [name.strip() for name in (article.image_keywords or '').split(',') if name.strip()]
    
    card_images = []
    if card_names:
        print(f"Fetching {len(card_names)} card images...")
        card_images = [pokemon_api.find_card_image(name) for name in card_names]
    
    # Prices are not handled yet.
    card_prices = [""] * len(card_names)
    
    # Use the first selected image for the background, or a card image, or the article URL as a fallback.
    background_image_options = [url.strip() for url in (article.selected_images or '').split(',') if url.strip()]
    
    first_background_image = next(iter(background_image_options), None)
    if not first_background_image:
        # Fallback to the first valid card image if no background is selected
        first_background_image = next((img for img in card_images if img != "PLACEHOLDER"), article.url)

    data = {
        "tytul": article.title,
        "opis": article.summary,
        "kategoria": "default", # This could be a field in the Article model
        "źródło": urlparse(article.url).netloc,
        "tlo": first_background_image,
    }

    # 2. Set up output directory
    safe_title = re.sub(r'[^\w-]', '', article.title.replace(' ', '_'))
    topic_dir = os.path.join(OUTPUT_DIR, f"article_{article.id}_{safe_title[:50]}")
    os.makedirs(topic_dir, exist_ok=True)

    # 3. Generate Slides
    # Title, desc, N cards (if any), end
    total_slides = 2 + len(card_names) + 1 if card_names else 2 + 1 
    current_slide_num = 0
    palette = PALETTES.get(data.get('kategoria', 'default'), PALETTES['default'])

    try:
        # Title Slide
        current_slide_num += 1
        print(f"  > Generating slide {current_slide_num}/{total_slides}: Title")
        slide = generate_title_slide(data, palette, current_slide_num, total_slides)
        slide.save(os.path.join(topic_dir, f"{current_slide_num}_title.png"))

        # Description Slide
        current_slide_num += 1
        print(f"  > Generating slide {current_slide_num}/{total_slides}: Description")
        slide = generate_description_slide(data, palette, current_slide_num, total_slides)
        slide.save(os.path.join(topic_dir, f"{current_slide_num}_description.png"))

        # Card Slides (only if keywords were provided)
        if card_names:
            for i, (name, img_url, price_str) in enumerate(zip(card_names, card_images, card_prices)):
                current_slide_num += 1
                clean_name = re.sub(r'^\d+\.\s*', '', name)
                print(f"  > Generating slide {current_slide_num}/{total_slides}: Card - {clean_name[:30]}...")
                # Use the specific card image for its own blurred background
                slide = generate_card_slide(name, img_url, price_str, palette, current_slide_num, total_slides)
                safe_card_name = re.sub(r'[^\w-]', '', clean_name.replace(' ', '_'))
                slide.save(os.path.join(topic_dir, f"{current_slide_num}_card_{safe_card_name[:20]}.png"))
        
        # Final Slide
        current_slide_num += 1
        print(f"  > Generating slide {current_slide_num}/{total_slides}: Final")
        slide = generate_final_slide(data, palette, current_slide_num, total_slides)
        slide.save(os.path.join(topic_dir, f"{current_slide_num}_final.png"))

    except Exception as e:
        print(f"🔥 An error occurred while generating the series for '{article.title}': {e}")
        import traceback
        traceback.print_exc()
        return None

    print(f"🎉 Finished! Slide series saved in '{topic_dir}'")
    return topic_dir