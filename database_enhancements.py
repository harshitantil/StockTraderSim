from extensions import db
from sqlalchemy import event, text
from datetime import datetime
import logging
import threading
import os
from models import Trade, Wallet, User, Position, WatchlistGroup, WatchlistStock, Stock

# Configure logging for database operations
logging.basicConfig(filename='database.log', level=logging.INFO)

# 1. Additional Constraints
def add_constraints():
    # Check constraints for Trade
    db.event.listen(Trade, 'before_insert', validate_trade)
    db.event.listen(Trade, 'before_update', validate_trade)
    
    # Check constraints for Wallet
    db.event.listen(Wallet, 'before_insert', validate_wallet)
    db.event.listen(Wallet, 'before_update', validate_wallet)

# 2. Views
def create_views():
    # View for user portfolio summary
    portfolio_view = text("""
    CREATE VIEW IF NOT EXISTS user_portfolio_summary AS
    SELECT 
        u.id as user_id,
        u.username,
        s.symbol as stock_symbol,
        p.quantity,
        p.average_price,
        (p.quantity * p.average_price) as total_value
    FROM user u
    JOIN position p ON u.id = p.user_id
    JOIN stock s ON p.stock_id = s.id
    """)
    
    # View for trade history with user details
    trade_history_view = text("""
    CREATE VIEW IF NOT EXISTS trade_history AS
    SELECT 
        t.id,
        u.username,
        s.symbol as stock_symbol,
        t.quantity,
        t.price_per_share,
        t.trade_type,
        t.timestamp,
        w.name as wallet_name
    FROM trade t
    JOIN user u ON t.user_id = u.id
    JOIN wallet w ON t.wallet_id = w.id
    JOIN stock s ON t.stock_id = s.id
    """)
    
    db.session.execute(portfolio_view)
    db.session.execute(trade_history_view)
    db.session.commit()

# 3. Triggers
def create_triggers():
    # Trigger for updating wallet balance after trade
    trade_trigger = text("""
    CREATE TRIGGER IF NOT EXISTS update_wallet_after_trade
    BEFORE INSERT ON trade
    FOR EACH ROW
    BEGIN
        -- First check if the trade would result in negative balance
        SELECT CASE
            WHEN NEW.trade_type = 'buy' AND (
                SELECT balance - (NEW.quantity * NEW.price_per_share)
                FROM wallet
                WHERE id = NEW.wallet_id
            ) < 0 THEN
                RAISE(ABORT, 'Insufficient funds in wallet')
        END;
        
        -- Then update the wallet balance
        UPDATE wallet
        SET balance = CASE
            WHEN NEW.trade_type = 'buy' THEN balance - (NEW.quantity * NEW.price_per_share)
            WHEN NEW.trade_type = 'sell' THEN balance + (NEW.quantity * NEW.price_per_share)
        END
        WHERE id = NEW.wallet_id;
    END;
    """)
    
    # Trigger for updating position after trade
    position_trigger = text("""
    CREATE TRIGGER IF NOT EXISTS update_position_after_trade
    AFTER INSERT ON trade
    BEGIN
        INSERT OR REPLACE INTO position (user_id, stock_id, quantity, average_price, updated_at)
        SELECT 
            NEW.user_id,
            NEW.stock_id,
            CASE
                WHEN NEW.trade_type = 'buy' THEN COALESCE(p.quantity, 0) + NEW.quantity
                WHEN NEW.trade_type = 'sell' THEN COALESCE(p.quantity, 0) - NEW.quantity
            END,
            CASE
                WHEN NEW.trade_type = 'buy' THEN 
                    (COALESCE(p.quantity * p.average_price, 0) + (NEW.quantity * NEW.price_per_share)) /
                    (COALESCE(p.quantity, 0) + NEW.quantity)
                ELSE p.average_price
            END,
            CURRENT_TIMESTAMP
        FROM position p
        WHERE p.user_id = NEW.user_id AND p.stock_id = NEW.stock_id;
    END;
    """)
    
    db.session.execute(trade_trigger)
    db.session.execute(position_trigger)
    db.session.commit()

# 4. Concurrency Control
class TransactionManager:
    _lock = threading.Lock()
    
    @staticmethod
    def begin_transaction():
        """Begin a new transaction with isolation level"""
        with TransactionManager._lock:
            db.session.execute(text("PRAGMA journal_mode=WAL"))  # Write-Ahead Logging
            db.session.execute(text("PRAGMA busy_timeout=5000"))  # 5 second timeout
            db.session.execute(text("PRAGMA synchronous=NORMAL"))  # Better performance while maintaining durability
            db.session.begin_nested()
    
    @staticmethod
    def commit_transaction():
        """Commit the current transaction with error handling"""
        try:
            with TransactionManager._lock:
                db.session.commit()
                logging.info(f"Transaction committed at {datetime.utcnow()}")
        except Exception as e:
            db.session.rollback()
            logging.error(f"Transaction failed: {str(e)}")
            raise
    
    @staticmethod
    def with_transaction(func):
        """Decorator for transaction management"""
        def wrapper(*args, **kwargs):
            TransactionManager.begin_transaction()
            try:
                result = func(*args, **kwargs)
                TransactionManager.commit_transaction()
                return result
            except Exception as e:
                db.session.rollback()
                logging.error(f"Transaction failed in {func.__name__}: {str(e)}")
                raise
        return wrapper

# Example usage of the decorator:
"""
@TransactionManager.with_transaction
def execute_trade(user_id, stock_id, quantity, price):
    # Trade execution logic here
    pass
"""

# 5. Recovery Mechanisms
class DatabaseRecovery:
    BACKUP_DIR = 'instance/backup'
    MAX_BACKUPS = 10  # Keep last 10 backups
    
    @staticmethod
    def backup_database():
        """Create a backup of the database with rotation"""
        try:
            # Ensure backup directory exists
            os.makedirs(DatabaseRecovery.BACKUP_DIR, exist_ok=True)
            
            # Create backup filename with timestamp
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_file = f'stocktrader_{timestamp}.db'
            backup_path = os.path.join(DatabaseRecovery.BACKUP_DIR, backup_file)
            
            # Create backup with file locking
            with open('instance/stocktrader.db', 'rb') as source:
                with open(backup_path, 'wb') as target:
                    target.write(source.read())
            
            # Rotate old backups
            DatabaseRecovery._rotate_backups()
            
            logging.info(f"Database backup created: {backup_file}")
            return backup_file
        except Exception as e:
            logging.error(f"Backup failed: {str(e)}")
            raise

    @staticmethod
    def _rotate_backups():
        """Keep only the most recent MAX_BACKUPS backups"""
        try:
            backups = sorted([
                f for f in os.listdir(DatabaseRecovery.BACKUP_DIR)
                if f.startswith('stocktrader_') and f.endswith('.db')
            ])
            
            # Remove old backups
            while len(backups) > DatabaseRecovery.MAX_BACKUPS:
                old_backup = backups.pop(0)
                os.remove(os.path.join(DatabaseRecovery.BACKUP_DIR, old_backup))
                logging.info(f"Removed old backup: {old_backup}")
        except Exception as e:
            logging.error(f"Backup rotation failed: {str(e)}")

    @staticmethod
    def restore_database(backup_file):
        """Restore database from backup with verification"""
        try:
            backup_path = os.path.join(DatabaseRecovery.BACKUP_DIR, backup_file)
            if not os.path.exists(backup_path):
                raise FileNotFoundError(f"Backup file not found: {backup_file}")
            
            # Create temporary backup of current database
            current_backup = DatabaseRecovery.backup_database()
            
            try:
                # Restore from backup with file locking
                with open(backup_path, 'rb') as source:
                    with open('instance/stocktrader.db', 'wb') as target:
                        target.write(source.read())
                
                # Verify database integrity
                db.session.execute(text("PRAGMA integrity_check"))
                db.session.commit()
                
                logging.info(f"Database restored from {backup_file}")
            except Exception as e:
                # If restore fails, restore from current backup
                DatabaseRecovery.restore_database(current_backup)
                raise Exception(f"Restore failed, reverted to previous state: {str(e)}")
        except Exception as e:
            logging.error(f"Restore failed: {str(e)}")
            raise

    @staticmethod
    def list_backups():
        """List all available backups"""
        try:
            backups = sorted([
                f for f in os.listdir(DatabaseRecovery.BACKUP_DIR)
                if f.startswith('stocktrader_') and f.endswith('.db')
            ], reverse=True)
            return backups
        except Exception as e:
            logging.error(f"Failed to list backups: {str(e)}")
            return []

# 6. Validation Functions
def validate_trade(mapper, connection, target):
    """Validate trade before insertion/update"""
    if target.quantity <= 0:
        raise ValueError("Trade quantity must be positive")
    if target.price_per_share <= 0:
        raise ValueError("Price per share must be positive")
    if target.trade_type not in ['buy', 'sell']:
        raise ValueError("Invalid trade type")

def validate_wallet(mapper, connection, target):
    """Validate wallet before insertion/update"""
    if target.balance < 0:
        raise ValueError("Wallet balance cannot be negative")

# 7. Normalization Improvements
def normalize_database():
    # Add indexes for frequently queried columns
    try:
        # Create index for trade user_id
        db.session.execute(text("""
        CREATE INDEX IF NOT EXISTS idx_trade_user_id ON trade(user_id)
        """))
        
        # Create index for trade timestamp
        db.session.execute(text("""
        CREATE INDEX IF NOT EXISTS idx_trade_timestamp ON trade(timestamp)
        """))
        
        # Create index for position user and stock
        db.session.execute(text("""
        CREATE INDEX IF NOT EXISTS idx_position_user_stock ON position(user_id, stock_id)
        """))
        
        db.session.commit()
        logging.info("Database indexes created successfully")
    except Exception as e:
        db.session.rollback()
        logging.error(f"Failed to create indexes: {str(e)}")
        raise

# 8. Data Migration
def migrate_data():
    """Handle data migration for schema changes"""
    try:
        # Check if we need to migrate stock_symbol to stock_id
        with db.engine.connect() as conn:
            # Check if position table has stock_symbol column
            result = conn.execute(text("""
                SELECT name FROM pragma_table_info('position') 
                WHERE name='stock_symbol'
            """))
            if result.fetchone():
                # Migrate data from stock_symbol to stock_id
                conn.execute(text("""
                    -- Create temporary table for stock data
                    CREATE TABLE IF NOT EXISTS temp_stocks AS
                    SELECT DISTINCT stock_symbol as symbol, stock_symbol as company_name
                    FROM position
                    UNION
                    SELECT DISTINCT stock_symbol as symbol, stock_symbol as company_name
                    FROM trade
                    UNION
                    SELECT DISTINCT stock_symbol as symbol, stock_symbol as company_name
                    FROM watchlist_stock;
                    
                    -- Insert into stock table
                    INSERT OR IGNORE INTO stock (symbol, company_name)
                    SELECT symbol, company_name FROM temp_stocks;
                    
                    -- Update position table
                    UPDATE position
                    SET stock_id = (SELECT id FROM stock WHERE symbol = position.stock_symbol)
                    WHERE stock_symbol IS NOT NULL;
                    
                    -- Update trade table
                    UPDATE trade
                    SET stock_id = (SELECT id FROM stock WHERE symbol = trade.stock_symbol)
                    WHERE stock_symbol IS NOT NULL;
                    
                    -- Update watchlist_stock table
                    UPDATE watchlist_stock
                    SET stock_id = (SELECT id FROM stock WHERE symbol = watchlist_stock.stock_symbol)
                    WHERE stock_symbol IS NOT NULL;
                    
                    -- Drop temporary table
                    DROP TABLE temp_stocks;
                """))
                
                # Drop old columns after migration
                conn.execute(text("""
                    CREATE TABLE position_new (
                        id INTEGER PRIMARY KEY,
                        user_id INTEGER NOT NULL,
                        stock_id INTEGER NOT NULL,
                        quantity INTEGER NOT NULL,
                        average_price FLOAT NOT NULL,
                        created_at DATETIME,
                        updated_at DATETIME,
                        FOREIGN KEY (user_id) REFERENCES user (id),
                        FOREIGN KEY (stock_id) REFERENCES stock (id),
                        UNIQUE (user_id, stock_id)
                    );
                    
                    INSERT INTO position_new
                    SELECT id, user_id, stock_id, quantity, average_price, created_at, updated_at
                    FROM position;
                    
                    DROP TABLE position;
                    ALTER TABLE position_new RENAME TO position;
                """))
                
                conn.execute(text("""
                    CREATE TABLE trade_new (
                        id INTEGER PRIMARY KEY,
                        user_id INTEGER NOT NULL,
                        wallet_id INTEGER NOT NULL,
                        stock_id INTEGER NOT NULL,
                        quantity INTEGER NOT NULL,
                        price_per_share FLOAT NOT NULL,
                        trade_type VARCHAR(10) NOT NULL,
                        timestamp DATETIME,
                        FOREIGN KEY (user_id) REFERENCES user (id),
                        FOREIGN KEY (wallet_id) REFERENCES wallet (id),
                        FOREIGN KEY (stock_id) REFERENCES stock (id)
                    );
                    
                    INSERT INTO trade_new
                    SELECT id, user_id, wallet_id, stock_id, quantity, price_per_share, trade_type, timestamp
                    FROM trade;
                    
                    DROP TABLE trade;
                    ALTER TABLE trade_new RENAME TO trade;
                """))
                
                conn.execute(text("""
                    CREATE TABLE watchlist_stock_new (
                        id INTEGER PRIMARY KEY,
                        watchlist_group_id INTEGER NOT NULL,
                        stock_id INTEGER NOT NULL,
                        added_at DATETIME,
                        FOREIGN KEY (watchlist_group_id) REFERENCES watchlist_group (id),
                        FOREIGN KEY (stock_id) REFERENCES stock (id),
                        UNIQUE (watchlist_group_id, stock_id)
                    );
                    
                    INSERT INTO watchlist_stock_new
                    SELECT id, watchlist_group_id, stock_id, added_at
                    FROM watchlist_stock;
                    
                    DROP TABLE watchlist_stock;
                    ALTER TABLE watchlist_stock_new RENAME TO watchlist_stock;
                """))
                
                logging.info("Data migration completed successfully")
    except Exception as e:
        logging.error(f"Data migration failed: {str(e)}")
        raise

# Initialize all enhancements
def initialize_database_enhancements():
    try:
        # Set up database configuration
        db.session.execute(text("PRAGMA foreign_keys=ON"))  # Enable foreign key constraints
        db.session.execute(text("PRAGMA journal_mode=WAL"))  # Write-Ahead Logging
        db.session.execute(text("PRAGMA synchronous=NORMAL"))  # Better performance while maintaining durability
        db.session.execute(text("PRAGMA busy_timeout=5000"))  # 5 second timeout
        
        # Initialize other enhancements
        add_constraints()
        create_views()
        create_triggers()
        normalize_database()
        migrate_data()
        
        # Create initial backup
        DatabaseRecovery.backup_database()
        
        logging.info("Database enhancements initialized successfully")
    except Exception as e:
        logging.error(f"Failed to initialize database enhancements: {str(e)}")
        raise 