import csv
import io
from datetime import datetime, timedelta

from flask import Blueprint, Response, flash, jsonify, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from models.models import (
    Booking,
    Invoice,
    ParkingLot,
    ParkingSpot,
    ScheduledBooking,
    SpotHold,
    SpotMaintenanceWindow,
    User,
    WaitlistEntry,
)
from .decorators import admin_required
from extensions import db
from services import (
    activate_due_scheduled_bookings,
    count_bookable_spots_for_lot,
    get_active_maintenance_map,
)


admin_bp = Blueprint('admin', __name__, url_prefix='/admin')


def _active_holds_count_for_lot(lot_id: int) -> int:
    now = datetime.utcnow()
    return SpotHold.query.filter(
        SpotHold.lot_id == lot_id,
        SpotHold.status == 'active',
        SpotHold.expires_at >= now,
    ).count()


def _cleanup_spot_dependents(spot_id: int) -> None:
    """Delete records that hold non-null references to a parking spot."""
    Booking.query.filter_by(spot_id=spot_id).delete(synchronize_session=False)
    SpotHold.query.filter_by(spot_id=spot_id).delete(synchronize_session=False)
    SpotMaintenanceWindow.query.filter_by(spot_id=spot_id).delete(synchronize_session=False)
    ScheduledBooking.query.filter_by(assigned_spot_id=spot_id).update(
        {'assigned_spot_id': None},
        synchronize_session=False,
    )


def _cleanup_lot_dependents(lot_id: int) -> None:
    """Delete/update records that hold non-null references to a parking lot."""
    Booking.query.filter_by(lot_id=lot_id).delete(synchronize_session=False)
    SpotHold.query.filter_by(lot_id=lot_id).delete(synchronize_session=False)
    SpotMaintenanceWindow.query.filter_by(lot_id=lot_id).delete(synchronize_session=False)
    WaitlistEntry.query.filter_by(lot_id=lot_id).delete(synchronize_session=False)
    ScheduledBooking.query.filter_by(lot_id=lot_id).delete(synchronize_session=False)


@admin_bp.route('/dashboard')
@login_required
@admin_required
def dashboard():
    activate_due_scheduled_bookings(limit=25)

    lots = ParkingLot.query.options(db.joinedload(ParkingLot.spots)).all()
    maintenance_map = get_active_maintenance_map()

    parking_lots = []
    for lot in lots:
        occupied_count = sum(1 for spot in lot.spots if not spot.is_available)
        maintenance_count = sum(1 for spot in lot.spots if spot.id in maintenance_map)
        held_count = _active_holds_count_for_lot(lot.id)
        bookable_count = count_bookable_spots_for_lot(lot.id)

        parking_lots.append(
            {
                'id': lot.id,
                'location_name': lot.location_name,
                'total_slots': lot.total_slots,
                'occupied_count': occupied_count,
                'maintenance_count': maintenance_count,
                'held_count': held_count,
                'bookable_count': bookable_count,
                'spots': lot.spots,
            }
        )

    return render_template('dashboard_admin.html', parking_lots=parking_lots)


@admin_bp.route('/edit_lot/<int:lot_id>', methods=['GET', 'POST'])
@login_required
@admin_required
def edit_lot(lot_id):
    lot = ParkingLot.query.get_or_404(lot_id)

    if request.method == 'POST':
        lot.location_name = request.form['location_name']
        lot.address = request.form['address']
        lot.pincode = request.form['pincode']
        lot.price = float(request.form['price'])
        desired_spots = int(request.form['total_slots'])

        existing_spots = ParkingSpot.query.filter_by(lot_id=lot.id).all()
        existing_labels = {str(spot.spot_number) for spot in existing_spots}
        current_spot_count = len(existing_labels)

        expected_labels = {f'S{i + 1}' for i in range(desired_spots)}
        missing_labels = sorted(expected_labels - existing_labels, key=lambda item: int(item[1:]))

        if desired_spots > current_spot_count:
            to_add = desired_spots - current_spot_count
            added = 0

            for label in missing_labels:
                if added >= to_add:
                    break
                db.session.add(ParkingSpot(lot_id=lot.id, spot_number=label, is_available=True))
                added += 1

            if added < to_add:
                existing_indexes = [int(str(label)[1:]) for label in existing_labels if str(label).startswith('S')]
                max_index = max(existing_indexes, default=0)

                while added < to_add:
                    max_index += 1
                    db.session.add(ParkingSpot(lot_id=lot.id, spot_number=f'S{max_index}', is_available=True))
                    added += 1

        elif desired_spots < current_spot_count:
            spots_to_remove = current_spot_count - desired_spots
            removable_spots = ParkingSpot.query.filter_by(
                lot_id=lot.id,
                is_available=True,
            ).order_by(ParkingSpot.id.desc()).all()

            if len(removable_spots) < spots_to_remove:
                flash('Cannot reduce total slots because not enough free spots are available.', 'danger')
                return redirect(request.url)

            remaining = spots_to_remove
            for spot in removable_spots:
                if remaining <= 0:
                    break
                _cleanup_spot_dependents(spot.id)
                db.session.delete(spot)
                remaining -= 1

        lot.total_slots = desired_spots
        lot.available_slots = count_bookable_spots_for_lot(lot.id)

        db.session.commit()
        flash('Parking lot updated successfully.', 'success')
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

        new_lot = ParkingLot(
            owner_id=current_user.id,
            location_name=location_name,
            address=address,
            pincode=pincode,
            price=price,
            total_slots=total_slots,
            available_slots=total_slots,
        )
        db.session.add(new_lot)
        db.session.flush()

        for i in range(1, total_slots + 1):
            db.session.add(
                ParkingSpot(
                    lot_id=new_lot.id,
                    spot_number=f'S{i}',
                    is_available=True,
                )
            )

        db.session.commit()
        flash('New parking lot added successfully.', 'success')
        return redirect(url_for('admin.dashboard'))

    return render_template('new_parking_lot.html')


@admin_bp.route('/delete_lot/<int:lot_id>')
@login_required
@admin_required
def delete_lot(lot_id):
    lot = ParkingLot.query.get_or_404(lot_id)

    occupied_spots = ParkingSpot.query.filter_by(lot_id=lot.id, is_available=False).count()
    if occupied_spots > 0:
        flash('Cannot delete parking lot: some spots are still occupied.', 'danger')
        return redirect(url_for('admin.dashboard'))

    active_bookings = Booking.query.filter_by(lot_id=lot.id, status='active').count()
    if active_bookings > 0:
        flash('Cannot delete parking lot: active bookings exist.', 'danger')
        return redirect(url_for('admin.dashboard'))

    _cleanup_lot_dependents(lot.id)

    db.session.delete(lot)
    db.session.commit()

    flash('Parking lot deleted successfully.', 'success')
    return redirect(url_for('admin.dashboard'))


@admin_bp.route('/admin/users')
@login_required
@admin_required
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
    user_booked_slots_per_lot = {}
    lot_occupied_spots = {}

    if query and filter_by:
        if filter_by == 'location':
            parking_lots = ParkingLot.query.options(db.joinedload(ParkingLot.spots)).filter(
                ParkingLot.location_name.ilike(f'%{query.strip()}%')
            ).all()
            for lot in parking_lots:
                lot_occupied_spots[lot.id] = sum(not spot.is_available for spot in lot.spots)

        elif filter_by == 'user':
            user = None
            if query.isdigit():
                user = User.query.filter_by(id=int(query)).first()
            else:
                user = User.query.filter(
                    (User.email.ilike(f'%{query.strip()}%'))
                    | (User.full_name.ilike(f'%{query.strip()}%'))
                ).first()

            if user:
                bookings = Booking.query.filter_by(user_id=user.id).all()
                user_booked_spot_ids = {str(item.spot_id) for item in bookings}
                lot_ids = {item.lot_id for item in bookings}
                parking_lots = ParkingLot.query.options(db.joinedload(ParkingLot.spots)).filter(
                    ParkingLot.id.in_(lot_ids)
                ).all()

                for lot in parking_lots:
                    user_booked_slots_per_lot[lot.id] = sum(1 for item in bookings if item.lot_id == lot.id)

    return render_template(
        'admin_search.html',
        parking_lots=parking_lots,
        query=query,
        filter_by=filter_by,
        user_booked_spot_ids=user_booked_spot_ids,
        lot_occupied_spots=lot_occupied_spots,
        user_booked_slots_per_lot=user_booked_slots_per_lot,
    )


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

    active_maintenance = SpotMaintenanceWindow.query.filter_by(spot_id=spot.id, is_active=True).order_by(
        SpotMaintenanceWindow.starts_at.desc()
    ).first()

    return render_template(
        'view_parking.html',
        spot=spot,
        booking=booking,
        user=user,
        duration_hours=duration_hours,
        total_cost=round(total_cost, 2),
        active_maintenance=active_maintenance,
    )


@admin_bp.route('/delete_spot/<int:spot_id>', methods=['POST'])
@login_required
@admin_required
def delete_spot(spot_id):
    spot = ParkingSpot.query.get_or_404(spot_id)

    if not spot.is_available:
        flash('Cannot delete an occupied spot.', 'danger')
        return redirect(url_for('admin.view_spot', spot_id=spot_id))

    active_bookings = Booking.query.filter_by(spot_id=spot.id, status='active').count()
    if active_bookings > 0:
        flash('Cannot delete this spot: active bookings exist.', 'danger')
        return redirect(url_for('admin.view_spot', spot_id=spot_id))

    _cleanup_spot_dependents(spot.id)

    lot = ParkingLot.query.get(spot.lot_id)
    if lot:
        lot.total_slots -= 1

    db.session.delete(spot)
    if lot:
        lot.available_slots = count_bookable_spots_for_lot(lot.id)

    db.session.commit()

    flash('Spot and related data removed successfully.', 'success')
    return redirect(url_for('admin.dashboard'))


@admin_bp.route('/spot/<int:spot_id>/maintenance/start', methods=['POST'])
@login_required
@admin_required
def start_spot_maintenance(spot_id):
    spot = ParkingSpot.query.get_or_404(spot_id)
    reason = request.form.get('reason', '').strip() or 'Routine maintenance'

    if not spot.is_available:
        flash('Cannot start maintenance on an occupied spot.', 'danger')
        return redirect(url_for('admin.view_spot', spot_id=spot_id))

    existing = SpotMaintenanceWindow.query.filter_by(spot_id=spot_id, is_active=True).first()
    if existing:
        flash('Maintenance is already active for this spot.', 'info')
        return redirect(url_for('admin.view_spot', spot_id=spot_id))

    maintenance = SpotMaintenanceWindow(
        spot_id=spot.id,
        lot_id=spot.lot_id,
        reason=reason,
        is_active=True,
        created_by=current_user.id,
    )
    db.session.add(maintenance)

    lot = ParkingLot.query.get(spot.lot_id)
    if lot:
        lot.available_slots = count_bookable_spots_for_lot(lot.id)

    db.session.commit()
    flash('Spot set to maintenance mode.', 'success')
    return redirect(url_for('admin.view_spot', spot_id=spot_id))


@admin_bp.route('/spot/<int:spot_id>/maintenance/stop', methods=['POST'])
@login_required
@admin_required
def stop_spot_maintenance(spot_id):
    maintenance = SpotMaintenanceWindow.query.filter_by(spot_id=spot_id, is_active=True).order_by(
        SpotMaintenanceWindow.starts_at.desc()
    ).first()

    if not maintenance:
        flash('No active maintenance window found.', 'info')
        return redirect(url_for('admin.view_spot', spot_id=spot_id))

    maintenance.is_active = False
    maintenance.ends_at = datetime.utcnow()

    lot = ParkingLot.query.get(maintenance.lot_id)
    if lot:
        lot.available_slots = count_bookable_spots_for_lot(lot.id)

    db.session.commit()
    flash('Maintenance mode ended for this spot.', 'success')
    return redirect(url_for('admin.view_spot', spot_id=spot_id))


@admin_bp.route('/export/bookings.csv')
@login_required
@admin_required
def export_bookings_csv():
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['Booking ID', 'User Email', 'Lot', 'Spot', 'Vehicle', 'Status', 'Start', 'Release', 'Cost'])

    records = Booking.query.order_by(Booking.timestamp.desc()).all()
    for item in records:
        writer.writerow(
            [
                item.id,
                item.user.email if item.user else '',
                item.parking_lot.location_name if item.parking_lot else '',
                item.parking_spot.spot_number if item.parking_spot else '',
                item.vehicle_no,
                item.status,
                item.timestamp.isoformat() if item.timestamp else '',
                item.release_time.isoformat() if item.release_time else '',
                item.cost if item.cost is not None else '',
            ]
        )

    response = Response(output.getvalue(), mimetype='text/csv')
    response.headers['Content-Disposition'] = 'attachment; filename=bookings_export.csv'
    return response


@admin_bp.route('/export/invoices.csv')
@login_required
@admin_required
def export_invoices_csv():
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['Invoice No', 'Booking ID', 'User Email', 'Amount', 'Currency', 'Status', 'Issued At', 'Paid At'])

    records = Invoice.query.order_by(Invoice.issued_at.desc()).all()
    for item in records:
        writer.writerow(
            [
                item.invoice_no,
                item.booking_id,
                item.user.email if item.user else '',
                item.amount,
                item.currency,
                item.status,
                item.issued_at.isoformat() if item.issued_at else '',
                item.paid_at.isoformat() if item.paid_at else '',
            ]
        )

    response = Response(output.getvalue(), mimetype='text/csv')
    response.headers['Content-Disposition'] = 'attachment; filename=invoices_export.csv'
    return response


@admin_bp.route('/analytics/hourly_data')
@login_required
@admin_required
def analytics_hourly_data():
    start_window = datetime.utcnow() - timedelta(days=7)
    bookings = Booking.query.filter(Booking.timestamp >= start_window).all()

    hourly = {f'{hour:02d}:00': 0 for hour in range(24)}
    for booking in bookings:
        if booking.timestamp:
            label = f'{booking.timestamp.hour:02d}:00'
            hourly[label] += 1

    payload = [{'hour': key, 'count': value} for key, value in hourly.items()]
    return jsonify(payload)


@admin_bp.route('/analytics/top_lots_data')
@login_required
@admin_required
def analytics_top_lots_data():
    lots = ParkingLot.query.options(db.joinedload(ParkingLot.bookings)).all()
    rows = []

    for lot in lots:
        total_bookings = len(lot.bookings)
        revenue = sum((booking.cost or lot.price) for booking in lot.bookings)
        rows.append(
            {
                'lot': lot.location_name,
                'bookings': total_bookings,
                'revenue': round(revenue, 2),
            }
        )

    rows.sort(key=lambda item: item['bookings'], reverse=True)
    return jsonify(rows[:10])
