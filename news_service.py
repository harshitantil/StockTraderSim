import requests
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Optional

class NewsService:
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = "https://newsapi.org/v2"
        self.logger = logging.getLogger(__name__)

    def get_market_news(self, limit: int = 5) -> List[Dict]:
        """
        Fetch market news from NewsAPI.org
        Returns a list of news articles
        """
        try:
            # Calculate date range (last 7 days)
            end_date = datetime.now()
            start_date = end_date - timedelta(days=7)
            
            # Format dates for API
            from_date = start_date.strftime('%Y-%m-%d')
            to_date = end_date.strftime('%Y-%m-%d')

            # Make API request
            url = f"{self.base_url}/everything"
            params = {
                'q': 'stock market OR trading OR finance',
                'from': from_date,
                'to': to_date,
                'language': 'en',
                'sortBy': 'publishedAt',
                'apiKey': self.api_key
            }

            response = requests.get(url, params=params)
            response.raise_for_status()
            
            data = response.json()
            
            if data['status'] != 'ok':
                self.logger.error(f"NewsAPI error: {data.get('message', 'Unknown error')}")
                return []

            # Process and format articles
            articles = []
            for article in data.get('articles', [])[:limit]:
                articles.append({
                    'title': article['title'],
                    'description': article['description'],
                    'url': article['url'],
                    'source': article['source']['name'],
                    'published_at': article['publishedAt'],
                    'image_url': article.get('urlToImage')
                })

            return articles

        except requests.exceptions.RequestException as e:
            self.logger.error(f"Error fetching news: {str(e)}")
            return []
        except Exception as e:
            self.logger.error(f"Unexpected error in get_market_news: {str(e)}")
            return []

    def get_stock_news(self, symbol: str, limit: int = 5) -> List[Dict]:
        """
        Fetch news specific to a stock symbol
        Returns a list of news articles
        """
        try:
            # Calculate date range (last 7 days)
            end_date = datetime.now()
            start_date = end_date - timedelta(days=7)
            
            # Format dates for API
            from_date = start_date.strftime('%Y-%m-%d')
            to_date = end_date.strftime('%Y-%m-%d')

            # Make API request
            url = f"{self.base_url}/everything"
            params = {
                'q': f'"{symbol}" stock',
                'from': from_date,
                'to': to_date,
                'language': 'en',
                'sortBy': 'publishedAt',
                'apiKey': self.api_key
            }

            response = requests.get(url, params=params)
            response.raise_for_status()
            
            data = response.json()
            
            if data['status'] != 'ok':
                self.logger.error(f"NewsAPI error: {data.get('message', 'Unknown error')}")
                return []

            # Process and format articles
            articles = []
            for article in data.get('articles', [])[:limit]:
                articles.append({
                    'title': article['title'],
                    'description': article['description'],
                    'url': article['url'],
                    'source': article['source']['name'],
                    'published_at': article['publishedAt'],
                    'image_url': article.get('urlToImage')
                })

            return articles

        except requests.exceptions.RequestException as e:
            self.logger.error(f"Error fetching stock news: {str(e)}")
            return []
        except Exception as e:
            self.logger.error(f"Unexpected error in get_stock_news: {str(e)}")
            return [] 