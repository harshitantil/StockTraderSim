import os
import logging
from flask import Flask, send_from_directory
from werkzeug.middleware.proxy_fix import ProxyFix
from extensions import db, login_manager
from flask_migrate import Migrate
from routes import register_routes
from models import User, Wallet, Trade, Position, WatchlistGroup, WatchlistStock
from config import Config
from datetime import datetime
from database_enhancements import initialize_database_enhancements, DatabaseRecovery, TransactionManager
from sqlalchemy import text

# Configure logging
logging.basicConfig(level=logging.DEBUG)

def create_app():
    # Create the Flask app
    app = Flask(__name__, static_folder='static')
    app.secret_key = os.environ.get("SESSION_SECRET", "dev-secret-key")  # Fallback for development
    app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)  # needed for url_for to generate with https

    # Load configuration
    app.config.from_object(Config)

    # Initialize extensions with app
    db.init_app(app)
    login_manager.init_app(app)
    login_manager.login_view = 'login'
    migrate = Migrate(app, db)

    # Add datetime filter
    @app.template_filter('datetime')
    def format_datetime(value, format='%Y-%m-%d %H:%M:%S'):
        if value is None:
            return ''
        if isinstance(value, str):
            try:
                value = datetime.fromisoformat(value.replace('Z', '+00:00'))
            except ValueError:
                return value
        return value.strftime(format)

    with app.app_context():
        try:
            # Import models
            from models import User  # noqa: F401
            
            @login_manager.user_loader
            def load_user(user_id):
                return User.query.get(int(user_id))
            
            # Create tables if they don't exist (without dropping existing data)
            db.create_all()
            
            # Import and register routes
            from routes import register_routes
            from wallet_routes import register_wallet_routes
            
            register_routes(app)
            register_wallet_routes(app)
            
            @app.route('/')
            def home():
                return "Welcome!"
            
            # Initialize database enhancements
            initialize_database_enhancements()
            
            # Create initial backup
            DatabaseRecovery.backup_database()
            
            logging.info("Application initialized successfully")
        except Exception as e:
            logging.error(f"Error during application initialization: {str(e)}")
            raise
    
    return app

app = create_app()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5001, debug=True)

@TransactionManager.with_transaction
def execute_trade(user_id, stock_id, quantity, price):
    # Your trade logic here
    pass

# Query the portfolio summary
portfolio = db.session.execute(text("SELECT * FROM user_portfolio_summary WHERE user_id = :user_id"), 
                             {"user_id": current_user.id}).fetchall()

# Query trade history
trades = db.session.execute(text("SELECT * FROM trade_history WHERE username = :username"), 
                          {"username": current_user.username}).fetchall()

# The database will automatically handle:
# - Concurrency control
# - Data integrity
# - Automatic backups
# - Recovery mechanisms
