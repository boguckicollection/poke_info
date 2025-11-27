import feedparser
import requests
from bs4 import BeautifulSoup

def get_article_content(url):
    """
    Fetches the content of an article from a given URL.
    This is a basic implementation and might need to be adapted
    for specific site structures.
    """
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.content, 'html.parser')

        # A common pattern is that the main content is in <article> tags,
        # or in a <div> with an id or class like 'content', 'main', 'post-body'.
        # This is a generic attempt and might not work for all sources.
        article_body = soup.find('article') or soup.find('div', class_='content') or soup.find('div', id='content') or soup.find('div', class_='post-body')

        if article_body:
            # Remove script and style tags
            for script_or_style in article_body(['script', 'style']):
                script_or_style.decompose()
            return article_body.get_text(separator='\n', strip=True)
        else:
            # Fallback for sites without clear semantic tags
            return soup.get_text(separator='\n', strip=True)

    except requests.RequestException as e:
        print(f"Error fetching article content from {url}: {e}")
        return None

def scrape_article_images(url):
    """
    Scrapes a given URL for high-quality images.
    """
    from urllib.parse import urljoin
    
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.content, 'html.parser')
        
        images = []
        # Find images within the main article body if possible
        article_body = soup.find('article') or soup.find('div', class_='entry-content') or soup.find('div', class_='post-content')
        
        search_area = article_body if article_body else soup

        for img in search_area.find_all('img'):
            src = img.get('src')
            if not src:
                continue

            # Skip small or tracking pixel images
            if img.get('width') and img.get('width').isdigit() and int(img.get('width')) < 200:
                continue
            if img.get('height') and img.get('height').isdigit() and int(img.get('height')) < 200:
                continue
            if any(bad_str in src for bad_str in ['.gif', 'data:image', 'ad.', '/ads/']):
                continue

            # Make URL absolute
            absolute_url = urljoin(url, src)
            images.append(absolute_url)
            
        # Remove duplicates
        return list(dict.fromkeys(images))

    except requests.RequestException as e:
        print(f"Error fetching article for image scraping from {url}: {e}")
        return []

def fetch_articles_from_rss(feed_urls):
    """
    Fetches articles from a list of RSS feed URLs.
    
    Args:
        feed_urls (list): A list of URLs for RSS feeds.
        
    Returns:
        list: A list of dictionaries, where each dictionary represents an article.
    """
    articles = []
    seen_urls = set()

    for url in feed_urls:
        feed = feedparser.parse(url)
        for entry in feed.entries:
            if entry.link not in seen_urls:
                article = {
                    'title': entry.title,
                    'url': entry.link,
                    'summary': entry.summary if 'summary' in entry else '',
                    'published': entry.get('published_parsed')
                }
                articles.append(article)
                seen_urls.add(entry.link)
    return articles
