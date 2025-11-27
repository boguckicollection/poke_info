from app import app, db
from flask import render_template, jsonify, request, redirect, url_for, flash
from app.models import Article
from app.rss_reader import fetch_articles_from_rss, get_article_content, scrape_article_images
from app.image_generator import create_infographic
import os

@app.route('/')
@app.route('/index')
def index():
    articles = Article.query.order_by(Article.created_at.desc()).all()
    return render_template('index.html', articles=articles)

@app.route('/fetch_articles', methods=['POST'])
def fetch_articles_route():
    try:
        # Get the absolute path to sources.txt
        basedir = os.path.abspath(os.path.dirname(__name__))
        sources_path = os.path.join(basedir, 'sources.txt')
        
        with open(sources_path, 'r') as f:
            feed_urls = [line.strip() for line in f if line.strip()]
            
        articles_from_rss = fetch_articles_from_rss(feed_urls)
        
        new_articles_count = 0
        for article_data in articles_from_rss:
            if not Article.query.filter_by(url=article_data['url']).first():
                new_article = Article(
                    title=article_data['title'],
                    url=article_data['url'],
                    summary=article_data.get('summary', '')
                )
                db.session.add(new_article)
                new_articles_count += 1
        
        db.session.commit()
        
        return jsonify({'message': f'Pobrano {new_articles_count} nowych artykułów.'}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@app.route('/edit_article/<int:article_id>', methods=['GET', 'POST'])
def edit_article(article_id):
    article = Article.query.get_or_404(article_id)
    if request.method == 'POST':
        article.title = request.form['title']
        article.summary = request.form['summary']
        article.image_keywords = request.form['image_keywords']
        article.selected_images = request.form['selected_images']
        article.status = request.form['status']
        db.session.commit()
        flash('Artykuł zaktualizowany!', 'success')
        return redirect(url_for('index'))
    return render_template('edit_article.html', article=article)

@app.route('/fetch_content/<int:article_id>', methods=['POST'])
def fetch_content_route(article_id):
    article = Article.query.get_or_404(article_id)
    if not article.content:
        content = get_article_content(article.url)
        if content:
            article.content = content
            db.session.commit()
            return jsonify({'content': content})
        return jsonify({'error': 'Nie udało się pobrać treści.'}), 500
    return jsonify({'content': article.content})

@app.route('/fetch_images/<int:article_id>', methods=['POST'])
def fetch_images_route(article_id):
    article = Article.query.get_or_404(article_id)
    images = scrape_article_images(article.url)
    if images:
        return jsonify({'images': images})
    return jsonify({'error': 'Nie udało się pobrać obrazków.'}), 500


@app.route('/settings', methods=['GET', 'POST'])
def settings():
    basedir = os.path.abspath(os.path.dirname(__name__))
    sources_path = os.path.join(basedir, 'sources.txt')

    if request.method == 'POST':
        content = request.form['sources']
        with open(sources_path, 'w') as f:
            f.write(content)
        flash('Źródła RSS zostały zaktualizowane.', 'success')
        return redirect(url_for('settings'))

    try:
        with open(sources_path, 'r') as f:
            sources_content = f.read()
    except FileNotFoundError:
        sources_content = ''

    return render_template('settings.html', sources_content=sources_content)

@app.route('/generate/<int:article_id>', methods=['POST'])
def generate_route(article_id):
    article = Article.query.get_or_404(article_id)
    if article.status != 'ready':
        flash('Tylko artykuły o statusie "Gotowy do generowania" mogą być przetwarzane.', 'warning')
        return redirect(url_for('index'))

    try:
        output_dir = create_infographic(article)
        if output_dir:
            article.status = 'generated'
            db.session.commit()
            flash(f'Infografiki dla "{article.title}" zostały wygenerowane! Zapisano w: {output_dir}', 'success')
        else:
            flash(f'Wystąpił błąd podczas generowania infografik dla "{article.title}".', 'error')
    except Exception as e:
        flash(f'Krytyczny błąd podczas generowania: {e}', 'error')

    return redirect(url_for('index'))




