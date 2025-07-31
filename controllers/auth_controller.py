from flask import Blueprint,Flask, render_template, request, flash, url_for, redirect, redirect
from flask_login import login_user, logout_user, current_user, login_required
from models.models import User
from extensions import db, login_manager
from werkzeug.security import generate_password_hash, check_password_hash
    
auth_bp = Blueprint('auth', __name__)
    

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))



@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        full_name = request.form['full_name']
        address = request.form['address']
        pincode = request.form['pincode']
        
        if User.query.filter_by(email=email).first():
            flash('Email already exists!', 'danger')
            return redirect(url_for('auth.register'))
        
        new_user = User(
            email = email,
            password = generate_password_hash(password),
            full_name = full_name,
            address = address,
            pincode = pincode,
            role = 'user'
        )
        
        db.session.add(new_user)
        db.session.commit()
        flash('Account created! Please login', 'success')
        return redirect(url_for('auth.login'))
    
    return render_template('signup.html')

@auth_bp.route('/', methods = ['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        
        user = User.query.filter_by(email=email).first()
        if user and check_password_hash(user.password, password):
            login_user(user)
            
            if user.role == 'admin':
                return redirect(url_for('dashboard.admin_dashboard'))
            
            else:
                return redirect(url_for('dashboard.user_dashboard'))
        else:
            flash('Invalid email or password', 'danger')
            return redirect(url_for('auth.login'))
    return render_template('login.html')


@auth_bp.route('/logout')
@login_required
def logout():
    logout_user()
    flash('you have been logged out', 'info')
    return redirect(url_for('auth.login'))
