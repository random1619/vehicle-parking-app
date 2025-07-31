from flask import Blueprint, redirect, url_for, flash, request, render_template
from flask_login import login_required, current_user
from models.models import db, ParkingSpot, Booking, ParkingLot
from datetime import datetime


user_bp = Blueprint('user', __name__)




# @user_bp.route('/user/book/<int:lot_id>', methods=['GET', 'POST'])
# @login_required
# def book_parking_lot(lot_id):
#     lot = ParkingSpot.query.get_or_404(lot_id)
    
#     if request.method == 'POST':
#         vehicle_no = request.form['vehicle_number']
        
#         # Concept: we will assign lowest id spot available in the lot
#         spot = ParkingSpot.query.filter_by(lot_id=lot_id, is_available=True).order_by(ParkingSpot.spot_number.asc()).first()
#         if not spot:
#             flash('No available spots in this lot.', 'danger')
#             return redirect(url_for('dashboard.user_dashboard'))
        
#         # now we will create the booking 
#         new_booking = Booking(
#             user_id=current_user.id,
#             lot_id=lot_id,
#             spot_id=spot.id,
#             vehicle_no=vehicle_no,
#             timestamp=datetime.utcnow(),
#             status='active'
#         )
        
#         db.session.add(new_booking)
        
#         # mark the spot as occupied
        
#         spot.status = 'O'
#         db.session.commit()
        
#         flash(f'Successfully booked Spot {spot.spot_number} at {lot.location_name}', 'success')
#         return redirect(url_for('dashboard.user_dashboard'))
#     return render_template('book.html', lot=lot)


@user_bp.route('/book/<int:lot_id>', methods=['GET', 'POST'])
@login_required
def book_parking_lot(lot_id):
    lot = ParkingLot.query.get_or_404(lot_id)

    # ✅ Get the first available spot in the lot
    available_spot = ParkingSpot.query.filter_by(lot_id=lot.id, is_available=True).order_by(ParkingSpot.spot_number).first()

    if not available_spot:
        flash('No available slots in this parking lot.', 'danger')
        return redirect(url_for('user.search_results'))

    if request.method == 'POST':
        vehicle_no = request.form['vehicle_number']

        # ✅ Create booking
        booking = Booking(
            user_id=current_user.id,
            lot_id=lot.id,
            vehicle_no=vehicle_no,
            spot_id=available_spot.id,
        )

        # ✅ Mark spot as booked
        available_spot.is_available = False
        db.session.add(booking)
        db.session.commit()

        flash(f'Parking spot {available_spot.spot_number} booked successfully!', 'success')
        return redirect(url_for('dashboard.user_dashboard'))

    return render_template('book.html', lot=lot, spot=available_spot)


# @user_bp.route('/user/release/<int:booking_id>', methods=['GET','POST'])
# @login_required
# def release_booking(booking_id):
#     booking = Booking.query.get_or_404(booking_id)
    
#     #Ensure the current user owns this booking
#     if booking.user_id != current_user.id:
#         flash('Unauthorized action!', 'danger')
#         return redirect(url_for('dashboard.user_dashboard'))
    
#     # if GET request: show release.html with booking info
#     if request.method == 'GET':
#         spot = ParkingSpot.query.filter_by(id=booking.spot_id).first()
#         if not spot:
#             flash('Parking spot not found.', "danger")
#             return redirect(url_for('dashboard.user_dashboard'))
#         release_time = datetime.utcnow()
#         duration_hours = (release_time - booking.timestamp).total_seconds()/ 3600
#         duration_hours = max(1, round(duration_hours))
        
#         # Cost/hour comes from the AdminSettings or ParkingLot
#         cost_per_hour = spot.lot.price
#         total_cost = duration_hours * cost_per_hour
        
#         return render_template(
#             'release.html',
#             booking=booking,
#             spot=spot, 
#             release_time=release_time,
#             duration_hours=duration_hours,
#             total_cost=total_cost
#         )
    
#     # if POST request: finalize release
#     if booking.status != 'active':
#         flash('This booking is already released.', 'info')
#         return redirect(url_for('dashboard.user_dashboard'))
    
    
    
#     # calculation of duration and cost
#     release_time= datetime.utcnow()
#     duration_hours=(release_time - booking.timestamp).total_seconds() / 3600
#     duration_hours = max(1, round(duration_hours))
#     spot = ParkingSpot.query.filter_by(id=booking.spot_id).first()
#     cost_per_hour = spot.price
#     total_cost = duration_hours * cost_per_hour
    
#     # update booking 
#     booking.status = 'released'
#     booking.release_time = release_time
#     booking.cost = total_cost
#     db.session.commit()
    
    
#     # update spot availability
#     if spot:
#         spot.status = 'A'
#         db.session.commit()
    
#     flash(f'Booking released! Duration: {duration_hours} hour(s), Cost:  ₹{total_cost:.2f}', 'success')
#     return redirect(url_for('dashboard.user_dashboard'))
  

@user_bp.route('/user/release/<int:booking_id>', methods=['GET', 'POST'])
@login_required
def release_booking(booking_id):
    booking = Booking.query.get_or_404(booking_id)
    
    if booking.user_id != current_user.id:
        flash('Unauthorized action!', 'danger')
        return redirect(url_for('dashboard.user_dashboard'))

    spot = ParkingSpot.query.get(booking.spot_id)
    if not spot:
        flash('Parking spot not found.', "danger")
        return redirect(url_for('dashboard.user_dashboard'))

    # GET request - show confirmation page
    if request.method == 'GET':
        release_time = datetime.utcnow()
        duration_hours = max(1, round((release_time - booking.timestamp).total_seconds() / 3600))
        total_cost = duration_hours * spot.lot.price

        return render_template(
            'release.html',
            booking=booking,
            spot=spot,
            release_time=datetime.utcnow(),
            duration_hours=duration_hours,
            total_cost=round(total_cost, 2)
        )

    # POST request — finalize release
    if booking.status != 'active':
        flash('This booking is already released.', 'info')
        return redirect(url_for('dashboard.user_dashboard'))

    # Calculate cost again
    release_time = datetime.utcnow()
    duration_hours = (release_time - booking.timestamp).total_seconds() / 3600
    duration_hours = max(1, round(duration_hours))
    cost_per_hour = spot.lot.price
    total_cost = duration_hours * cost_per_hour

    # Update booking
    booking.status = 'released'
    booking.release_time = release_time
    booking.cost = total_cost

    # Update spot availability
    spot.is_available = True
    spot.lot.available_slots +=1

    db.session.commit()

    flash(f'Booking released! Duration: {duration_hours} hour(s), Cost: ₹{total_cost:.2f}', 'success')
    return redirect(url_for('dashboard.user_dashboard'))

   