from flask import Blueprint, request, jsonify
from app.core.deps import admin_required, get_db
from app.models.models import AuditLog
from app.schemas.schemas import AuditLogOut

audit_logs_bp = Blueprint("audit_logs", __name__, url_prefix="/audit-logs")

@audit_logs_bp.route("", methods=["GET"])
@admin_required
def get_audit_logs():
    db = get_db()
    skip = request.args.get("skip", default=0, type=int)
    limit = request.args.get("limit", default=100, type=int)

    logs = db.query(AuditLog).order_by(AuditLog.timestamp.desc()).offset(skip).limit(limit).all()
    results = [AuditLogOut.model_validate(l).model_dump(mode="json") for l in logs]
    return jsonify(results), 200
