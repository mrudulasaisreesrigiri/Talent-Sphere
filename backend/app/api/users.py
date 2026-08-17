from flask import Blueprint, request, jsonify, g
from app.core.deps import admin_required, get_db
from app.core.security import get_password_hash
from app.models.models import User, UserRole
from app.schemas.schemas import UserOut
from app.utils.logger import log_audit_event
from app.services.email_service import email_service

users_bp = Blueprint("users", __name__, url_prefix="/users")

@users_bp.route("", methods=["GET"])
@admin_required
def get_users():
    db = get_db()
    skip = request.args.get("skip", default=0, type=int)
    limit = request.args.get("limit", default=100, type=int)
    search = request.args.get("search", default=None, type=str)
    role_param = request.args.get("role", default=None, type=str)

    query = db.query(User)
    if search:
        query = query.filter((User.full_name.ilike(f"%{search}%")) | (User.email.ilike(f"%{search}%")))
    if role_param:
        query = query.filter(User.role == role_param)

    users = query.order_by(User.created_at.desc()).offset(skip).limit(limit).all()
    user_list = [UserOut.model_validate(u).model_dump(mode="json") for u in users]
    return jsonify(user_list), 200

@users_bp.route("", methods=["POST"])
@admin_required
def create_user():
    db = get_db()
    admin = g.current_user
    data = request.get_json() or {}

    email = data.get("email")
    full_name = data.get("full_name")
    password = data.get("password")
    role_str = data.get("role", "STUDENT")
    is_active = data.get("is_active", True)

    if not email or not full_name or not password:
        return jsonify({"detail": "email, full_name, and password are required"}), 400

    existing_user = db.query(User).filter(User.email == email).first()
    if existing_user:
        return jsonify({"detail": "A user with this email address already exists"}), 400

    db_user = User(
        email=email,
        full_name=full_name,
        password_hash=get_password_hash(password),
        role=UserRole(role_str) if hasattr(UserRole, role_str) else UserRole.STUDENT,
        is_active=is_active
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)

    log_audit_event(
        db, action="CREATE_USER", entity_type="USER", user_id=admin.id, entity_id=db_user.id,
        details=f"Created user {db_user.email} with role {db_user.role}"
    )

    user_data = UserOut.model_validate(db_user).model_dump(mode="json")
    return jsonify(user_data), 201

@users_bp.route("/<user_id>", methods=["PUT"])
@admin_required
def update_user(user_id):
    db = get_db()
    admin = g.current_user
    data = request.get_json() or {}

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        return jsonify({"detail": "User not found"}), 404

    if "full_name" in data and data["full_name"] is not None:
        user.full_name = data["full_name"]
    if "email" in data and data["email"] is not None:
        user.email = data["email"]
    if "role" in data and data["role"] is not None:
        user.role = UserRole(data["role"]) if hasattr(UserRole, data["role"]) else user.role
    if "is_active" in data and data["is_active"] is not None:
        user.is_active = data["is_active"]

    db.commit()
    db.refresh(user)

    log_audit_event(
        db, action="UPDATE_USER", entity_type="USER", user_id=admin.id, entity_id=user.id, details=f"Updated user {user.email}"
    )

    user_data = UserOut.model_validate(user).model_dump(mode="json")
    return jsonify(user_data), 200

@users_bp.route("/<user_id>", methods=["DELETE"])
@admin_required
def delete_user(user_id):
    db = get_db()
    admin = g.current_user

    if user_id == admin.id:
        return jsonify({"detail": "Cannot delete your own admin account"}), 400

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        return jsonify({"detail": "User not found"}), 404

    db.delete(user)
    db.commit()

    log_audit_event(
        db, action="DELETE_USER", entity_type="USER", user_id=admin.id, entity_id=user_id, details=f"Deleted user {user.email}"
    )
    return jsonify({"message": "User deleted successfully"}), 200

@users_bp.route("/<user_id>/reset-password", methods=["POST"])
@admin_required
def admin_reset_password(user_id):
    db = get_db()
    admin = g.current_user
    data = request.get_json() or {}
    new_password = data.get("new_password")

    if not new_password:
        return jsonify({"detail": "new_password is required"}), 400

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        return jsonify({"detail": "User not found"}), 404

    user.password_hash = get_password_hash(new_password)
    db.commit()

    log_audit_event(
        db, action="RESET_USER_PASSWORD", entity_type="USER", user_id=admin.id, entity_id=user.id, details=f"Reset password for {user.email}"
    )
    return jsonify({"message": "User password reset successfully"}), 200

@users_bp.route("/<user_id>/send-credentials", methods=["POST"])
@admin_required
def send_user_credentials(user_id):
    """
    Sends the welcome login credentials email to the specified user.
    Admin supplies initial_password.
    """
    db = get_db()
    admin = g.current_user
    data = request.get_json() or {}
    initial_password = data.get("initial_password") or data.get("password")

    if not initial_password:
        return jsonify({"detail": "initial_password is required to send login credentials email"}), 400

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        return jsonify({"detail": "User not found"}), 404

    # Send the credentials email via EmailService
    success, msg = email_service.send_user_credentials_email(
        to_email=user.email,
        user_name=user.full_name,
        initial_password=initial_password
    )

    if not success:
        return jsonify({"detail": msg}), 500

    log_audit_event(
        db,
        action="SEND_CREDENTIALS_EMAIL",
        entity_type="USER",
        user_id=admin.id,
        entity_id=user.id,
        details=f"Sent login credentials email to {user.email}"
    )

    return jsonify({"message": f"Login credentials sent successfully to {user.email}."}), 200
