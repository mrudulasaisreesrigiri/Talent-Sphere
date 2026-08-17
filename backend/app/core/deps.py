from functools import wraps
from flask import request, jsonify, g
from app.core.database import SessionLocal
from app.core.security import decode_access_token
from app.models.models import User, UserRole

def get_db():
    if 'db' not in g:
        g.db = SessionLocal()
    return g.db

def close_db(e=None):
    db = g.pop('db', None)
    if db is not None:
        db.close()

def get_current_user():
    auth_header = request.headers.get("Authorization", "")
    token = None
    if auth_header.startswith("Bearer "):
        token = auth_header.split(" ", 1)[1]
    else:
        token = request.cookies.get("access_token") or request.args.get("access_token") or request.args.get("token")

    if not token:
        return None, (jsonify({"detail": "Could not validate credentials"}), 401)
    
    payload = decode_access_token(token)
    if payload is None:
        return None, (jsonify({"detail": "Could not validate credentials"}), 401)
    
    user_id = payload.get("sub")
    if not user_id:
        return None, (jsonify({"detail": "Could not validate credentials"}), 401)
    
    db = get_db()
    user = db.query(User).filter(User.id == user_id).first()
    if not user or not user.is_active:
        return None, (jsonify({"detail": "User not found or inactive"}), 401)
    
    return user, None

def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        user, err = get_current_user()
        if err:
            return err
        g.current_user = user
        return f(*args, **kwargs)
    return decorated

def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        user, err = get_current_user()
        if err:
            return err
        if user.role != UserRole.ADMIN:
            return jsonify({"detail": "Operation restricted to Administrators only"}), 403
        g.current_user = user
        return f(*args, **kwargs)
    return decorated
