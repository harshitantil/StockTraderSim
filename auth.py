from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField, EmailField
from wtforms.validators import DataRequired, Email, EqualTo, Length, ValidationError

from extensions import db
from models import User, Wallet

# Create forms for authentication
class LoginForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired()])
    password = PasswordField('Password', validators=[DataRequired()])
    submit = SubmitField('Login')

class RegistrationForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired(), Length(min=3, max=20)])
    email = EmailField('Email', validators=[DataRequired(), Email()])
    password = PasswordField('Password', validators=[DataRequired(), Length(min=6)])
    confirm_password = PasswordField('Confirm Password', 
                                     validators=[DataRequired(), EqualTo('password')])
    submit = SubmitField('Register')
    
    def validate_username(self, username):
        user = User.query.filter_by(username=username.data).first()
        if user:
            raise ValidationError('Username already taken. Please choose a different one.')
            
    def validate_email(self, email):
        user = User.query.filter_by(email=email.data).first()
        if user:
            raise ValidationError('Email already registered. Please use a different one.')

# Authentication functions
def register_user(form):
    hashed_password = generate_password_hash(form.password.data)
    new_user = User(username=form.username.data, 
                    email=form.email.data, 
                    password_hash=hashed_password)
    
    try:
        db.session.add(new_user)
        db.session.commit()
        
        # Create a default wallet for the new user
        wallet = Wallet(
            user_id=new_user.id,
            name="Main Wallet",  # Default wallet name
            balance=0.00
        )
        db.session.add(wallet)
        db.session.commit()
        
        return True
    except Exception as e:
        db.session.rollback()
        flash(f'An error occurred during registration: {str(e)}', 'danger')
        return False

def authenticate_user(form):
    user = User.query.filter_by(username=form.username.data).first()
    
    if user and check_password_hash(user.password_hash, form.password.data):
        login_user(user)
        return True
    return False
