from pokemontcgsdk import Card
from pokemontcgsdk import RestClient
import os

# It's good practice to set an API key, though this library can work without one for some features.
# The user can get a free key from https://pokemontcg.io/
# For now, we'll proceed without a key, but include the option.
API_KEY = os.getenv("POKEMONTCG_API_KEY") 
if API_KEY:
    RestClient.configure(API_KEY)

def find_card_image(card_name: str) -> str:
    """
    Finds a Pokémon card by name and returns its high-resolution image URL.
    """
    try:
        # The API query is picky. We try to clean the name.
        # Sometimes names have "ex" or "V" at the end.
        # The search works best with just the Pokémon name.
        clean_name = card_name.split(' ')[0]

        cards = Card.where(q=f'name:"{clean_name}"')
        
        # Find the best match from the results
        if not cards:
            print(f"⚠️ No card found for name: {card_name}")
            return "PLACEHOLDER"

        # We need a good way to select the best card.
        # Let's try to find an exact match or a close one.
        best_match = None
        for card in cards:
            if card.name.lower() == card_name.lower():
                best_match = card
                break
        
        # If no exact match, take the first one that is likely a Pokémon
        if not best_match:
            for card in cards:
                if card.supertype == "Pokémon":
                    best_match = card
                    break
        
        # If still no good match, take the first result
        if not best_match:
            best_match = cards[0]

        if best_match and best_match.images and best_match.images.large:
            print(f"✅ Found image for {card_name}: {best_match.images.large}")
            return best_match.images.large
        else:
            print(f"⚠️ No image found for card: {card_name}")
            return "PLACEHOLDER"

    except Exception as e:
        # The PokemonTcgException can sometimes contain bytes, causing a TypeError on print.
        # We print a generic but more stable error message.
        print(f"""
🔥 An error occurred with the Pokémon TCG API. 
   The service may be temporarily unavailable or the card name '{card_name}' could not be processed.
""")
        print(f"  Underlying error type: {type(e)}")
        return "PLACEHOLDER"

if __name__ == '__main__':
    print("Testing Pokémon TCG API wrapper...")

    # Example 1: A common card
    image_url = find_card_image("Charizard ex")
    assert "images.pokemontcg.io" in image_url
    print(f"Found Charizard ex image: {image_url}")

    # Example 2: Another card
    image_url_2 = find_card_image("Pikachu")
    assert "images.pokemontcg.io" in image_url_2
    print(f"Found Pikachu image: {image_url_2}")

    # Example 3: A card that might not exist
    image_url_3 = find_card_image("Imaginary Card")
    assert image_url_3 == "PLACEHOLDER"
    print("Correctly handled non-existent card.")
