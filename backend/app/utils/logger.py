import logging
from sqlalchemy.orm import Session
from app.models.models import AuditLog

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)

logger = logging.getLogger("talent_sphere")

def log_audit_event(
    db: Session,
    action: str,
    entity_type: str,
    user_id: str = None,
    entity_id: str = None,
    details: str = None,
    ip_address: str = None
):
    try:
        log_entry = AuditLog(
            user_id=user_id,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            details=details,
            ip_address=ip_address
        )
        db.add(log_entry)
        db.commit()
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to record audit log: {e}")
