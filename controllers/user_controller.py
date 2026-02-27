from datetime import datetime, timedelta

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from extensions import db
from models.models import (
    Booking,
    Invoice,
    NotificationLog,
    ParkingLot,
    ParkingSpot,
    ScheduledBooking,
    Vehicle,
    WaitlistEntry,
)
from services import (
    activate_due_scheduled_bookings,
    add_to_waitlist,
    count_bookable_spots_for_lot,
    create_or_refresh_spot_hold,
    create_vehicle_for_user,
    fulfill_waitlist_for_lot,
    generate_invoice_for_release,
    get_active_hold_for_user,
    get_active_maintenance_map,
    get_bookable_spot,
    get_user_vehicle_choices,
    log_notification,
    parse_schedule_datetime,
)


user_bp = Blueprint('user', __name__)


def _normalize_vehicle_no(raw_value: str) -> str:
    return ''.join((raw_value or '').upper().split())


@user_bp.route('/book/<int:lot_id>', methods=['GET', 'POST'])
@login_required
def book_parking_lot(lot_id):
    activate_due_scheduled_bookings(limit=10)
    lot = ParkingLot.query.get_or_404(lot_id)

    vehicles = get_user_vehicle_choices(current_user.id)
    selected_vehicle_id = request.form.get('vehicle_id', type=int)
    selected_vehicle = None

    if selected_vehicle_id:
        selected_vehicle = Vehicle.query.filter_by(
            id=selected_vehicle_id,
            user_id=current_user.id,
            is_active=True,
        ).first()

    if request.method == 'POST':
        action = request.form.get('action', 'book')
        booking_type = request.form.get('booking_type', 'immediate')
        duration_hours = max(1, request.form.get('duration_hours', type=int) or 1)

        vehicle_no = _normalize_vehicle_no(
            request.form.get('vehicle_number') or (selected_vehicle.plate_number if selected_vehicle else '')
        )

        if not vehicle_no:
            flash('Please provide a vehicle number or choose a saved vehicle.', 'danger')
            return redirect(request.url)

        if action == 'waitlist':
            waitlist_entry, created = add_to_waitlist(
                user_id=current_user.id,
                lot_id=lot.id,
                vehicle_no=vehicle_no,
                vehicle_id=selected_vehicle.id if selected_vehicle else None,
            )
            if created:
                log_notification(
                    user_id=current_user.id,
                    notification_type='waitlist_joined',
                    subject='Added to Waitlist',
                    message=f'You were added to waitlist for {lot.location_name}.',
                )
                flash('Lot is full. You were added to waitlist.', 'info')
            else:
                flash('You are already in waitlist for this lot.', 'info')
            return redirect(url_for('dashboard.user_dashboard'))

        if booking_type == 'scheduled':
            scheduled_start = parse_schedule_datetime(request.form.get('scheduled_start', ''))
            if not scheduled_start:
                flash('Please choose a valid future start time for scheduled booking.', 'danger')
                return redirect(request.url)

            if scheduled_start <= datetime.utcnow() + timedelta(minutes=5):
                flash('Scheduled start time must be at least 5 minutes in the future.', 'danger')
                return redirect(request.url)

            scheduled_booking = ScheduledBooking(
                user_id=current_user.id,
                lot_id=lot.id,
                vehicle_id=selected_vehicle.id if selected_vehicle else None,
                vehicle_no=vehicle_no,
                requested_start=scheduled_start,
                duration_hours=duration_hours,
                status='scheduled',
            )
            db.session.add(scheduled_booking)
            db.session.commit()

            log_notification(
                user_id=current_user.id,
                notification_type='scheduled_booking_created',
                subject='Scheduled Booking Created',
                message=(
                    f'Your booking at {lot.location_name} is scheduled for '
                    f"{scheduled_start.strftime('%Y-%m-%d %H:%M')}"
                ),
            )
            log_notification(
                user_id=current_user.id,
                notification_type='scheduled_booking_created_email',
                subject='Parking Booking Scheduled',
                message=(
                    f'Booking confirmed at {lot.location_name} for '
                    f"{scheduled_start.strftime('%Y-%m-%d %H:%M')}"
                ),
                channel='email',
            )

            flash('Scheduled booking created successfully.', 'success')
            return redirect(url_for('dashboard.user_dashboard'))

        active_hold = get_active_hold_for_user(current_user.id, lot.id)
        if not active_hold:
            flash('Your spot hold expired. Please try again.', 'warning')
            return redirect(request.url)

        spot = ParkingSpot.query.get(active_hold.spot_id)
        maintenance_map = get_active_maintenance_map(lot.id)

        if not spot or not spot.is_available or spot.id in maintenance_map:
            active_hold.status = 'expired'
            db.session.commit()
            flash('That spot is no longer available. Try again to lock another spot.', 'warning')
            return redirect(request.url)

        booking = Booking(
            user_id=current_user.id,
            lot_id=lot.id,
            spot_id=spot.id,
            vehicle_no=vehicle_no,
            status='active',
        )

        active_hold.status = 'converted'
        spot.is_available = False
        lot.available_slots = count_bookable_spots_for_lot(lot.id)

        db.session.add(booking)
        db.session.commit()

        log_notification(
            user_id=current_user.id,
            notification_type='booking_confirmed',
            subject='Booking Confirmed',
            message=f'Parking spot {spot.spot_number} at {lot.location_name} is now active.',
        )
        log_notification(
            user_id=current_user.id,
            notification_type='booking_confirmed_email',
            subject='Parking Booking Confirmed',
            message=f'You booked spot {spot.spot_number} at {lot.location_name}.',
            channel='email',
        )

        flash(f'Parking spot {spot.spot_number} booked successfully!', 'success')
        return redirect(url_for('dashboard.user_dashboard'))

    active_hold = get_active_hold_for_user(current_user.id, lot.id)
    locked_spot = None

    if active_hold:
        locked_spot = ParkingSpot.query.get(active_hold.spot_id)

    if not active_hold or not locked_spot:
        bookable_spot = get_bookable_spot(lot.id, current_user.id)
        if bookable_spot:
            active_hold = create_or_refresh_spot_hold(
                user_id=current_user.id,
                lot_id=lot.id,
                spot_id=bookable_spot.id,
            )
            locked_spot = bookable_spot

    hold_seconds_remaining = 0
    if active_hold and active_hold.expires_at:
        hold_seconds_remaining = max(0, int((active_hold.expires_at - datetime.utcnow()).total_seconds()))

    return render_template(
        'book.html',
        lot=lot,
        spot=locked_spot,
        hold=active_hold,
        hold_seconds_remaining=hold_seconds_remaining,
        vehicles=vehicles,
        now=datetime.utcnow(),
    )


@user_bp.route('/user/release/<int:booking_id>', methods=['GET', 'POST'])
@login_required
def release_booking(booking_id):
    booking = Booking.query.get_or_404(booking_id)

    if booking.user_id != current_user.id:
        flash('Unauthorized action!', 'danger')
        return redirect(url_for('dashboard.user_dashboard'))

    spot = ParkingSpot.query.get(booking.spot_id)
    if not spot:
        flash('Parking spot not found.', 'danger')
        return redirect(url_for('dashboard.user_dashboard'))

    if request.method == 'GET':
        release_time = datetime.utcnow()
        duration_hours = max(1, round((release_time - booking.timestamp).total_seconds() / 3600))
        total_cost = duration_hours * spot.lot.price

        return render_template(
            'release.html',
            booking=booking,
            spot=spot,
            release_time=release_time,
            duration_hours=duration_hours,
            total_cost=round(total_cost, 2),
        )

    if booking.status != 'active':
        flash('This booking is already released.', 'info')
        return redirect(url_for('dashboard.user_dashboard'))

    release_time = datetime.utcnow()
    duration_hours = max(1, round((release_time - booking.timestamp).total_seconds() / 3600))
    total_cost = duration_hours * spot.lot.price

    booking.status = 'released'
    booking.release_time = release_time
    booking.cost = total_cost

    spot.is_available = True
    spot.lot.available_slots = count_bookable_spots_for_lot(spot.lot_id)

    db.session.commit()

    invoice = generate_invoice_for_release(booking, total_cost)

    log_notification(
        user_id=current_user.id,
        notification_type='release_success',
        subject='Parking Released',
        message=(
            f'Booking #{booking.id} released successfully. '
            f'Invoice {invoice.invoice_no} generated for INR {invoice.amount:.2f}.'
        ),
    )
    log_notification(
        user_id=current_user.id,
        notification_type='release_success_email',
        subject='Parking Release Receipt',
        message=(
            f'Release completed for booking #{booking.id}. '
            f'Invoice: {invoice.invoice_no}, Amount: INR {invoice.amount:.2f}.'
        ),
        channel='email',
    )

    _, waitlist_booking = fulfill_waitlist_for_lot(booking.lot_id)

    flash_message = (
        f'Release completed. Invoice {invoice.invoice_no} paid for INR {invoice.amount:.2f}.'
    )
    if waitlist_booking:
        flash_message += ' A waitlisted user was auto-assigned this lot.'

    flash(flash_message, 'success')
    return redirect(url_for('dashboard.user_dashboard'))


@user_bp.route('/user/vehicles', methods=['GET', 'POST'])
@login_required
def manage_vehicles():
    if request.method == 'POST':
        plate_number = request.form.get('plate_number', '').strip()
        label = request.form.get('label', '').strip() or None
        set_default = request.form.get('is_default') == 'on'

        if not plate_number:
            flash('Vehicle number is required.', 'danger')
            return redirect(request.url)

        _, created = create_vehicle_for_user(
            user_id=current_user.id,
            plate_number=plate_number,
            label=label,
            set_default=set_default,
        )

        if created:
            flash('Vehicle added successfully.', 'success')
        else:
            flash('Vehicle already exists in your profile.', 'info')

        return redirect(request.url)

    vehicles = get_user_vehicle_choices(current_user.id)
    return render_template('vehicles.html', vehicles=vehicles)


@user_bp.route('/user/vehicles/<int:vehicle_id>/set-default', methods=['POST'])
@login_required
def set_default_vehicle(vehicle_id):
    vehicle = Vehicle.query.filter_by(
        id=vehicle_id,
        user_id=current_user.id,
        is_active=True,
    ).first_or_404()

    Vehicle.query.filter_by(user_id=current_user.id).update({'is_default': False})
    vehicle.is_default = True
    db.session.commit()

    flash('Default vehicle updated.', 'success')
    return redirect(url_for('user.manage_vehicles'))


@user_bp.route('/user/vehicles/<int:vehicle_id>/delete', methods=['POST'])
@login_required
def delete_vehicle(vehicle_id):
    vehicle = Vehicle.query.filter_by(
        id=vehicle_id,
        user_id=current_user.id,
        is_active=True,
    ).first_or_404()

    vehicle.is_active = False
    vehicle.is_default = False

    fallback_default = Vehicle.query.filter_by(
        user_id=current_user.id,
        is_active=True,
    ).order_by(Vehicle.created_at.asc()).first()

    if fallback_default:
        fallback_default.is_default = True

    db.session.commit()
    flash('Vehicle removed.', 'info')
    return redirect(url_for('user.manage_vehicles'))


@user_bp.route('/user/waitlist/<int:entry_id>/cancel', methods=['POST'])
@login_required
def cancel_waitlist(entry_id):
    entry = WaitlistEntry.query.filter_by(id=entry_id, user_id=current_user.id).first_or_404()
    if entry.status != 'waiting':
        flash('Only waiting entries can be cancelled.', 'warning')
        return redirect(url_for('dashboard.user_dashboard'))

    entry.status = 'cancelled'
    db.session.commit()
    flash('Waitlist entry cancelled.', 'info')
    return redirect(url_for('dashboard.user_dashboard'))


@user_bp.route('/user/invoices')
@login_required
def invoice_history():
    invoices = Invoice.query.filter_by(user_id=current_user.id).order_by(Invoice.issued_at.desc()).all()
    return render_template('invoice_history.html', invoices=invoices)


@user_bp.route('/user/notifications')
@login_required
def notifications():
    items = NotificationLog.query.filter_by(user_id=current_user.id).order_by(NotificationLog.created_at.desc()).limit(200).all()
    return render_template('notifications.html', notifications=items)
