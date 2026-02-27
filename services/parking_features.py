import os
import secrets
import smtplib
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage
from typing import Optional, Tuple

from sqlalchemy import or_

from extensions import db
from models.models import (
    Booking,
    Invoice,
    NotificationLog,
    ParkingLot,
    ParkingSpot,
    ScheduledBooking,
    SpotHold,
    SpotMaintenanceWindow,
    User,
    Vehicle,
    WaitlistEntry,
)

HOLD_DURATION_MINUTES = 5
WAITLIST_LOOKAHEAD_HOURS = 24


def utcnow() -> datetime:
    return datetime.utcnow()


def parse_schedule_datetime(raw_value: str) -> Optional[datetime]:
    if not raw_value:
        return None

    try:
        parsed = datetime.fromisoformat(raw_value)
    except ValueError:
        return None

    if parsed.tzinfo is not None:
        parsed = parsed.astimezone(timezone.utc).replace(tzinfo=None)

    return parsed


def cleanup_expired_spot_holds() -> int:
    now = utcnow()
    expired = SpotHold.query.filter(
        SpotHold.status == 'active',
        SpotHold.expires_at < now,
    ).all()

    for hold in expired:
        hold.status = 'expired'

    if expired:
        db.session.flush()

    return len(expired)


def get_active_hold_for_user(user_id: int, lot_id: int) -> Optional[SpotHold]:
    cleanup_expired_spot_holds()
    now = utcnow()
    return SpotHold.query.filter(
        SpotHold.user_id == user_id,
        SpotHold.lot_id == lot_id,
        SpotHold.status == 'active',
        SpotHold.expires_at >= now,
    ).order_by(SpotHold.created_at.desc()).first()


def get_active_maintenance_map(lot_id: Optional[int] = None):
    now = utcnow()
    query = SpotMaintenanceWindow.query.filter(
        SpotMaintenanceWindow.is_active.is_(True),
        or_(
            SpotMaintenanceWindow.ends_at.is_(None),
            SpotMaintenanceWindow.ends_at > now,
        ),
    )

    if lot_id is not None:
        query = query.filter(SpotMaintenanceWindow.lot_id == lot_id)

    return {item.spot_id: item for item in query.all()}


def get_bookable_spot(lot_id: int, user_id: Optional[int] = None) -> Optional[ParkingSpot]:
    cleanup_expired_spot_holds()

    now = utcnow()
    active_holds = SpotHold.query.filter(
        SpotHold.lot_id == lot_id,
        SpotHold.status == 'active',
        SpotHold.expires_at >= now,
    ).all()
    active_holds_by_spot = {hold.spot_id: hold for hold in active_holds}
    maintenance_map = get_active_maintenance_map(lot_id)

    candidate_spots = ParkingSpot.query.filter_by(
        lot_id=lot_id,
        is_available=True,
    ).order_by(ParkingSpot.spot_number.asc()).all()

    for spot in candidate_spots:
        if spot.id in maintenance_map:
            continue

        hold = active_holds_by_spot.get(spot.id)
        if hold and hold.user_id != user_id:
            continue

        return spot

    return None


def count_bookable_spots_for_lot(lot_id: int, user_id: Optional[int] = None) -> int:
    cleanup_expired_spot_holds()

    now = utcnow()
    active_holds = SpotHold.query.filter(
        SpotHold.lot_id == lot_id,
        SpotHold.status == 'active',
        SpotHold.expires_at >= now,
    ).all()
    active_holds_by_spot = {hold.spot_id: hold for hold in active_holds}
    maintenance_map = get_active_maintenance_map(lot_id)

    count = 0
    candidate_spots = ParkingSpot.query.filter_by(
        lot_id=lot_id,
        is_available=True,
    ).all()

    for spot in candidate_spots:
        if spot.id in maintenance_map:
            continue
        hold = active_holds_by_spot.get(spot.id)
        if hold and hold.user_id != user_id:
            continue
        count += 1

    return count


def create_or_refresh_spot_hold(
    user_id: int,
    lot_id: int,
    spot_id: int,
    duration_minutes: int = HOLD_DURATION_MINUTES,
) -> SpotHold:
    now = utcnow()
    expires_at = now + timedelta(minutes=duration_minutes)

    existing_hold = SpotHold.query.filter(
        SpotHold.user_id == user_id,
        SpotHold.lot_id == lot_id,
        SpotHold.status == 'active',
        SpotHold.expires_at >= now,
    ).order_by(SpotHold.created_at.desc()).first()

    if existing_hold:
        if existing_hold.spot_id == spot_id:
            existing_hold.expires_at = expires_at
            db.session.commit()
            return existing_hold

        existing_hold.status = 'cancelled'

    hold = SpotHold(
        user_id=user_id,
        lot_id=lot_id,
        spot_id=spot_id,
        status='active',
        created_at=now,
        expires_at=expires_at,
    )
    db.session.add(hold)
    db.session.commit()
    return hold


def create_vehicle_for_user(
    user_id: int,
    plate_number: str,
    label: Optional[str] = None,
    set_default: bool = False,
) -> Tuple[Vehicle, bool]:
    normalized_plate = ''.join(plate_number.upper().split())
    existing = Vehicle.query.filter_by(
        user_id=user_id,
        plate_number=normalized_plate,
        is_active=True,
    ).first()

    if existing:
        return existing, False

    if set_default:
        Vehicle.query.filter_by(user_id=user_id).update({'is_default': False})

    vehicle = Vehicle(
        user_id=user_id,
        plate_number=normalized_plate,
        label=label,
        is_default=set_default,
    )
    db.session.add(vehicle)
    db.session.commit()
    return vehicle, True


def get_user_vehicle_choices(user_id: int):
    return Vehicle.query.filter_by(user_id=user_id, is_active=True).order_by(
        Vehicle.is_default.desc(),
        Vehicle.created_at.asc(),
    ).all()


def add_to_waitlist(
    user_id: int,
    lot_id: int,
    vehicle_no: str,
    vehicle_id: Optional[int] = None,
    requested_start: Optional[datetime] = None,
    requested_duration_hours: int = 1,
    auto_commit: bool = True,
) -> Tuple[WaitlistEntry, bool]:
    normalized_vehicle = ''.join(vehicle_no.upper().split())

    existing = WaitlistEntry.query.filter_by(
        user_id=user_id,
        lot_id=lot_id,
        status='waiting',
    ).first()

    if existing:
        return existing, False

    entry = WaitlistEntry(
        user_id=user_id,
        lot_id=lot_id,
        vehicle_id=vehicle_id,
        vehicle_no=normalized_vehicle,
        requested_start=requested_start,
        requested_duration_hours=max(1, requested_duration_hours),
        status='waiting',
    )
    db.session.add(entry)

    if auto_commit:
        db.session.commit()

    return entry, True


def _try_send_email(to_email: str, subject: str, body: str) -> Tuple[bool, str]:
    smtp_host = os.environ.get('SMTP_HOST')
    smtp_port = int(os.environ.get('SMTP_PORT', '587'))
    smtp_username = os.environ.get('SMTP_USERNAME')
    smtp_password = os.environ.get('SMTP_PASSWORD')
    smtp_from = os.environ.get('SMTP_FROM', smtp_username or 'no-reply@parking.local')
    smtp_use_tls = os.environ.get('SMTP_USE_TLS', 'true').lower() in ('1', 'true', 'yes')

    if not smtp_host:
        return False, 'SMTP is not configured'

    message = EmailMessage()
    message['Subject'] = subject
    message['From'] = smtp_from
    message['To'] = to_email
    message.set_content(body)

    try:
        with smtplib.SMTP(smtp_host, smtp_port, timeout=10) as server:
            if smtp_use_tls:
                server.starttls()
            if smtp_username and smtp_password:
                server.login(smtp_username, smtp_password)
            server.send_message(message)
    except Exception as exc:  # pragma: no cover - external dependency
        return False, str(exc)

    return True, 'sent'


def log_notification(
    user_id: int,
    notification_type: str,
    message: str,
    subject: Optional[str] = None,
    channel: str = 'in_app',
    auto_commit: bool = True,
) -> NotificationLog:
    now = utcnow()
    notification = NotificationLog(
        user_id=user_id,
        channel=channel,
        notification_type=notification_type,
        subject=subject,
        message=message,
        status='queued',
        created_at=now,
    )
    db.session.add(notification)

    if channel == 'email':
        user = User.query.get(user_id)
        if user:
            sent, info = _try_send_email(
                to_email=user.email,
                subject=subject or 'Parking App Notification',
                body=message,
            )
            if sent:
                notification.status = 'sent'
                notification.sent_at = now
            else:
                notification.status = 'failed'
                notification.error_message = info
        else:
            notification.status = 'failed'
            notification.error_message = 'User not found'
    elif channel == 'sms':
        notification.status = 'queued'
        notification.error_message = 'SMS provider not configured'
    else:
        notification.status = 'sent'
        notification.sent_at = now

    if auto_commit:
        db.session.commit()

    return notification


def generate_invoice_for_release(booking: Booking, total_cost: float) -> Invoice:
    now = utcnow()
    invoice_no = f"INV-{now.strftime('%Y%m%d')}-{booking.id}-{secrets.token_hex(2).upper()}"
    payment_ref = f"PAY-{secrets.token_hex(6).upper()}"

    invoice = Invoice(
        booking_id=booking.id,
        user_id=booking.user_id,
        invoice_no=invoice_no,
        amount=round(float(total_cost), 2),
        currency='INR',
        status='paid',
        payment_ref=payment_ref,
        issued_at=now,
        paid_at=now,
    )
    db.session.add(invoice)
    db.session.commit()
    return invoice


def fulfill_waitlist_for_lot(lot_id: int):
    entry = WaitlistEntry.query.filter_by(
        lot_id=lot_id,
        status='waiting',
    ).order_by(WaitlistEntry.created_at.asc()).first()

    if not entry:
        return None, None

    spot = get_bookable_spot(lot_id=lot_id, user_id=entry.user_id)
    if not spot:
        return entry, None

    now = utcnow()
    spot.is_available = False

    booking = Booking(
        user_id=entry.user_id,
        lot_id=entry.lot_id,
        spot_id=spot.id,
        vehicle_no=entry.vehicle_no,
        status='active',
        timestamp=now,
    )
    db.session.add(booking)
    lot = ParkingLot.query.get(lot_id)
    if lot:
        lot.available_slots = count_bookable_spots_for_lot(lot_id)

    entry.status = 'fulfilled'
    entry.fulfilled_at = now
    entry.notified_at = now

    db.session.flush()
    log_notification(
        user_id=entry.user_id,
        notification_type='waitlist_fulfilled',
        subject='Spot Assigned from Waitlist',
        message=f'Parking spot {spot.spot_number} in {spot.lot.location_name} is now assigned to you.',
        auto_commit=False,
    )
    db.session.commit()

    return entry, booking


def activate_due_scheduled_bookings(limit: int = 20):
    now = utcnow()
    due_entries = ScheduledBooking.query.filter(
        ScheduledBooking.status == 'scheduled',
        ScheduledBooking.requested_start <= now,
    ).order_by(ScheduledBooking.requested_start.asc()).limit(limit).all()

    converted = []
    deferred = []

    for scheduled in due_entries:
        spot = get_bookable_spot(scheduled.lot_id, scheduled.user_id)
        if not spot:
            add_to_waitlist(
                user_id=scheduled.user_id,
                lot_id=scheduled.lot_id,
                vehicle_no=scheduled.vehicle_no,
                vehicle_id=scheduled.vehicle_id,
                requested_start=scheduled.requested_start,
                requested_duration_hours=scheduled.duration_hours,
                auto_commit=False,
            )
            scheduled.status = 'missed'
            deferred.append(scheduled)
            log_notification(
                user_id=scheduled.user_id,
                notification_type='scheduled_booking_deferred',
                subject='Scheduled Booking Deferred',
                message='Your scheduled booking could not start on time and was moved to waitlist.',
                auto_commit=False,
            )
            continue

        spot.is_available = False
        booking = Booking(
            user_id=scheduled.user_id,
            lot_id=scheduled.lot_id,
            spot_id=spot.id,
            vehicle_no=scheduled.vehicle_no,
            status='active',
            timestamp=scheduled.requested_start,
        )
        db.session.add(booking)
        db.session.flush()
        lot = ParkingLot.query.get(scheduled.lot_id)
        if lot:
            lot.available_slots = count_bookable_spots_for_lot(scheduled.lot_id)

        scheduled.status = 'converted'
        scheduled.assigned_spot_id = spot.id
        scheduled.converted_booking_id = booking.id
        converted.append(scheduled)

        log_notification(
            user_id=scheduled.user_id,
            notification_type='scheduled_booking_started',
            subject='Scheduled Booking Started',
            message=f'Your scheduled booking is now active at {scheduled.lot.location_name}, spot {spot.spot_number}.',
            auto_commit=False,
        )

    if due_entries:
        db.session.commit()

    return converted, deferred
