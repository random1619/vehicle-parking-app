from extensions import db
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime


class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(150), unique=True, nullable=False)
    password = db.Column(db.String(255), nullable = False)
    full_name = db.Column(db.String(100))
    address = db.Column(db.String(200))
    pincode = db.Column(db.String(10))
    role = db.Column(db.String(10), default='user')  # 'user' or 'admin'
    
    def set_password(self, password):
        self.password= generate_password_hash(password)
        
    def check_password(self, password):
        return check_password_hash(self.password, password)


class ParkingLot(db.Model):
   # __tablename__ = 'parking_lot'

    id = db.Column(db.Integer, primary_key=True)
    # # addition
    # lot_id = db.Column(db.Integer, db.ForeignKey('parking_lot.id'), nullable=False)
    # spot_number = db.Column(db.Integer, nullable=False)  # <-- MANUALLY controlled
    # is_available = db.Column(db.Boolean, default=True)
    # __table_args__ = (db.UniqueConstraint('lot_id', 'spot_number', name='unique_spot_per_lot'),)

    owner_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    location_name = db.Column(db.String(100), nullable=False)
    address = db.Column(db.String(200), nullable=False)
    pincode = db.Column(db.String(10), nullable=False) 
    price = db.Column(db.Float, nullable=False) 
    total_slots = db.Column(db.Integer, nullable=False)
    available_slots = db.Column(db.Integer, nullable=False)
    owner = db.relationship("User")
    spots = db.relationship('ParkingSpot', backref='lot', cascade='all, delete-orphan')

    @property
    def available_spots(self):
        return sum(1 for spot in self.spots if spot.status == 'A')

class Booking(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    lot_id = db.Column(db.Integer, db.ForeignKey('parking_lot.id'), nullable=False)
    vehicle_no = db.Column(db.String(20), nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    status = db.Column(db.String(10), default='active')
    spot_id = db.Column(db.Integer, db.ForeignKey('parking_spot.id'), nullable=False)
    
    # Relationship to ParkingSpot
    parking_spot = db.relationship('ParkingSpot', backref='bookings', lazy=True)
    
    # Property to get spot_number
    @property
    def spot_number(self):
        return self.parking_spot.spot_number if self.parking_spot else None
    
    user = db.relationship('User', backref='bookings')
    parking_lot = db.relationship('ParkingLot', backref='bookings')
    
# class SearchHistory(db.Model):
#     id = db.Column(db.Integer, primary_key = True)
#     user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
#     search_query = db.Column(db.String(100))
#     searched_at = db.Column(db.DateTime, default=datetime.utcnow)


class ParkingSpot(db.Model):
   # __tablename__ = 'parking_lot'
    __table_args__ = (
        db.UniqueConstraint('lot_id', 'spot_number', name='uix_lot_spot'),
    )
    id = db.Column(db.Integer, primary_key=True)
    lot_id = db.Column(db.Integer, db.ForeignKey('parking_lot.id'), nullable = False)
    spot_number = db.Column(db.Integer, nullable=False)
    is_available = db.Column(db.Boolean, default=True)
   # lot = db.relationship('ParkingLot', backref='spots', lazy=True)
    
