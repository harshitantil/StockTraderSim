import os
import json
import logging
from datetime import datetime, timedelta
import time
import yfinance as yf
import pandas as pd
from functools import lru_cache

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Cache to store stock data and prevent excessive API calls
price_cache = {}
chart_cache = {}
search_cache = {}

# Cache expiration in seconds
PRICE_CACHE_EXPIRY = 300  # 5 minutes for stock prices
CHART_CACHE_EXPIRY = 1800  # 30 minutes for chart data
SEARCH_CACHE_EXPIRY = 3600  # 1 hour for search results

# Rate limiting
RATE_LIMIT_WINDOW = 60  # 1 minute window
MAX_REQUESTS_PER_WINDOW = 30  # Maximum requests per minute
request_timestamps = []

def check_rate_limit():
    """Check if we're within rate limits"""
    current_time = time.time()
    # Remove timestamps older than the window
    global request_timestamps
    request_timestamps = [ts for ts in request_timestamps if current_time - ts < RATE_LIMIT_WINDOW]
    
    if len(request_timestamps) >= MAX_REQUESTS_PER_WINDOW:
        return False
    request_timestamps.append(current_time)
    return True

def get_stock_price(symbol):
    """Get the current price of a stock using Yahoo Finance"""
    current_time = time.time()
    
    # Check if we have a cached value that's still valid
    if symbol in price_cache and current_time - price_cache[symbol]['timestamp'] < PRICE_CACHE_EXPIRY:
        logger.debug(f"Using cached price for {symbol}")
        return price_cache[symbol]['data']
    
    logger.info(f"Fetching live price for {symbol} using yfinance")
    
    try:
        if not check_rate_limit():
            logger.warning("Rate limit reached, using cached data if available")
            if symbol in price_cache:
                return price_cache[symbol]['data']
            return None

        # Get stock info using yfinance
        stock = yf.Ticker(symbol)
        info = stock.info
        
        # Handle potential missing keys
        if not info or 'regularMarketPrice' not in info:
            logger.error(f"Failed to fetch price info for {symbol}")
            # Return cached data if available
            if symbol in price_cache:
                logger.warning(f"Using expired cache for {symbol}")
                return price_cache[symbol]['data']
            return None
        
        # Calculate change and change percent
        previous_close = info.get('previousClose', info.get('regularMarketPreviousClose', 0))
        current_price = info.get('regularMarketPrice', 0)
        change = current_price - previous_close
        change_percent = (change / previous_close * 100) if previous_close > 0 else 0
        
        price_data = {
            'symbol': symbol,
            'price': current_price,
            'change': change,
            'change_percent': change_percent,
            'volume': info.get('regularMarketVolume', 0),
            'last_trading_day': datetime.now().strftime('%Y-%m-%d')
        }
        
        # Cache the results
        price_cache[symbol] = {
            'data': price_data,
            'timestamp': current_time
        }
        
        return price_data
        
    except Exception as e:
        logger.error(f"Error fetching price for {symbol}: {str(e)}")
        if symbol in price_cache:
            logger.warning(f"Using expired cache for {symbol} due to error")
            return price_cache[symbol]['data']
        return None

def get_stock_chart_data(symbol, time_range='1h'):
    """Get stock chart data for the specified time range using Yahoo Finance"""
    current_time = time.time()
    cache_key = f"{symbol}_{time_range}"
    
    # Check if we have cached data that's still valid
    if cache_key in chart_cache and current_time - chart_cache[cache_key]['timestamp'] < CHART_CACHE_EXPIRY:
        logger.debug(f"Using cached chart data for {symbol} ({time_range})")
        return chart_cache[cache_key]['data']
    
    logger.info(f"Fetching chart data for {symbol} ({time_range}) using yfinance")
    
    # Determine the appropriate period and interval based on time_range
    period = "1d"
    interval = "1m"
    
    if time_range == '5m':
        period = "1d"
        interval = "5m"
    elif time_range == '1h':
        period = "1d"
        interval = "60m"
    elif time_range == 'all':
        period = "1y"
        interval = "1d"
    
    try:
        # Get historical data from yfinance
        stock = yf.Ticker(symbol)
        hist = stock.history(period=period, interval=interval)
        
        if hist.empty:
            logger.error(f"No historical data found for {symbol}")
            # If there was an error but we have cached data, return it even if expired
            if cache_key in chart_cache:
                logger.warning(f"Using expired cache for chart data ({symbol})")
                return chart_cache[cache_key]['data']
            return []
        
        # Convert to our expected format
        chart_data = []
        for index, row in hist.iterrows():
            chart_data.append({
                'date': index.strftime('%Y-%m-%d %H:%M:%S'),
                'open': float(row['Open']),
                'high': float(row['High']),
                'low': float(row['Low']),
                'close': float(row['Close']),
                'volume': int(row['Volume'])
            })
        
        # Cache the results
        chart_cache[cache_key] = {
            'data': chart_data,
            'timestamp': current_time
        }
        
        return chart_data
            
    except Exception as e:
        logger.error(f"Error fetching chart data for {symbol}: {str(e)}")
        # If there was an error but we have cached data, return it even if expired
        if cache_key in chart_cache:
            logger.warning(f"Using expired cache for chart data ({symbol}) due to error")
            return chart_cache[cache_key]['data']
        return []

def search_stocks(query):
    """Search for stocks by symbol or keywords using yfinance"""
    current_time = time.time()
    query = query.strip().upper()
    
    # Check if we have cached results for this query
    if query in search_cache and current_time - search_cache[query]['timestamp'] < SEARCH_CACHE_EXPIRY:
        logger.debug(f"Using cached search results for {query}")
        return search_cache[query]['data']
    
    logger.info(f"Searching stocks with query: {query}")
    
    try:
        if not check_rate_limit():
            logger.warning("Rate limit reached, using cached data if available")
            if query in search_cache:
                return search_cache[query]['data']
            return []

        # For simple queries, we can search through our common stocks list
        filtered_stocks = []
        
        # First try an exact match
        try:
            exact_match = yf.Ticker(query)
            if hasattr(exact_match, 'info') and exact_match.info and 'shortName' in exact_match.info:
                info = exact_match.info
                filtered_stocks.append({
                    'symbol': query,
                    'name': info.get('shortName', info.get('longName', 'Unknown Company')),
                    'type': 'Equity',
                    'region': info.get('country', 'USA'),
                    'currency': info.get('currency', 'USD')
                })
        except Exception as e:
            logger.warning(f"Error fetching exact match for {query}: {str(e)}")
        
        # Then search in common stocks
        for stock in COMMON_STOCKS:
            if query in stock['symbol'] or query.lower() in stock['name'].lower():
                # Add if not already added as exact match
                if not any(fs['symbol'] == stock['symbol'] for fs in filtered_stocks):
                    filtered_stocks.append(stock)
        
        # Cache the results
        search_cache[query] = {
            'data': filtered_stocks,
            'timestamp': current_time
        }
        
        return filtered_stocks
        
    except Exception as e:
        logger.error(f"Error searching stocks: {str(e)}")
        if query in search_cache:
            logger.warning(f"Using expired cache for search query {query} due to error")
            return search_cache[query]['data']
        return []

# Common stock tickers - useful for search functionality
COMMON_STOCKS = [
    {'symbol': 'AAPL', 'name': 'Apple Inc.', 'type': 'Equity', 'region': 'USA', 'currency': 'USD'},
    {'symbol': 'MSFT', 'name': 'Microsoft Corporation', 'type': 'Equity', 'region': 'USA', 'currency': 'USD'},
    {'symbol': 'GOOGL', 'name': 'Alphabet Inc.', 'type': 'Equity', 'region': 'USA', 'currency': 'USD'},
    {'symbol': 'AMZN', 'name': 'Amazon.com Inc.', 'type': 'Equity', 'region': 'USA', 'currency': 'USD'},
    {'symbol': 'META', 'name': 'Meta Platforms Inc.', 'type': 'Equity', 'region': 'USA', 'currency': 'USD'},
    {'symbol': 'TSLA', 'name': 'Tesla Inc.', 'type': 'Equity', 'region': 'USA', 'currency': 'USD'},
    {'symbol': 'NVDA', 'name': 'NVIDIA Corporation', 'type': 'Equity', 'region': 'USA', 'currency': 'USD'},
    {'symbol': 'JPM', 'name': 'JPMorgan Chase & Co.', 'type': 'Equity', 'region': 'USA', 'currency': 'USD'},
    {'symbol': 'V', 'name': 'Visa Inc.', 'type': 'Equity', 'region': 'USA', 'currency': 'USD'},
    {'symbol': 'JNJ', 'name': 'Johnson & Johnson', 'type': 'Equity', 'region': 'USA', 'currency': 'USD'},
    {'symbol': 'WMT', 'name': 'Walmart Inc.', 'type': 'Equity', 'region': 'USA', 'currency': 'USD'},
    {'symbol': 'MA', 'name': 'Mastercard Incorporated', 'type': 'Equity', 'region': 'USA', 'currency': 'USD'},
    {'symbol': 'PG', 'name': 'Procter & Gamble Co.', 'type': 'Equity', 'region': 'USA', 'currency': 'USD'},
    {'symbol': 'DIS', 'name': 'Walt Disney Co.', 'type': 'Equity', 'region': 'USA', 'currency': 'USD'},
    {'symbol': 'NFLX', 'name': 'Netflix Inc.', 'type': 'Equity', 'region': 'USA', 'currency': 'USD'}
]
