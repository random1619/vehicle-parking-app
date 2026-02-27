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
        return sum(1 for spot in self.spots if spot.is_available)

class Booking(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    lot_id = db.Column(db.Integer, db.ForeignKey('parking_lot.id'), nullable=False)
    vehicle_no = db.Column(db.String(20), nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    status = db.Column(db.String(10), default='active')
    spot_id = db.Column(db.Integer, db.ForeignKey('parking_spot.id'), nullable=False)
    release_time = db.Column(db.DateTime, nullable=True)
    cost = db.Column(db.Float, nullable=True)
    
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


class Vehicle(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    label = db.Column(db.String(50), nullable=True)
    plate_number = db.Column(db.String(20), nullable=False)
    is_default = db.Column(db.Boolean, default=False)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    user = db.relationship('User', backref='vehicles')

    __table_args__ = (
        db.UniqueConstraint('user_id', 'plate_number', name='uix_user_vehicle_plate'),
    )


class SpotHold(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    lot_id = db.Column(db.Integer, db.ForeignKey('parking_lot.id'), nullable=False)
    spot_id = db.Column(db.Integer, db.ForeignKey('parking_spot.id'), nullable=False)
    status = db.Column(db.String(20), default='active')  # active, converted, expired, cancelled
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    expires_at = db.Column(db.DateTime, nullable=False)

    user = db.relationship('User', backref='spot_holds')
    lot = db.relationship('ParkingLot', backref='spot_holds')
    spot = db.relationship('ParkingSpot', backref='spot_holds')


class WaitlistEntry(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    lot_id = db.Column(db.Integer, db.ForeignKey('parking_lot.id'), nullable=False)
    vehicle_id = db.Column(db.Integer, db.ForeignKey('vehicle.id'), nullable=True)
    vehicle_no = db.Column(db.String(20), nullable=False)
    requested_start = db.Column(db.DateTime, nullable=True)
    requested_duration_hours = db.Column(db.Integer, default=1, nullable=False)
    status = db.Column(db.String(20), default='waiting')  # waiting, fulfilled, cancelled
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    notified_at = db.Column(db.DateTime, nullable=True)
    fulfilled_at = db.Column(db.DateTime, nullable=True)

    user = db.relationship('User', backref='waitlist_entries')
    lot = db.relationship('ParkingLot', backref='waitlist_entries')
    vehicle = db.relationship('Vehicle', backref='waitlist_entries')


class ScheduledBooking(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    lot_id = db.Column(db.Integer, db.ForeignKey('parking_lot.id'), nullable=False)
    vehicle_id = db.Column(db.Integer, db.ForeignKey('vehicle.id'), nullable=True)
    vehicle_no = db.Column(db.String(20), nullable=False)
    requested_start = db.Column(db.DateTime, nullable=False)
    duration_hours = db.Column(db.Integer, default=1, nullable=False)
    status = db.Column(db.String(20), default='scheduled')  # scheduled, converted, cancelled, missed
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    assigned_spot_id = db.Column(db.Integer, db.ForeignKey('parking_spot.id'), nullable=True)
    converted_booking_id = db.Column(db.Integer, db.ForeignKey('booking.id'), nullable=True)

    user = db.relationship('User', backref='scheduled_bookings')
    lot = db.relationship('ParkingLot', backref='scheduled_bookings')
    vehicle = db.relationship('Vehicle', backref='scheduled_bookings')
    assigned_spot = db.relationship('ParkingSpot', backref='scheduled_bookings')
    converted_booking = db.relationship('Booking', backref='scheduled_source')


class Invoice(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    booking_id = db.Column(db.Integer, db.ForeignKey('booking.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    invoice_no = db.Column(db.String(32), unique=True, nullable=False)
    amount = db.Column(db.Float, nullable=False)
    currency = db.Column(db.String(8), default='INR', nullable=False)
    status = db.Column(db.String(20), default='paid')  # paid, pending, failed
    payment_ref = db.Column(db.String(64), nullable=True)
    issued_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    paid_at = db.Column(db.DateTime, nullable=True)

    booking = db.relationship('Booking', backref='invoices')
    user = db.relationship('User', backref='invoices')


class NotificationLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    channel = db.Column(db.String(20), default='in_app', nullable=False)  # in_app, email, sms
    notification_type = db.Column(db.String(50), nullable=False)
    subject = db.Column(db.String(120), nullable=True)
    message = db.Column(db.Text, nullable=False)
    status = db.Column(db.String(20), default='queued', nullable=False)  # queued, sent, failed
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    sent_at = db.Column(db.DateTime, nullable=True)
    error_message = db.Column(db.Text, nullable=True)

    user = db.relationship('User', backref='notifications')


class PasswordResetToken(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    token_hash = db.Column(db.String(128), unique=True, nullable=False)
    expires_at = db.Column(db.DateTime, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    used_at = db.Column(db.DateTime, nullable=True)

    user = db.relationship('User', backref='password_reset_tokens')


class SpotMaintenanceWindow(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    spot_id = db.Column(db.Integer, db.ForeignKey('parking_spot.id'), nullable=False)
    lot_id = db.Column(db.Integer, db.ForeignKey('parking_lot.id'), nullable=False)
    reason = db.Column(db.String(200), nullable=True)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    starts_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    ends_at = db.Column(db.DateTime, nullable=True)
    created_by = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)

    spot = db.relationship('ParkingSpot', backref='maintenance_windows')
    lot = db.relationship('ParkingLot', backref='maintenance_windows')
    creator = db.relationship('User', backref='created_maintenance_windows')
    
