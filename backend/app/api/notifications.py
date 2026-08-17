from flask import Blueprint, request, jsonify, g
from app.core.deps import token_required, get_db
from app.models.models import Notification
from app.schemas.schemas import NotificationOut

notifications_bp = Blueprint("notifications", __name__, url_prefix="/notifications")

@notifications_bp.route("", methods=["GET"])
@token_required
def get_notifications():
    db = get_db()
    current_user = g.current_user
    skip = request.args.get("skip", default=0, type=int)
    limit = request.args.get("limit", default=50, type=int)

    notifs = db.query(Notification).filter(
        Notification.user_id == current_user.id
    ).order_by(Notification.created_at.desc()).offset(skip).limit(limit).all()

    results = [NotificationOut.model_validate(n).model_dump(mode="json") for n in notifs]
    return jsonify(results), 200

@notifications_bp.route("/unread-count", methods=["GET"])
@token_required
def get_unread_count():
    db = get_db()
    current_user = g.current_user

    count = db.query(Notification).filter(
        Notification.user_id == current_user.id,
        Notification.is_read == False
    ).count()
    return jsonify({"unread_count": count}), 200

@notifications_bp.route("/<notif_id>/read", methods=["POST"])
@token_required
def mark_notification_read(notif_id):
    db = get_db()
    current_user = g.current_user

    notif = db.query(Notification).filter(
        Notification.id == notif_id,
        Notification.user_id == current_user.id
    ).first()
    if not notif:
        return jsonify({"detail": "Notification not found"}), 404

    notif.is_read = True
    db.commit()
    return jsonify({"message": "Marked as read"}), 200

@notifications_bp.route("/read-all", methods=["POST"])
@token_required
def mark_all_notifications_read():
    db = get_db()
    current_user = g.current_user

    db.query(Notification).filter(
        Notification.user_id == current_user.id,
        Notification.is_read == False
    ).update({"is_read": True})
    db.commit()
    return jsonify({"message": "All notifications marked as read"}), 200
