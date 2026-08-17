from flask import Blueprint, request, jsonify, g
from app.core.deps import token_required, admin_required, get_db
from app.models.models import User, Announcement, Notification
from app.schemas.schemas import AnnouncementOut
from app.utils.logger import log_audit_event

announcements_bp = Blueprint("announcements", __name__, url_prefix="/announcements")

@announcements_bp.route("", methods=["GET"])
@token_required
def get_announcements():
    db = get_db()
    current_user = g.current_user

    query = db.query(Announcement)
    if current_user.role != "ADMIN":
        query = query.filter(Announcement.is_published == True)

    announcements = query.order_by(Announcement.created_at.desc()).all()
    results = [AnnouncementOut.model_validate(a).model_dump(mode="json") for a in announcements]
    return jsonify(results), 200

@announcements_bp.route("", methods=["POST"])
@admin_required
def create_announcement():
    db = get_db()
    admin = g.current_user
    data = request.get_json() or {}

    title = data.get("title")
    content = data.get("content")
    source_document_name = data.get("source_document_name")
    is_published = data.get("is_published", True)

    if not title or not content:
        return jsonify({"detail": "title and content are required"}), 400

    db_ann = Announcement(
        title=title,
        content=content,
        source_document_name=source_document_name,
        is_published=is_published,
        created_by=admin.id
    )
    db.add(db_ann)
    db.commit()
    db.refresh(db_ann)

    if is_published:
        all_users = db.query(User).filter(User.is_active == True).all()
        for u in all_users:
            notif = Notification(
                user_id=u.id,
                title="New Announcement",
                message=title,
                type="ANNOUNCEMENT"
            )
            db.add(notif)
        db.commit()

    log_audit_event(
        db, action="CREATE_ANNOUNCEMENT", entity_type="ANNOUNCEMENT", user_id=admin.id, entity_id=db_ann.id, details=f"Title: {db_ann.title}"
    )

    result_data = AnnouncementOut.model_validate(db_ann).model_dump(mode="json")
    return jsonify(result_data), 201

@announcements_bp.route("/<ann_id>", methods=["PUT"])
@admin_required
def update_announcement(ann_id):
    db = get_db()
    admin = g.current_user
    data = request.get_json() or {}

    ann = db.query(Announcement).filter(Announcement.id == ann_id).first()
    if not ann:
        return jsonify({"detail": "Announcement not found"}), 404

    if "title" in data and data["title"] is not None:
        ann.title = data["title"]
    if "content" in data and data["content"] is not None:
        ann.content = data["content"]
    if "is_published" in data and data["is_published"] is not None:
        ann.is_published = data["is_published"]

    db.commit()
    db.refresh(ann)

    log_audit_event(
        db, action="UPDATE_ANNOUNCEMENT", entity_type="ANNOUNCEMENT", user_id=admin.id, entity_id=ann.id
    )
    result_data = AnnouncementOut.model_validate(ann).model_dump(mode="json")
    return jsonify(result_data), 200

@announcements_bp.route("/<ann_id>", methods=["DELETE"])
@admin_required
def delete_announcement(ann_id):
    db = get_db()
    admin = g.current_user

    ann = db.query(Announcement).filter(Announcement.id == ann_id).first()
    if not ann:
        return jsonify({"detail": "Announcement not found"}), 404

    db.delete(ann)
    db.commit()

    log_audit_event(
        db, action="DELETE_ANNOUNCEMENT", entity_type="ANNOUNCEMENT", user_id=admin.id, entity_id=ann_id
    )
    return jsonify({"message": "Announcement deleted successfully"}), 200
