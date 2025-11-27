# GEMINI.md

## Project Overview

This project features a sophisticated Python application that automates the creation of social media infographics about Pokémon TCG news. The original script, which relied on a static CSV file, has been completely refactored into a dynamic pipeline.

The new workflow is as follows:
1.  **Scrapes Content**: Reads a list of news source URLs from `sources.txt`.
2.  **Processes with AI**: For each URL, it scrapes the article's text and sends it to an OpenAI model (GPT). The AI summarizes the article, translates it to Polish, and extracts key information, such as mentioned Pokémon cards and their price data, into a structured format.
3.  **Fetches Card Data**: It then takes the names of the extracted cards and uses the `pokemontcg.io` API to find and download high-quality card images.
4.  **Generates Infographics**: Finally, the script uses the AI-generated text and the fetched card images to produce a series of polished PNG infographics, which are saved into the `output` directory.

This dynamic, API-driven approach allows the application to generate timely and relevant content without manual data entry.

## Project Structure

The project is now modular, with responsibilities separated into different files:

-   `main3.py`: The main script that orchestrates the entire pipeline from scraping to image generation.
-   `web_scraper.py`: A module responsible for fetching and parsing article text from URLs.
-   `openai_processor.py`: Handles all interaction with the OpenAI API, including sending prompts and parsing the structured JSON response.
-   `pokemon_api.py`: A module for querying the `pokemontcg.io` API to find card images.
-   `sources.txt`: A simple text file containing the list of URLs to be scraped.
-   `.env.example`: A template for the required `.env` file, which holds the API key.
-   `fonts/`: Contains the `.ttf` font files for rendering text on the images.
-   `output/`: The directory where all generated infographics are saved.

## Building and Running

This project is a Python script and does not have a formal build process. The web scraper now uses Selenium to control a real web browser (Google Chrome), which allows it to bypass anti-scraping measures and correctly render modern websites.

### 1. Prerequisites

-   **Google Chrome:** You must have Google Chrome installed on your system.

### 2. Set Up Environment

First, you must provide your OpenAI API key.

1.  Rename the `.env.example` file to `.env`.
2.  Open the `.env` file and replace `"YOUR_OPENAI_API_KEY_HERE"` with your actual OpenAI API key.

    **Optional: Pokémon TCG API Key**
    To potentially improve reliability and bypass rate limits for fetching card images, you can obtain a free API key from [pokemontcg.io](https://pokemontcg.io/). Add it to your `.env` file like this:
    ```
    POKEMONTCG_API_KEY="YOUR_POKEMONTCG_API_KEY_HERE"
    ```

    *Note: The script can function without the Pokémon TCG API key, but having one can improve performance and reduce errors.*

### 3. Install Dependencies

The script relies on several new Python libraries. It is highly recommended to use a virtual environment. Install the dependencies using pip:

```bash
pip install python-dotenv openai beautifulsoup4 pokemontcgsdk requests pillow matplotlib selenium webdriver-manager
```
The `webdriver-manager` library will automatically download and manage the correct driver for your installed version of Google Chrome.

### 4. Customize Sources (Optional)

You can change the news sources by editing the `sources.txt` file. Add or remove URLs as needed, with one URL per line.

### 5. Run the Script

To generate the infographics, run the `main3.py` script from the project's root directory:

```bash
python main3.py
```

The script will then launch a headless browser, execute the full pipeline (scraping, AI processing, data fetching), and save the results in the `output` folder.

## Development Conventions

-   **Modularity**: The codebase is now split into modules with clear responsibilities, making it easier to maintain and extend.
-   **Configuration**: Sensitive information like API keys is managed via a `.env` file using `python-dotenv`.
-   **API Integration**: The script demonstrates best practices for interacting with external APIs, including handling potential errors and structuring data.
-   **Data Flow**: The data pipeline is unidirectional: URL -> Scraped Text -> AI-Processed Data -> Image Generation. This makes the logic easy to follow.
