from flask import Blueprint, render_template, redirect, url_for,request, flash
from flask_login import login_required, logout_user, current_user
from models.models import ParkingLot, ParkingSpot, Booking, User
from extensions import db
from datetime import datetime
from werkzeug.security import check_password_hash, generate_password_hash
dashboard_bp = Blueprint('dashboard', __name__)  # name MUST match 'dashboard'


#for user
@dashboard_bp.route('/user/dashboard')
@login_required
def user_dashboard():
    bookings = Booking.query.filter_by(user_id=current_user.id).order_by(Booking.timestamp.desc()).all()
    lots = ParkingLot.query.options(db.joinedload(ParkingLot.spots)).all()
    return render_template('dashboard_user.html', parking_lots=lots, bookings=bookings)  # make sure this file exists!

@dashboard_bp.route('/user/book/<int:lot_id>')
@login_required
def show_booking_form(lot_id):
    lot = ParkingLot.query.get_or_404(lot_id)
    return render_template('book.html', lot=lot)

@dashboard_bp.route('/user/release')
@login_required
def show_release_form():
    return render_template('release.html')
    
# @dashboard_bp.route('/user/summary')
# @login_required
# def user_summary():
#     lots = ParkingLot.query.all()
    
#     summary_data = []
#     for lot in lots:
#         used_spots = sum(1 for spot in lot.spots if not spot.is_available)
#         summary_data.append({
#             'name': lot.location_name,
#             'used': used_spots
#         })

#     return render_template('summary.html', summary=summary_data)

@dashboard_bp.route('/user/summary')
@login_required
def user_summary():
    return render_template('summary.html')


# for admin
# Removed - admin dashboard now handled by admin_controller.py
# @dashboard_bp.route('/admin/dashboard')
# @login_required
# def admin_dashboard():
#     lots = ParkingLot.query.options(db.joinedload(ParkingLot.spots)).all()
#     # Add a new property dynamically for each lot: occupied_slots
#     for lot in lots:
#         lot.occupied_slots = sum(not spot.is_available for spot in lot.spots)
    
#     return render_template('dashboard_admin.html', parking_lots = lots)  # make sure this file exists!

# admin users
@dashboard_bp.route('/admin/users')
@login_required
def users():
    return render_template('admin_users.html')


# # admin search 
# @dashboard_bp.route('/admin/search')
# @login_required
# def search():
#     return render_template('admin_search.html')

# admin summary
@dashboard_bp.route('/admin/summary')
@login_required
def admin_summary():
    return render_template('admin_summary.html')

@dashboard_bp.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('auth.login'))

@dashboard_bp.route('/admin/view_spot/<int:spot_id>')
@login_required
def view_spot(spot_id):
    booking = Booking.query.filter_by(spot_id=spot_id, status='active').first()
    user = User.query.get(booking.user_id) if booking else None
    spot = ParkingSpot.query.get_or_404(spot_id)
    
    total_cost = 0
    duration_hours = 0
    no_booking = booking is None

    if booking and spot and spot.lot:
        release_time = datetime.utcnow()
        duration_hours = max(1, round((release_time - booking.timestamp).total_seconds() / 3600))
        cost_per_hour = spot.lot.price
        total_cost = duration_hours * cost_per_hour

    return render_template(
        'view_parking.html',
        spot=spot,
        booking=booking,
        user=user,
        total_cost=round(total_cost, 2),
        duration_hours=duration_hours,
        no_booking=no_booking,
        disable_delete=not no_booking  # Disable delete if there's an active booking
    )
    
    
    
    
# Edit profile part common in both admin and user:
# @dashboard_bp.route('/edit-profile', methods=['GET', 'POST'])
# @login_required
# def edit_profile():
#     if request.method == 'POST':
#         full_name = request.form.get('full_name')
#         address = request.form.get('address')
#         pincode = request.form.get('pincode')

#         current_user.full_name = full_name
#         current_user.address = address
#         current_user.pincode = pincode

#         db.session.commit()
#         flash('Profile updated successfully!', 'success')
#         # Redirect to user or admin dashboard based on role
#         if current_user.is_admin:
#             return redirect(url_for('dashboard.admin_dashboard'))
#         else:
#             return redirect(url_for('dashboard.user_dashboard'))

#     return render_template('edit_profile.html')


# @dashboard_bp.route('/edit-profile', methods=['GET', 'POST'])
# @login_required
# def edit_profile():
#     if request.method == 'POST':
#         full_name = request.form.get('full_name')
#         address = request.form.get('address')
#         pincode = request.form.get('pincode')
#         new_email = request.form.get('email')
#         old_password = request.form.get('old_password')
#         new_password = request.form.get('new_password')

#         # ✅ Check old password before allowing sensitive changes
#         if not check_password_hash(current_user.password, old_password):
#             flash('Incorrect old password. Cannot update email or password.', 'danger')
#             return redirect(url_for('dashboard.edit_profile'))

#         # ✅ Update profile fields
#         current_user.full_name = full_name
#         current_user.address = address
#         current_user.pincode = pincode
#         current_user.email = new_email  # Update email

#         # ✅ Update password only if new one is provided
#         if new_password:
#             current_user.password = generate_password_hash(new_password)

#         db.session.commit()
#         flash('Profile updated successfully!', 'success')

#         # Redirect to appropriate dashboard
        
#         if current_user.role == 'admin':
#             return redirect(url_for('dashboard.admin_dashboard'))
#         else:
#             return redirect(url_for('dashboard.user_dashboard'))

#     return render_template('edit_profile.html')




@dashboard_bp.route('/edit-profile', methods=['GET', 'POST'])
@login_required
def edit_profile():
    if request.method == 'POST':
        try:
            full_name = request.form.get('full_name')
            address = request.form.get('address')
            pincode = request.form.get('pincode')
            new_email = request.form.get('email')
            old_password = request.form.get('old_password')
            new_password = request.form.get('new_password')

            with db.session.no_autoflush:
                user = db.session.get(User, current_user.id)

                if not user.check_password(old_password):
                    flash('Incorrect old password. Cannot update email or password.', 'danger')
                    return redirect(url_for('dashboard.edit_profile'))

                # Update only if values are actually changed
                if full_name != user.full_name:
                    user.full_name = full_name

                if address != user.address:
                    user.address = address

                if pincode != user.pincode:
                    user.pincode = pincode

                if new_email != user.email:
                    user.email = new_email

                if new_password.strip():
                    user.set_password(new_password)

                db.session.commit()
                flash('Profile updated successfully!', 'success')

                return redirect(url_for('dashboard.admin_dashboard' if user.role == 'admin' else 'dashboard.user_dashboard'))

        except Exception as e:
            db.session.rollback()
            # current_app.logger.error(f"Error updating profile: {e}")
            flash("An error occurred while updating your profile. Please try again.", "danger")
            return redirect(url_for('dashboard.edit_profile'))

    return render_template('edit_profile.html')




