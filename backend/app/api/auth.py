import logging
from flask import Blueprint, request, jsonify, g
from sqlalchemy import func
from app.core.database import SessionLocal
from app.core.security import verify_password, create_access_token, get_password_hash
from app.core.deps import token_required, get_db
from app.models.models import User, UserRole
from app.schemas.schemas import UserOut
from app.utils.logger import log_audit_event

logger = logging.getLogger(__name__)

auth_bp = Blueprint("auth", __name__, url_prefix="/auth")

@auth_bp.route("/login", methods=["POST"])
def login_access_token():
    db = get_db()
    
    # Safely extract payload from JSON or Form Data
    data = request.get_json(silent=True) or request.form or {}
    username = data.get("username") or data.get("email")
    password = data.get("password")

    if not username or not password:
        logger.warning("Login failed: Missing username or password in payload.")
        return jsonify({"detail": "Incorrect email or password"}), 401

    clean_email = str(username).strip().lower()
    clean_password = str(password).strip()

    user = db.query(User).filter(func.lower(User.email) == clean_email).first()
    if not user:
        logger.warning(f"Login failed: User email '{clean_email}' not found in database.")
        return jsonify({"detail": "Incorrect email or password"}), 401

    # Verify password against hash
    if not verify_password(clean_password, user.password_hash):
        logger.warning(f"Login failed: Invalid password for user '{clean_email}'.")
        return jsonify({"detail": "Incorrect email or password"}), 401
    
    if not user.is_active:
        logger.warning(f"Login failed: User '{clean_email}' is deactivated.")
        return jsonify({"detail": "Account is deactivated. Contact Administrator."}), 400

    role_str = user.role.value if hasattr(user.role, 'value') else str(user.role)
    access_token = create_access_token(subject=user.id, role=role_str)
    logger.info(f"User '{clean_email}' (Role: {role_str}) logged in successfully.")

    log_audit_event(db, action="USER_LOGIN", entity_type="USER", user_id=user.id, entity_id=user.id)

    user_data = UserOut.model_validate(user).model_dump(mode="json")
    
    response = jsonify({
        "access_token": access_token,
        "token_type": "bearer",
        "user": user_data
    })
    response.set_cookie("access_token", access_token, max_age=86400, path="/", samesite="Lax")
    return response, 200

@auth_bp.route("/me", methods=["GET"])
@token_required
def read_user_me():
    user = g.current_user
    user_data = UserOut.model_validate(user).model_dump(mode="json")
    return jsonify(user_data), 200

@auth_bp.route("/change-password", methods=["POST"])
@token_required
def change_password():
    db = get_db()
    current_user = g.current_user
    data = request.get_json(silent=True) or request.form or {}
    new_password = data.get("new_password")
    
    if not new_password:
        return jsonify({"detail": "new_password is required"}), 400

    db_user = db.query(User).filter(User.id == current_user.id).first()
    db_user.password_hash = get_password_hash(new_password)
    db.commit()

    logger.info(f"Password changed successfully for user ID '{current_user.id}'.")
    log_audit_event(db, action="CHANGE_PASSWORD", entity_type="USER", user_id=current_user.id, entity_id=current_user.id)
    return jsonify({"message": "Password changed successfully"}), 200
