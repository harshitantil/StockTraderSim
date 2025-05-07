class Config:
    SECRET_KEY = 'your-secret-key-here'
    SQLALCHEMY_DATABASE_URI = 'sqlite:///stocktrader.db'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    NEWS_API_KEY = 'c68553e98ba04529a9fd575a0b1784fb'  # NewsAPI.org API key 