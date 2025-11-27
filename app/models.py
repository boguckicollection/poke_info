from datetime import datetime
from app import db

class Article(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    url = db.Column(db.String(200), nullable=False, unique=True)
    content = db.Column(db.Text, nullable=True)
    summary = db.Column(db.Text, nullable=True)
    status = db.Column(db.String(20), nullable=False, default='new') # new, ready, generated
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    image_keywords = db.Column(db.String(200), nullable=True)
    selected_images = db.Column(db.Text, nullable=True)

    def __repr__(self):
        return f'<Article {self.title}>'
