from flask import Blueprint, jsonify, request, render_template
from flask_login import login_required, current_user
from extensions import db
from models import Wallet, WalletTransaction, Trade
from datetime import datetime

def register_wallet_routes(app):
    @app.route('/wallet')
    @login_required
    def wallet():
        return render_template('wallet.html', title='Wallet Management')

    @app.route('/api/wallets')
    @login_required
    def get_wallets():
        wallets = Wallet.query.filter_by(user_id=current_user.id).all()
        return jsonify([{
            'id': wallet.id,
            'name': wallet.name,
            'balance': wallet.balance,
            'last_updated': wallet.last_updated.isoformat() if wallet.last_updated else None
        } for wallet in wallets])

    @app.route('/api/wallets', methods=['POST'])
    @login_required
    def create_wallet():
        data = request.json
        name = data.get('name')
        initial_balance = float(data.get('initial_balance', 0))
        
        if not name:
            return jsonify({'error': 'Wallet name is required'}), 400
        
        try:
            wallet = Wallet(
                user_id=current_user.id,
                name=name,
                balance=initial_balance
            )
            db.session.add(wallet)
            db.session.commit()
            
            return jsonify({
                'id': wallet.id,
                'name': wallet.name,
                'balance': wallet.balance,
                'last_updated': wallet.last_updated.isoformat() if wallet.last_updated else None
            })
        except Exception as e:
            db.session.rollback()
            return jsonify({'error': str(e)}), 400

    @app.route('/api/wallets/<int:wallet_id>', methods=['DELETE'])
    @login_required
    def delete_wallet(wallet_id):
        wallet = Wallet.query.filter_by(id=wallet_id, user_id=current_user.id).first()
        if not wallet:
            return jsonify({'error': 'Wallet not found'}), 404
        
        try:
            db.session.delete(wallet)
            db.session.commit()
            return '', 204
        except Exception as e:
            db.session.rollback()
            return jsonify({'error': str(e)}), 400

    @app.route('/api/wallets/<int:wallet_id>/deposit', methods=['POST'])
    @login_required
    def deposit(wallet_id):
        data = request.json
        amount = float(data.get('amount', 0))
        
        if amount <= 0:
            return jsonify({'error': 'Amount must be greater than 0'}), 400
        
        wallet = Wallet.query.filter_by(id=wallet_id, user_id=current_user.id).first()
        if not wallet:
            return jsonify({'error': 'Wallet not found'}), 404
        
        try:
            # Update wallet balance first
            wallet.balance += amount
            
            # Create transaction record with the new balance
            transaction = WalletTransaction(
                wallet_id=wallet.id,
                amount=amount,
                type='deposit',
                balance_after=wallet.balance
            )
            
            db.session.add(transaction)
            db.session.commit()
            
            return jsonify({
                'id': wallet.id,
                'name': wallet.name,
                'balance': wallet.balance,
                'last_updated': wallet.last_updated.isoformat() if wallet.last_updated else None
            })
        except Exception as e:
            db.session.rollback()
            return jsonify({'error': str(e)}), 400

    @app.route('/api/wallets/<int:wallet_id>/withdraw', methods=['POST'])
    @login_required
    def withdraw(wallet_id):
        data = request.json
        amount = float(data.get('amount', 0))
        
        if amount <= 0:
            return jsonify({'error': 'Amount must be greater than 0'}), 400
        
        wallet = Wallet.query.filter_by(id=wallet_id, user_id=current_user.id).first()
        if not wallet:
            return jsonify({'error': 'Wallet not found'}), 404
        
        if wallet.balance < amount:
            return jsonify({'error': 'Insufficient funds'}), 400
        
        try:
            # Update wallet balance first
            wallet.balance -= amount
            
            # Create transaction record with the new balance
            transaction = WalletTransaction(
                wallet_id=wallet.id,
                amount=amount,
                type='withdrawal',
                balance_after=wallet.balance
            )
            
            db.session.add(transaction)
            db.session.commit()
            
            return jsonify({
                'id': wallet.id,
                'name': wallet.name,
                'balance': wallet.balance,
                'last_updated': wallet.last_updated.isoformat() if wallet.last_updated else None
            })
        except Exception as e:
            db.session.rollback()
            return jsonify({'error': str(e)}), 400

    @app.route('/api/wallets/transactions')
    @login_required
    def get_transactions():
        # Get wallet transactions
        wallet_transactions = WalletTransaction.query.join(Wallet).filter(
            Wallet.user_id == current_user.id
        ).order_by(WalletTransaction.timestamp.desc()).all()
        
        # Get trades
        trades = Trade.query.join(Wallet).filter(
            Wallet.user_id == current_user.id
        ).order_by(Trade.timestamp.desc()).all()
        
        # Combine and sort all transactions
        all_transactions = []
        
        # Add wallet transactions
        for t in wallet_transactions:
            all_transactions.append({
                'id': f'w{t.id}',
                'wallet_id': t.wallet_id,
                'wallet_name': t.wallet.name,
                'amount': t.amount,
                'type': t.type,
                'timestamp': t.timestamp.isoformat(),
                'balance_after': t.balance_after,
                'transaction_type': 'wallet'
            })
        
        # Add trades
        for t in trades:
            all_transactions.append({
                'id': t.id,
                'type': t.trade_type,
                'amount': t.price_per_share * t.quantity,
                'symbol': t.stock.symbol,
                'quantity': t.quantity,
                'price': t.price_per_share,
                'timestamp': t.timestamp.strftime('%Y-%m-%d %H:%M:%S'),
                'transaction_type': 'trade'
            })
        
        # Sort by timestamp
        all_transactions.sort(key=lambda x: x['timestamp'], reverse=True)
        
        return jsonify(all_transactions) 