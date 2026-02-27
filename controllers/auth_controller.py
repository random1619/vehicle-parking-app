import hashlib
import secrets
from datetime import datetime, timedelta

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required, login_user, logout_user
from werkzeug.security import check_password_hash, generate_password_hash

from extensions import db, login_manager
from models.models import PasswordResetToken, User
from services import log_notification


auth_bp = Blueprint('auth', __name__)


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        email = request.form['email'].strip().lower()
        password = request.form['password']
        full_name = request.form['full_name']
        address = request.form['address']
        pincode = request.form['pincode']

        if User.query.filter_by(email=email).first():
            flash('Email already exists.', 'danger')
            return redirect(url_for('auth.register'))

        new_user = User(
            email=email,
            password=generate_password_hash(password),
            full_name=full_name,
            address=address,
            pincode=pincode,
            role='user',
        )

        db.session.add(new_user)
        db.session.commit()
        flash('Account created. Please sign in.', 'success')
        return redirect(url_for('auth.login'))

    return render_template('signup.html')


@auth_bp.route('/', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        if current_user.role == 'admin':
            return redirect(url_for('admin.dashboard'))
        return redirect(url_for('dashboard.user_dashboard'))

    if request.method == 'POST':
        email = request.form['email'].strip().lower()
        password = request.form['password']

        user = User.query.filter_by(email=email).first()
        if user and check_password_hash(user.password, password):
            login_user(user)
            if user.role == 'admin':
                return redirect(url_for('admin.dashboard'))
            return redirect(url_for('dashboard.user_dashboard'))

        flash('Invalid email or password.', 'danger')
        return redirect(url_for('auth.login'))

    return render_template('login.html')


@auth_bp.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        user = User.query.filter_by(email=email).first()

        if user:
            raw_token = secrets.token_urlsafe(32)
            token_hash = hashlib.sha256(raw_token.encode('utf-8')).hexdigest()

            PasswordResetToken.query.filter_by(user_id=user.id, used_at=None).delete()

            token_record = PasswordResetToken(
                user_id=user.id,
                token_hash=token_hash,
                expires_at=datetime.utcnow() + timedelta(minutes=30),
            )
            db.session.add(token_record)
            db.session.commit()

            reset_link = url_for('auth.reset_password', token=raw_token, _external=True)
            log_notification(
                user_id=user.id,
                notification_type='password_reset_requested',
                subject='Password Reset Request',
                message=f'Use this link to reset your password: {reset_link}',
                channel='email',
            )

            flash('Password reset link generated. Check your email. (Dev link shown below)', 'info')
            flash(reset_link, 'info')
        else:
            # Do not reveal whether user exists.
            flash('If an account exists for that email, a reset link has been sent.', 'info')

        return redirect(url_for('auth.forgot_password'))

    return render_template('forgot_password.html')


@auth_bp.route('/reset-password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    token_hash = hashlib.sha256(token.encode('utf-8')).hexdigest()
    token_record = PasswordResetToken.query.filter_by(token_hash=token_hash, used_at=None).first()

    if not token_record or token_record.expires_at < datetime.utcnow():
        flash('This reset link is invalid or expired.', 'danger')
        return redirect(url_for('auth.forgot_password'))

    if request.method == 'POST':
        password = request.form.get('password', '')
        confirm_password = request.form.get('confirm_password', '')

        if len(password) < 6:
            flash('Password must be at least 6 characters long.', 'danger')
            return redirect(request.url)

        if password != confirm_password:
            flash('Passwords do not match.', 'danger')
            return redirect(request.url)

        user = User.query.get(token_record.user_id)
        if not user:
            flash('User no longer exists.', 'danger')
            return redirect(url_for('auth.forgot_password'))

        user.password = generate_password_hash(password)
        token_record.used_at = datetime.utcnow()

        db.session.commit()

        log_notification(
            user_id=user.id,
            notification_type='password_reset_completed',
            subject='Password Updated',
            message='Your password was reset successfully.',
        )

        flash('Password updated successfully. Please sign in.', 'success')
        return redirect(url_for('auth.login'))

    return render_template('reset_password.html')


@auth_bp.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for('auth.login'))
