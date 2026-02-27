import os
import secrets
from flask import Flask, g
from extensions import db, login_manager, migrate
from werkzeug.security import generate_password_hash
from models.models import User, ParkingLot, Booking  # Import here for app-wide access

admin_check_done = False  # Global flag to avoid multiple inserts

def create_app():
    app = Flask(__name__)
    
    # Use environment variable for SECRET_KEY, fallback to generated key for development
    app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', secrets.token_hex(16))
    
    # Support both SQLite and PostgreSQL via DATABASE_URL environment variable
    database_url = os.environ.get('DATABASE_URL', 'sqlite:///parking.db')
    
    # Fix for Heroku/Render PostgreSQL URL (postgres:// -> postgresql://)
    if database_url.startswith('postgres://'):
        database_url = database_url.replace('postgres://', 'postgresql://', 1)
    
    app.config['SQLALCHEMY_DATABASE_URI'] = database_url
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

    db.init_app(app)
    login_manager.init_app(app)
    migrate.init_app(app, db)
    login_manager.login_view = 'auth.login'

    from controllers.auth_controller import auth_bp
    from controllers.dashboard_controller import dashboard_bp
    from controllers.admin_controller import admin_bp
    from controllers.user_controller import user_bp
    from controllers.graph_controller import graph_bp


    app.register_blueprint(auth_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(user_bp)
    app.register_blueprint(graph_bp)

    # Ensure newly added feature tables exist in non-migrated environments.
    with app.app_context():
        db.create_all()
    
    @app.before_request
    def ensure_admin_user_exists():
        global admin_check_done
        if not admin_check_done:
            with app.app_context():
                admin_email = os.environ.get('ADMIN_EMAIL', 'admin@parking.com')
                admin_password = os.environ.get('ADMIN_PASSWORD', 'admin123')
                
                if not User.query.filter_by(email=admin_email).first():
                    admin = User(
                        email=admin_email,
                        password=generate_password_hash(admin_password),
                        full_name='Admin',
                        address='Head Office',
                        pincode='000000',
                        role='admin'
                    )
                    db.session.add(admin)
                    db.session.commit()
                    print(f" Admin user created: {admin_email}")
                admin_check_done = True

    return app

app = create_app()

if __name__ == '__main__':
    # Only enable debug mode in development
    debug_mode = os.environ.get('FLASK_ENV', 'development') == 'development'
    app.run(debug=debug_mode)
