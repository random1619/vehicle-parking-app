from flask import Blueprint, render_template, redirect, url_for, flash, request, abort
from flask_login import login_required, current_user
from models.models import db, ParkingLot, ParkingSpot, Booking, User  # Added Booking here
from .decorators import admin_required
from datetime import datetime

admin_bp = Blueprint('admin', __name__, url_prefix='/admin')


@admin_bp.route('/dashboard')
@login_required
@admin_required
def dashboard():
    lots = ParkingLot.query.all()
    parking_lots = []

    for lot in lots:
        # Count only spots that are marked unavailable (occupied)
        occupied_count = ParkingSpot.query.filter_by(lot_id=lot.id, is_available=False).count()

        # Append everything needed to the parking_lots list
        parking_lots.append({
            'id': lot.id,
            'location_name': lot.location_name,
            'total_slots': lot.total_slots,
            'occupied_count': occupied_count,
            'spots': lot.spots  # so you can loop in template
        })

    return render_template("dashboard_admin.html", parking_lots=parking_lots)


# priority no - 2
# @admin_bp.route('/edit_lot/<int:lot_id>', methods=['GET', 'POST'])
# @login_required
# @admin_required
# def edit_lot(lot_id):
#     lot = ParkingLot.query.get_or_404(lot_id)
    
#     if request.method == 'POST':
        
#         # Capture old total_slots before modifying
#         old_total = lot.total_slots
        
#         #update lot details
#         lot.location_name = request.form['location_name']
#         lot.address = request.form['address']
#         lot.pincode = request.form['pincode']
#         lot.price = float(request.form['price'])
#         new_total = int(request.form['total_slots'])
       
        
        
#         if new_total > old_total:
#             # Add new Available Slots
#             for i in range(old_total + 1, new_total + 1):
#                 new_spot = ParkingSpot(lot_id=lot.id, spot_number=f"S{i}", is_available=True)
#                 db.session.add(new_spot)
        
#         elif new_total < old_total:
#             # Determine how many spots need to be removed
#             spots_to_remove = old_total - new_total
            
#             # Get spots from the end that are available
#             removable_spots = ParkingSpot.query.filter_by(
#                 lot_id = lot.id,
#                 is_available=True
#             ).order_by(ParkingSpot.spot_number.desc()).limit(spots_to_remove).all()
            
#             if len(removable_spots) < spots_to_remove:
#                 flash("Cannot reduce total slots because not enough free spots are available.","danger")
#                 return redirect(request.url)
            
#             for spot in removable_spots:
#                 db.session.delete(spot)
        
#         # Update total_slots after adjustments
#         lot.total_slots = new_total
        
#         # Recalculate available_slots
        
#         lot.available_slots = ParkingSpot.query.filter_by(lot_id=lot.id, is_available=True).count()
        
#         db.session.commit()
#         flash('Parking Lot updated successfully!', "info")
        
#         return redirect(url_for('admin.dashboard'))
#     return render_template('edit_parking_lot.html', lot=lot)




# priority no - 1
        
# @admin_bp.route('/edit_lot/<int:lot_id>', methods=['GET', 'POST'])
# @login_required
# @admin_required
# def edit_lot(lot_id):
#     lot = ParkingLot.query.get_or_404(lot_id)
    
#     if request.method == 'POST':
#         old_total = lot.total_slots

#         # Update lot fields
#         lot.location_name = request.form['location_name']
#         lot.address = request.form['address']
#         lot.pincode = request.form['pincode']
#         lot.price = float(request.form['price'])
#         new_total = int(request.form['total_slots'])

#         if new_total > old_total:
#             # Add new spots
#             for i in range(old_total + 1, new_total + 1):
#                 new_spot = ParkingSpot(lot_id=lot.id, spot_number=f"S{i}", is_available=True)
#                 db.session.add(new_spot)

#         elif new_total < old_total:
#             spots_to_remove = old_total - new_total

#             removable_spots = ParkingSpot.query.filter_by(
#                 lot_id=lot.id,
#                 is_available=True
#             ).order_by(ParkingSpot.spot_number.desc()).limit(spots_to_remove).all()

#             if len(removable_spots) < spots_to_remove:
#                 flash("❌ Cannot reduce total slots — not enough free spots are available.", "danger")
#                 return redirect(request.url)

#             for spot in removable_spots:
#                 # Delete associated bookings (to avoid FK constraint)
#                 Booking.query.filter_by(spot_id=spot.id).delete()
#                 db.session.delete(spot)

#         # Update total and available slots
#         lot.total_slots = new_total
#         lot.available_slots = ParkingSpot.query.filter_by(lot_id=lot.id, is_available=True).count()

#         db.session.commit()
#         flash('✅ Parking Lot updated successfully!', "info")
#         return redirect(url_for('admin.dashboard'))

#     return render_template('edit_parking_lot.html', lot=lot)
        
        
@admin_bp.route('/edit_lot/<int:lot_id>', methods=['GET', 'POST'])
@login_required
@admin_required
def edit_lot(lot_id):
    lot = ParkingLot.query.get_or_404(lot_id)

    if request.method == 'POST':
        # Update lot fields
        lot.location_name = request.form['location_name']
        lot.address = request.form['address']
        lot.pincode = request.form['pincode']
        lot.price = float(request.form['price'])
        desired_spots = int(request.form['total_slots'])

        # Fetch all current spot numbers for this lot
        existing_spots = ParkingSpot.query.filter_by(lot_id=lot.id).all()
        existing_spot_numbers = {spot.spot_number for spot in existing_spots}
        current_spots = len(existing_spot_numbers)

        # Determine the expected spot numbers (e.g., S1 to S4)
        expected_numbers = {f"S{i+1}" for i in range(desired_spots)}

        # Find missing numbers like "S3"
        missing_spots = sorted(expected_numbers - existing_spot_numbers, key=lambda x: int(x[1:]))

        if desired_spots > current_spots:
            spots_to_add = desired_spots - current_spots
            added = 0

            # Reuse missing labels first
            for spot_number in missing_spots:
                if added >= spots_to_add:
                    break
                new_spot = ParkingSpot(lot_id=lot.id, spot_number=spot_number, is_available=True)
                db.session.add(new_spot)
                added += 1

            # Add new numbered spots beyond max index if still needed
            if added < spots_to_add:
                existing_indices = [int(s[1:]) for s in existing_spot_numbers]
                max_index = max(existing_indices, default=0)

                while added < spots_to_add:
                    max_index += 1
                    new_spot_number = f"S{max_index}"
                    new_spot = ParkingSpot(lot_id=lot.id, spot_number=new_spot_number, is_available=True)
                    db.session.add(new_spot)
                    added += 1

        elif desired_spots < current_spots:
            # Reduce: only delete *available* spots
            removable_spots = ParkingSpot.query.filter_by(
                lot_id=lot.id,
                is_available=True
            ).order_by(ParkingSpot.spot_number.desc()).all()

            if len(removable_spots) < (current_spots - desired_spots):
                flash("❌ Cannot reduce total slots — not enough free spots are available.", "danger")
                return redirect(request.url)

            extra = current_spots - desired_spots
            for spot in removable_spots:
                if extra <= 0:
                    break
                # Remove bookings if they exist
                Booking.query.filter_by(spot_id=spot.id).delete()
                db.session.delete(spot)
                extra -= 1

        # Update total and available spots
        lot.total_slots = desired_spots
        lot.available_slots = ParkingSpot.query.filter_by(lot_id=lot.id, is_available=True).count()

        db.session.commit()
        flash('✅ Parking Lot updated successfully!', "info")
        return redirect(url_for('admin.dashboard'))

    return render_template('edit_parking_lot.html', lot=lot)





@admin_bp.route('/add_lot', methods=['GET', 'POST'])
@login_required
@admin_required
def add_lot():
    if request.method == 'POST':
        location_name = request.form['location_name']
        address = request.form['address']
        pincode = request.form['pincode']
        price = float(request.form['price'])
        total_slots = int(request.form['total_slots'])

        # Create new lot
        new_lot = ParkingLot(
            owner_id=current_user.id,
            location_name=location_name,
            address=address,
            pincode=pincode,
            price=price,
            total_slots=total_slots,
            available_slots=total_slots
        )
        db.session.add(new_lot)
        db.session.flush()  # Get the ID without committing

        # Add slots with independent numbering (1 to N for each lot)
        for i in range(1, total_slots + 1):
            spot = ParkingSpot(
                lot_id=new_lot.id,
                spot_number=f"S{i}",  # Always starts at 1 for each new lot
                is_available=True
            )
            db.session.add(spot)
        
        db.session.commit()
        flash("New parking lot added successfully!", "success")
        return redirect(url_for('admin.dashboard'))
    return render_template('new_parking_lot.html')
# @admin_bp.route('/delete_lot/<int:lot_id>')
# def delete_lot(lot_id):
#     lot = ParkingLot.query.get_or_404(lot_id)
    
#     # Delete associated parking spots first to maintain foreign key integrity
#     ParkingSpot.query.filter_by(lot_id=lot.id).delete()
    
#     db.session.delete(lot)
#     db.session.commit()
    
#     flash('Parking lot deleted successfully.', 'success')
#     return redirect(url_for('admin.dashboard'))

@admin_bp.route('/delete_lot/<int:lot_id>')
@login_required
@admin_required
def delete_lot(lot_id):
    lot = ParkingLot.query.get_or_404(lot_id)
    
    # Check if any spots are occupied
    occupied_spots = ParkingSpot.query.filter_by(lot_id=lot.id, is_available=False).count()
    if occupied_spots > 0:
        flash('Cannot delete parking lot - some spots are still occupied.', 'danger')
        return redirect(url_for('admin.dashboard'))

    # Check for any active bookings
    active_bookings = Booking.query.filter_by(lot_id=lot.id, status='active').count()
    if active_bookings > 0:
        flash('Cannot delete parking lot - there are active bookings.', 'danger')
        return redirect(url_for('admin.dashboard'))

    # Delete all bookings associated with this lot first
    Booking.query.filter_by(lot_id=lot.id).delete()
    
    # Now delete the lot (spots will be deleted due to cascade)
    db.session.delete(lot)
    db.session.commit()
    
    flash('Parking lot deleted successfully.', 'success')
    return redirect(url_for('admin.dashboard'))

@admin_bp.route('/admin/users')
@login_required
def view_users():
    users = User.query.all()
    return render_template('admin_users.html', users=users)   
        
        


@admin_bp.route('/search', methods=['GET'])
@login_required
@admin_required
def admin_search():
    query = request.args.get('query')
    filter_by = request.args.get('filter')

    parking_lots = []
    user_booked_spot_ids = set()
    user_booked_slots_per_lot = {}  # New dict to store counts
    lot_occupied_spots = {}
    if query and filter_by:
        if filter_by == 'location':
            parking_lots = ParkingLot.query.options(db.joinedload(ParkingLot.spots)).filter(
                ParkingLot.location_name.ilike(f"%{query.strip()}%")
            ).all()
            for lot in parking_lots:
                occupied_count = sum(not spot.is_available for spot in lot.spots)
                lot_occupied_spots[lot.id] = occupied_count  # Store per-lot occupancy

        elif filter_by == 'user':
            if query.isdigit():
                user = User.query.filter_by(id=int(query)).first()
                if user:
                    bookings = Booking.query.filter_by(user_id=user.id).all()
                    user_booked_spot_ids = set(str(b.spot_id) for b in bookings)
                    lot_ids = {b.lot_id for b in bookings}
                    parking_lots = ParkingLot.query.options(db.joinedload(ParkingLot.spots)).filter(ParkingLot.id.in_(lot_ids)).all()

                    # Count how many spots the user has booked per lot
                    for lot in parking_lots:
                        count = sum(1 for b in bookings if b.lot_id == lot.id)
                        user_booked_slots_per_lot[lot.id] = count

    return render_template(
        'admin_search.html',
        parking_lots=parking_lots,
        query=query,
        filter_by=filter_by,
        user_booked_spot_ids=user_booked_spot_ids,
        lot_occupied_spots=lot_occupied_spots,
        user_booked_slots_per_lot=user_booked_slots_per_lot  # Pass this to template
    )
# @admin_bp.route('/search', methods=['GET'])
# @login_required
# @admin_required
# def admin_search():
#     query = request.args.get('query')
#     filter_by = request.args.get('filter')

#     parking_lots = []
#     user_booked_spot_ids = set()
#     user_booked_slots_per_lot = {}
#     user_revenue_per_lot = {}
#     lot_occupied_spots = {}  # NEW: lot_id -> occupied count

#     if query and filter_by:
#         if filter_by == 'location':
#             parking_lots = ParkingLot.query.options(db.joinedload(ParkingLot.spots)).filter(
#                 ParkingLot.location_name.ilike(f"%{query.strip()}%")
#             ).all()

#             for lot in parking_lots:
#                 occupied_count = sum(not spot.is_available for spot in lot.spots)
#                 lot_occupied_spots[lot.id] = occupied_count  # Store per-lot occupancy

#         elif filter_by == 'user':
#             if query.isdigit():
#                 user = User.query.filter_by(id=int(query)).first()
#                 if user:
#                     bookings = Booking.query.filter_by(user_id=user.id).all()
#                     user_booked_spot_ids = set(str(b.spot_id) for b in bookings)
#                     lot_ids = {b.lot_id for b in bookings}
#                     parking_lots = ParkingLot.query.options(db.joinedload(ParkingLot.spots)).filter(ParkingLot.id.in_(lot_ids)).all()

#                     for lot in parking_lots:
#                         count = sum(1 for b in bookings if b.lot_id == lot.id)
#                         user_booked_slots_per_lot[lot.id] = count
#                         revenue = sum(b.price for b in bookings if b.lot_id == lot.id)
#                         user_revenue_per_lot[lot.id] = revenue

#     return render_template(
#         'admin_search.html',
#         parking_lots=parking_lots,
#         query=query,
#         filter_by=filter_by,
#         user_booked_spot_ids=user_booked_spot_ids,
#         user_booked_slots_per_lot=user_booked_slots_per_lot,
#         user_revenue_per_lot=user_revenue_per_lot,
#         lot_occupied_spots=lot_occupied_spots,
#         total_lots=len(parking_lots) if filter_by == 'location' else None  # for location searches
#     )



@admin_bp.route('/spot/<int:spot_id>')
@login_required
@admin_required
def view_spot(spot_id):
    spot = ParkingSpot.query.get_or_404(spot_id)

    booking = Booking.query.filter_by(spot_id=spot_id, status='active').first()
    user = User.query.get(booking.user_id) if booking else None

    duration_hours = 1
    total_cost = 0
    if booking:
        duration_hours = max(1, round((datetime.utcnow() - booking.timestamp).total_seconds() / 3600))
        total_cost = duration_hours * spot.lot.price

    return render_template(
        'view_parking.html' if spot.is_available else 'view_parking_occupied.html',
        spot=spot,
        booking=booking,
        user=user,
        duration_hours=duration_hours,
        total_cost=round(total_cost, 2)
    )





# @admin_bp.route('/delete_spot/<int:spot_id>', methods=['POST'])
# @login_required
# @admin_required
# def delete_spot(spot_id):
#     spot = ParkingSpot.query.get_or_404(spot_id)

#     if not spot.is_available:
#         flash('❌ Cannot delete an occupied spot.', 'danger')
#         return redirect(url_for('dashboard.view_spot', spot_id=spot_id))

#     lot = ParkingLot.query.get(spot.lot_id)
#     if lot:
#         lot.total_slots -= 1
#         # Also update available_slots
#         if spot.is_available:
#             lot.available_slots = ParkingSpot.query.filter_by(lot_id=lot.id, is_available=True).count()

#     db.session.delete(spot)
#     db.session.commit()

#     flash('✅ Spot deleted and lot updated successfully.', 'success')
#     return redirect(url_for('admin.dashboard'))

@admin_bp.route('/delete_spot/<int:spot_id>', methods=['POST'])
@login_required
@admin_required
def delete_spot(spot_id):
    spot = ParkingSpot.query.get_or_404(spot_id)

    if not spot.is_available:
        flash('❌ Cannot delete an occupied spot.', 'danger')
        return redirect(url_for('dashboard.view_spot', spot_id=spot_id))

    # Check for any active bookings related to this spot
    active_bookings = Booking.query.filter_by(spot_id=spot.id, status='active').count()
    if active_bookings > 0:
        flash('❌ Cannot delete this spot — active bookings exist.', 'danger')
        return redirect(url_for('dashboard.view_spot', spot_id=spot_id))

    # Delete all bookings associated with this spot
    Booking.query.filter_by(spot_id=spot.id).delete()

    # Update lot metadata
    lot = ParkingLot.query.get(spot.lot_id)
    if lot:
        lot.total_slots -= 1
        lot.available_slots = ParkingSpot.query.filter_by(lot_id=lot.id, is_available=True).count()

    db.session.delete(spot)
    db.session.commit()

    flash('✅ Spot and related bookings deleted successfully.', 'success')
    return redirect(url_for('admin.dashboard'))
