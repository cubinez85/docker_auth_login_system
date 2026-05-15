from app import db
from datetime import datetime

class TokenBlacklist(db.Model):
    __tablename__ = 'token_blacklist'

    id = db.Column(db.Integer, primary_key=True)
    token = db.Column(db.String(500), unique=True, nullable=False, index=True)
    blacklisted_on = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    expires_at = db.Column(db.DateTime, nullable=False)

    @classmethod
    def is_blacklisted(cls, token):
        return cls.query.filter_by(token=token).first() is not None

    def __repr__(self):
        return f'<TokenBlacklist {self.token[:20]}...>'
