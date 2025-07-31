import os
import secrets
from flask import Flask, g
from extensions import db, login_manager, migrate
from werkzeug.security import generate_password_hash
from models.models import User, ParkingLot, Booking  # Import here for app-wide access

admin_check_done = False  # Global flag to avoid multiple inserts

def create_app():
    app = Flask(__name__)
    app.config['SECRET_KEY'] = secrets.token_hex(16)
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///parking.db'
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
    
    @app.before_request
    def ensure_admin_user_exists():
        global admin_check_done
        if not admin_check_done:
            with app.app_context():
                if not User.query.filter_by(email='admin@parking.com').first():
                    admin = User(
                        email='admin@parking.com',
                        password=generate_password_hash('admin123'),
                        full_name='Admin',
                        address='Head Office',
                        pincode='000000',
                        role='admin'
                    )
                    db.session.add(admin)
                    db.session.commit()
                    print(" Admin user created: admin@parking.com / admin123")
                admin_check_done = True

    return app

app = create_app()

if __name__ == '__main__':
    app.run(debug=True)
