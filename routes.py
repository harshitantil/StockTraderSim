from flask import render_template, redirect, url_for, flash, request, jsonify, session
from flask_login import login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
import logging
from sqlalchemy import func, desc

from extensions import db
from models import User, Wallet, Trade, Position, WatchlistGroup, WatchlistStock, Stock
from auth import LoginForm, RegistrationForm, register_user, authenticate_user
from stock_api import get_stock_price, get_stock_chart_data, search_stocks
from news_service import NewsService

def register_routes(app):
    # Initialize NewsService with API key from config
    news_service = NewsService(app.config.get('NEWS_API_KEY', ''))

    # Home route - redirects to login or dashboard based on authentication
    @app.route('/')
    def index():
        if current_user.is_authenticated:
            return redirect(url_for('dashboard'))
        return redirect(url_for('login'))

    # Login route
    @app.route('/login', methods=['GET', 'POST'])
    def login():
        if current_user.is_authenticated:
            return redirect(url_for('dashboard'))
        
        form = LoginForm()
        
        if form.validate_on_submit():
            if authenticate_user(form):
                next_page = request.args.get('next')
                return redirect(next_page or url_for('dashboard'))
            else:
                flash('Login unsuccessful. Please check your username and password.', 'danger')
        
        return render_template('login.html', form=form, title='Login')

    # Registration route
    @app.route('/register', methods=['GET', 'POST'])
    def register():
        if current_user.is_authenticated:
            return redirect(url_for('dashboard'))
        
        form = RegistrationForm()
        
        if form.validate_on_submit():
            if register_user(form):
                flash('Account created successfully! You can now log in.', 'success')
                return redirect(url_for('login'))
        
        return render_template('register.html', form=form, title='Register')

    # Logout route
    @app.route('/logout')
    @login_required
    def logout():
        logout_user()
        flash('You have been logged out.', 'info')
        return redirect(url_for('login'))

    # Dashboard route - main page after login
    @app.route('/dashboard')
    @login_required
    def dashboard():
        # Get user's wallet balance
        wallet = Wallet.query.filter_by(user_id=current_user.id).first()
        
        # Get user's positions
        positions = Position.query.filter_by(user_id=current_user.id).all()
        position_data = []
        
        # Get current prices and calculate P/L for each position
        for position in positions:
            stock_data = get_stock_price(position.stock.symbol)
            if stock_data:
                current_price = stock_data['price']
                market_value = position.quantity * current_price
                cost_basis = position.quantity * position.average_price
                profit_loss = market_value - cost_basis
                profit_loss_pct = (profit_loss / cost_basis) * 100 if cost_basis > 0 else 0
                
                position_data.append({
                    'symbol': position.stock.symbol,
                    'quantity': position.quantity,
                    'avg_price': position.average_price,
                    'current_price': current_price,
                    'market_value': market_value,
                    'profit_loss': profit_loss,
                    'profit_loss_pct': profit_loss_pct
                })
        
        # Get watchlist groups and their stocks
        watchlist_groups = WatchlistGroup.query.filter_by(user_id=current_user.id).all()
        watchlist_data = []
        
        for group in watchlist_groups:
            stocks = []
            for watchlist_stock in group.stocks:
                stock_data = get_stock_price(watchlist_stock.stock.symbol)
                if stock_data:
                    stocks.append({
                        'symbol': watchlist_stock.stock.symbol,
                        'price': stock_data['price'],
                        'change': stock_data['change'],
                        'change_percent': stock_data['change_percent']
                    })
            
            watchlist_data.append({
                'id': group.id,
                'name': group.name,
                'description': group.description,
                'stocks': stocks
            })
        
        return render_template('dashboard.html', 
                            title='Dashboard', 
                            wallet=wallet,
                            positions=position_data,
                            watchlists=watchlist_data)

    # Portfolio route
    @app.route('/portfolio')
    @login_required
    def portfolio():
        try:
            # Get user's positions
            positions = Position.query.filter_by(user_id=current_user.id).all()
            portfolio_data = []
            
            # Get all user's wallets
            wallets = Wallet.query.filter_by(user_id=current_user.id).all()
            total_cash = sum(wallet.balance for wallet in wallets)
            
            # Calculate portfolio value and performance
            total_investment = 0
            total_market_value = 0
            
            for position in positions:
                stock_data = get_stock_price(position.stock.symbol)
                if stock_data:
                    current_price = stock_data.get('price', 0)
                    market_value = position.quantity * current_price
                    cost_basis = position.quantity * position.average_price
                    profit_loss = market_value - cost_basis
                    profit_loss_pct = (profit_loss / cost_basis) * 100 if cost_basis > 0 else 0
                    
                    total_market_value += market_value
                    total_investment += cost_basis
                    
                    portfolio_data.append({
                        'symbol': position.stock.symbol,
                        'quantity': position.quantity,
                        'average_price': position.average_price,
                        'current_price': current_price,
                        'market_value': market_value,
                        'profit_loss': profit_loss,
                        'profit_loss_pct': profit_loss_pct
                    })
            
            # Calculate overall portfolio performance
            total_profit_loss = total_market_value - total_investment
            total_profit_loss_pct = (total_profit_loss / (total_investment or 1)) * 100
            
            # Create summary data
            summary = {
                'cash_balance': total_cash,
                'investments_value': total_investment,
                'total_value': total_market_value + total_cash,
                'profit_loss': total_profit_loss,
                'profit_loss_pct': total_profit_loss_pct
            }
            
            logging.info(f"Portfolio data: {portfolio_data}")  # Debug log
            logging.info(f"Summary data: {summary}")  # Debug log
            
            return render_template('portfolio.html', 
                                 portfolio=portfolio_data,
                                 summary=summary)
        except Exception as e:
            logging.error(f"Error in portfolio route: {str(e)}")
            flash('Error loading portfolio data', 'danger')
            return render_template('portfolio.html', 
                                 portfolio=[],
                                 summary={'cash_balance': 0, 'investments_value': 0, 'total_value': 0, 'profit_loss': 0, 'profit_loss_pct': 0})

    # Trading page route
    @app.route('/trading', methods=['GET'])
    @login_required
    def trading():
        # Get symbol and action from query parameters
        symbol = request.args.get('symbol', '')
        action = request.args.get('action', '')
        
        # Clean up symbol by removing any query parameters
        if '?' in symbol:
            symbol = symbol.split('?')[0]
        
        # Get user's wallet balance
        wallet = Wallet.query.filter_by(user_id=current_user.id).first()
        
        # Get stock data if symbol is provided
        stock_data = None
        position = None
        company_info = None
        stock = None
        
        if symbol:
            stock_data = get_stock_price(symbol)
            # Get or create stock record
            stock = Stock.query.filter_by(symbol=symbol).first()
            if not stock:
                stock = Stock(symbol=symbol, company_name=symbol)
                db.session.add(stock)
                db.session.commit()
            
            # Check if user has an existing position
            position = Position.query.filter_by(user_id=current_user.id, stock_id=stock.id).first()
            
            # Fetch additional company information
            try:
                import yfinance as yf
                ticker = yf.Ticker(symbol)
                info = ticker.info
                print(info.get('longBusinessSummary', ''))  # Company profile/description
                print(info.get('sector', ''))               # Sector
                financials = ticker.financials
                balance_sheet = ticker.balance_sheet
                cashflow = ticker.cashflow
                print(financials)
                print(balance_sheet)
                print(cashflow)
                # Get latest news
                news = ticker.news
                latest_news = news[0] if news else None
                
                company_info = {
                    'description': info.get('longBusinessSummary', 'No description available'),
                    'sector': info.get('sector', 'N/A'),
                    'industry': info.get('industry', 'N/A'),
                    'market_cap': info.get('marketCap', 0),
                    'pe_ratio': info.get('trailingPE', 0),
                    'dividend_yield': info.get('dividendYield', 0),
                    'financials': financials.to_dict() if hasattr(financials, 'to_dict') else {},
                    'balance_sheet': balance_sheet.to_dict() if hasattr(balance_sheet, 'to_dict') else {},
                    'cashflow': cashflow.to_dict() if hasattr(cashflow, 'to_dict') else {},
                    'latest_news': {
                        'title': latest_news.get('title', 'No news available') if latest_news else 'No news available',
                        'link': latest_news.get('link', '#') if latest_news else '#',
                        'publisher': latest_news.get('publisher', 'N/A') if latest_news else 'N/A',
                        'published': latest_news.get('providerPublishTime', 'N/A') if latest_news else 'N/A'
                    } if latest_news else None
                }
            except Exception as e:
                logging.error(f"Error fetching company info for {symbol}: {str(e)}")
                company_info = None
        
        # Check if stock is in any watchlist
        in_watchlist = False
        watchlist_groups = []
        if symbol:
            # Get all watchlists that contain this stock
            watchlist_stocks = WatchlistStock.query.join(WatchlistGroup).filter(
                WatchlistGroup.user_id == current_user.id,
                WatchlistStock.stock_id == stock.id
            ).all()
            
            if watchlist_stocks:
                in_watchlist = True
                watchlist_groups = [ws.watchlist_group for ws in watchlist_stocks]
        
        return render_template('trading.html', 
                            title='Trading', 
                            wallet=wallet,
                            symbol=symbol,
                            action=action,
                            stock_data=stock_data,
                            position=position,
                            in_watchlist=in_watchlist,
                            watchlist_groups=watchlist_groups,
                            company_info=company_info)

    # API route to search stocks
    @app.route('/api/search_stocks')
    @login_required
    def api_search_stocks():
        query = request.args.get('q', '')
        if not query or len(query) < 2:
            return jsonify([])
        
        results = search_stocks(query)
        return jsonify(results)

    # API route to get stock price
    @app.route('/api/stock_price/<symbol>')
    @login_required
    def api_stock_price(symbol):
        stock_data = get_stock_price(symbol)
        if stock_data:
            return jsonify(stock_data)
        return jsonify({'error': 'Stock not found'}), 404

    # API route to get chart data
    @app.route('/api/chart_data/<symbol>')
    @login_required
    def api_chart_data(symbol):
        time_range = request.args.get('range', '1h')
        data = get_stock_chart_data(symbol, time_range)
        return jsonify(data)

    # API route to execute a trade
    @app.route('/api/trade', methods=['POST'])
    @login_required
    def api_trade():
        try:
            data = request.json
            symbol = data.get('symbol')
            quantity = int(data.get('quantity', 0))
            trade_type = data.get('type')  # 'buy' or 'sell'
            wallet_id = int(data.get('wallet_id'))
            
            if not symbol or quantity <= 0 or trade_type not in ['buy', 'sell']:
                return jsonify({'error': 'Invalid trade parameters'}), 400
            
            # Clean up symbol by removing any query parameters
            if '?' in symbol:
                symbol = symbol.split('?')[0]
            
            # Verify wallet exists and belongs to user
            wallet = Wallet.query.filter_by(id=wallet_id, user_id=current_user.id).first()
            if not wallet:
                return jsonify({'error': 'Invalid wallet'}), 400
            
            # Get or create stock record
            stock = Stock.query.filter_by(symbol=symbol).first()
            if not stock:
                stock = Stock(symbol=symbol, company_name=symbol)
                db.session.add(stock)
                db.session.commit()
            
            # Get current stock price
            stock_data = get_stock_price(symbol)
            current_price = None
            
            if stock_data:
                current_price = stock_data['price']
            elif trade_type == 'sell':
                # For sell orders, use the position's average price if live price fetch fails
                position = Position.query.filter_by(user_id=current_user.id, stock_id=stock.id).first()
                if position:
                    current_price = position.average_price
                else:
                    return jsonify({'error': 'Could not determine price for sell order'}), 400
            else:
                return jsonify({'error': 'Could not fetch current stock price'}), 400
            
            total_cost = quantity * current_price
            
            # For buy orders, check if wallet has sufficient funds
            if trade_type == 'buy':
                # Lock the wallet row to prevent race conditions
                wallet = Wallet.query.with_for_update().filter_by(id=wallet_id, user_id=current_user.id).first()
                if not wallet:
                    return jsonify({'error': 'Invalid wallet'}), 400
                
                # Check if wallet has sufficient funds
                if wallet.balance < total_cost:
                    return jsonify({'error': f'Insufficient funds. Required: ${total_cost:.2f}, Available: ${wallet.balance:.2f}'}), 400
                
                # Deduct from wallet
                wallet.balance -= total_cost
                
            # For sell orders, add to wallet
            else:
                # Lock the wallet row to prevent race conditions
                wallet = Wallet.query.with_for_update().filter_by(id=wallet_id, user_id=current_user.id).first()
                if not wallet:
                    return jsonify({'error': 'Invalid wallet'}), 400
                
                # Verify user has enough shares to sell
                position = Position.query.filter_by(user_id=current_user.id, stock_id=stock.id).first()
                if not position or position.quantity < quantity:
                    return jsonify({'error': 'Insufficient shares to sell'}), 400
                
                # Add to wallet
                wallet.balance += total_cost
            
            # Create trade record
            trade = Trade(
                user_id=current_user.id,
                wallet_id=wallet_id,
                stock_id=stock.id,
                quantity=quantity,
                price_per_share=current_price,
                trade_type=trade_type
            )
            db.session.add(trade)
            
            # Update position
            position = Position.query.filter_by(user_id=current_user.id, stock_id=stock.id).first()
            if trade_type == 'buy':
                if position:
                    # Update existing position
                    total_quantity = position.quantity + quantity
                    total_cost = (position.quantity * position.average_price) + (quantity * current_price)
                    position.quantity = total_quantity
                    position.average_price = total_cost / total_quantity
                else:
                    # Create new position
                    position = Position(
                        user_id=current_user.id,
                        stock_id=stock.id,
                        quantity=quantity,
                        average_price=current_price
                    )
                    db.session.add(position)
            else:
                position.quantity -= quantity
                if position.quantity == 0:
                    db.session.delete(position)
            
            db.session.commit()
            
            return jsonify({
                'success': True,
                'trade': {
                    'id': trade.id,
                    'symbol': stock.symbol,
                    'quantity': trade.quantity,
                    'price': trade.price_per_share,
                    'type': trade.trade_type,
                    'wallet_balance': wallet.balance
                }
            })
        except Exception as e:
            db.session.rollback()
            logging.error(f"Trade error: {str(e)}")
            return jsonify({'error': 'An error occurred while processing the trade'}), 500

    # API route to get user's positions
    @app.route('/api/positions')
    @login_required
    def api_positions():
        positions = Position.query.filter_by(user_id=current_user.id).all()
        position_data = []
        
        for position in positions:
            stock_data = get_stock_price(position.stock.symbol)
            if stock_data:
                current_price = stock_data['price']
                market_value = position.quantity * current_price
                cost_basis = position.quantity * position.average_price
                profit_loss = market_value - cost_basis
                profit_loss_pct = (profit_loss / cost_basis) * 100 if cost_basis > 0 else 0
                
                position_data.append({
                    'symbol': position.stock.symbol,
                    'quantity': position.quantity,
                    'avg_price': position.average_price,
                    'current_price': current_price,
                    'market_value': market_value,
                    'profit_loss': profit_loss,
                    'profit_loss_pct': profit_loss_pct
                })
        
        return jsonify(position_data)

    # API route to get all watchlists
    @app.route('/api/watchlists')
    @login_required
    def api_watchlists():
        watchlists = WatchlistGroup.query.filter_by(user_id=current_user.id).all()
        watchlist_data = []
        
        for watchlist in watchlists:
            stocks = []
            for watchlist_stock in watchlist.stocks:
                stock_data = get_stock_price(watchlist_stock.stock.symbol)
                if stock_data:
                    stocks.append({
                        'symbol': watchlist_stock.stock.symbol,
                        'price': stock_data['price'],
                        'change': stock_data['change'],
                        'change_percent': stock_data['change_percent']
                    })
            
            watchlist_data.append({
                'id': watchlist.id,
                'name': watchlist.name,
                'description': watchlist.description,
                'stocks': stocks
            })
        
        return jsonify(watchlist_data)

    # API route to create a new watchlist
    @app.route('/api/watchlists', methods=['POST'])
    @login_required
    def api_create_watchlist():
        data = request.json
        name = data.get('name')
        description = data.get('description', '')
        
        if not name:
            return jsonify({'error': 'Watchlist name is required'}), 400
        
        try:
            watchlist = WatchlistGroup(
                user_id=current_user.id,
                name=name,
                description=description
            )
            db.session.add(watchlist)
            db.session.commit()
            
            return jsonify({
                'success': True,
                'message': f'Created watchlist: {name}',
                'watchlist': {
                    'id': watchlist.id,
                    'name': watchlist.name,
                    'description': watchlist.description,
                    'stocks': []
                }
            })
        except Exception as e:
            db.session.rollback()
            logging.error(f"Error creating watchlist: {str(e)}")
            return jsonify({'error': f'Failed to create watchlist: {str(e)}'}), 500

    # API route to delete a watchlist
    @app.route('/api/watchlists/<int:watchlist_id>', methods=['DELETE'])
    @login_required
    def api_delete_watchlist(watchlist_id):
        try:
            watchlist = WatchlistGroup.query.filter_by(
                id=watchlist_id,
                user_id=current_user.id
            ).first()
            
            if not watchlist:
                return jsonify({'error': 'Watchlist not found'}), 404
            
            db.session.delete(watchlist)
            db.session.commit()
            
            return jsonify({
                'success': True,
                'message': f'Deleted watchlist: {watchlist.name}'
            })
        except Exception as e:
            db.session.rollback()
            logging.error(f"Error deleting watchlist: {str(e)}")
            return jsonify({'error': f'Failed to delete watchlist: {str(e)}'}), 500

    # API route to add stock to watchlist
    @app.route('/api/watchlists/<int:watchlist_id>/stocks', methods=['POST'])
    @login_required
    def api_add_stock_to_watchlist(watchlist_id):
        data = request.json
        symbol = data.get('symbol')
        
        if not symbol:
            return jsonify({'error': 'Symbol is required'}), 400
        
        try:
            watchlist = WatchlistGroup.query.filter_by(
                id=watchlist_id,
                user_id=current_user.id
            ).first()
            
            if not watchlist:
                return jsonify({'error': 'Watchlist not found'}), 404
            
            # First, get or create the stock
            stock = Stock.query.filter_by(symbol=symbol).first()
            if not stock:
                stock = Stock(symbol=symbol, company_name=symbol)  # You might want to fetch real company name
                db.session.add(stock)
                db.session.commit()
            
            # Check if stock is already in watchlist
            existing = WatchlistStock.query.filter_by(
                watchlist_group_id=watchlist_id,
                stock_id=stock.id
            ).first()
            
            if existing:
                return jsonify({'message': 'Stock already in watchlist'}), 200
            
            # Add to watchlist
            watchlist_stock = WatchlistStock(
                watchlist_group_id=watchlist_id,
                stock_id=stock.id
            )
            db.session.add(watchlist_stock)
            db.session.commit()
            
            return jsonify({
                'success': True,
                'message': f'Added {symbol} to watchlist'
            })
        except Exception as e:
            db.session.rollback()
            logging.error(f"Error adding to watchlist: {str(e)}")
            return jsonify({'error': f'Failed to add to watchlist: {str(e)}'}), 500

    # API route to remove stock from watchlist
    @app.route('/api/watchlists/<int:watchlist_id>/stocks/<symbol>', methods=['DELETE'])
    @login_required
    def api_remove_stock_from_watchlist(watchlist_id, symbol):
        try:
            watchlist = WatchlistGroup.query.filter_by(
                id=watchlist_id,
                user_id=current_user.id
            ).first()
            
            if not watchlist:
                return jsonify({'error': 'Watchlist not found'}), 404
            
            # Get the stock
            stock = Stock.query.filter_by(symbol=symbol).first()
            if not stock:
                return jsonify({'error': 'Stock not found'}), 404
            
            watchlist_stock = WatchlistStock.query.filter_by(
                watchlist_group_id=watchlist_id,
                stock_id=stock.id
            ).first()
            
            if not watchlist_stock:
                return jsonify({'error': 'Stock not found in watchlist'}), 404
            
            db.session.delete(watchlist_stock)
            db.session.commit()
            
            return jsonify({
                'success': True,
                'message': f'Removed {symbol} from watchlist'
            })
        except Exception as e:
            db.session.rollback()
            logging.error(f"Error removing from watchlist: {str(e)}")
            return jsonify({'error': f'Failed to remove from watchlist: {str(e)}'}), 500

    # API route to get market movers
    @app.route('/api/market-movers')
    @login_required
    def api_market_movers():
        try:
            # Common stocks to check
            common_stocks = ['AAPL', 'MSFT', 'GOOGL', 'AMZN', 'META', 'TSLA', 'NVDA', 'JPM', 'V', 'JNJ', 
                           'WMT', 'MA', 'PG', 'DIS', 'NFLX', 'INTC', 'CSCO', 'PFE', 'BAC', 'KO']
            
            # Get market data for each stock
            stocks_data = []
            for symbol in common_stocks:
                try:
                    stock_data = get_stock_price(symbol)
                    if stock_data:
                        stocks_data.append({
                            'symbol': symbol,
                            'price': stock_data.get('price', 0),
                            'change': stock_data.get('change', 0),
                            'change_percent': stock_data.get('change_percent', 0)
                        })
                except Exception as e:
                    logging.error(f"Error fetching data for {symbol}: {str(e)}")
                    continue
            
            # If no data was fetched, return default entries
            if not stocks_data:
                default_stocks = [
                    {'symbol': 'AAPL', 'price': 0, 'change': 0, 'change_percent': 0},
                    {'symbol': 'MSFT', 'price': 0, 'change': 0, 'change_percent': 0},
                    {'symbol': 'GOOGL', 'price': 0, 'change': 0, 'change_percent': 0},
                    {'symbol': 'AMZN', 'price': 0, 'change': 0, 'change_percent': 0},
                    {'symbol': 'META', 'price': 0, 'change': 0, 'change_percent': 0}
                ]
                return jsonify({
                    'success': False,
                    'error': 'Failed to fetch market data',
                    'top_gainers': default_stocks[:3],
                    'top_losers': default_stocks[:3],
                    'biggest_movers': default_stocks[:3],
                    'biggest_losers': default_stocks[:3]
                })
            
            # Sort stocks by percentage change
            stocks_by_percent = sorted(stocks_data, key=lambda x: x['change_percent'], reverse=True)
            top_gainers = stocks_by_percent[:5]  # Top 5 gainers by percentage
            top_losers = stocks_by_percent[-5:]  # Bottom 5 losers by percentage
            
            # Sort stocks by absolute dollar change
            stocks_by_dollar = sorted(stocks_data, key=lambda x: abs(x['change']), reverse=True)
            biggest_movers = [s for s in stocks_by_dollar if s['change'] > 0][:5]  # Top 5 positive dollar movers
            biggest_losers = [s for s in stocks_by_dollar if s['change'] < 0][:5]  # Top 5 negative dollar movers
            
            return jsonify({
                'success': True,
                'top_gainers': top_gainers,
                'top_losers': top_losers,
                'biggest_movers': biggest_movers,
                'biggest_losers': biggest_losers
            })
            
        except Exception as e:
            logging.error(f"Error in market movers: {str(e)}")
            # Return default data in case of error
            default_stocks = [
                {'symbol': 'AAPL', 'price': 0, 'change': 0, 'change_percent': 0},
                {'symbol': 'MSFT', 'price': 0, 'change': 0, 'change_percent': 0},
                {'symbol': 'GOOGL', 'price': 0, 'change': 0, 'change_percent': 0},
                {'symbol': 'AMZN', 'price': 0, 'change': 0, 'change_percent': 0},
                {'symbol': 'META', 'price': 0, 'change': 0, 'change_percent': 0}
            ]
            return jsonify({
                'success': False,
                'error': 'Failed to fetch market movers',
                'top_gainers': default_stocks[:3],
                'top_losers': default_stocks[:3],
                'biggest_movers': default_stocks[:3],
                'biggest_losers': default_stocks[:3]
            })

    @app.route('/api/news')
    def get_news():
        """Get market news"""
        try:
            news = news_service.get_market_news()
            return jsonify({
                'success': True,
                'news': news
            })
        except Exception as e:
            app.logger.error(f"Error fetching news: {str(e)}")
            return jsonify({
                'success': False,
                'error': 'Failed to fetch news'
            }), 500

    @app.route('/api/news/<symbol>')
    def get_stock_news(symbol):
        """Get news for a specific stock"""
        try:
            news = news_service.get_stock_news(symbol)
            return jsonify({
                'success': True,
                'news': news
            })
        except Exception as e:
            app.logger.error(f"Error fetching stock news: {str(e)}")
            return jsonify({
                'success': False,
                'error': 'Failed to fetch stock news'
            }), 500
