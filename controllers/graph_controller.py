from flask import Blueprint, jsonify
from flask_login import current_user, login_required
from models.models import Booking, ParkingSpot, ParkingLot
from extensions import db
from sqlalchemy import func

graph_bp = Blueprint('graph', __name__)

@graph_bp.route('/user/spot_summary_data')
@login_required
def user_spot_summary_data():
    user_id = current_user.id

    # Get all bookings for the current user
    bookings = Booking.query.filter_by(user_id=user_id).all()

    usage_data = {}

    for booking in bookings:
        lot_name = booking.parking_lot.location_name
        usage_data[lot_name] = usage_data.get(lot_name, 0) + 1

    summary_list = [{'spot': name, 'usage': count} for name, count in usage_data.items()]
    return jsonify(summary_list)

@graph_bp.route('/admin/lot_revenue_data')
@login_required
def lot_revenue_data():
    # Returns revenue per parking lot
    data = db.session.query(
        Booking.lot_id,
        func.count(Booking.id).label("count")
    ).group_by(Booking.lot_id).all()

    results = []
    for lot_id, count in data:
        lot = ParkingLot.query.get(lot_id)
        if lot:
            revenue = count * lot.price  # Assuming flat price per booking
            results.append({
                "lot": lot.location_name,
                "revenue": float(revenue)
            })
    return jsonify(results)


@graph_bp.route('/admin/lot_occupancy_data')
@login_required
def lot_occupancy_data():
    lots = ParkingLot.query.options(db.joinedload(ParkingLot.spots)).all()
    
    data = []
    for lot in lots:
        total = len(lot.spots)
        occupied = sum(not spot.is_available for spot in lot.spots)
        available = total - occupied
        data.append({
            "lot": lot.location_name,
            "available": available,
            "occupied": occupied
        })
    return jsonify(data)

