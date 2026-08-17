from flask import Blueprint, request, jsonify, g
from app.core.deps import admin_required, get_db
from app.models.models import User, Document, DocumentChunk, Exam, Question, Announcement, Notification, ExamStatus
from app.services.groq_service import groq_service
from app.utils.logger import log_audit_event

ai_commands_bp = Blueprint("ai_commands", __name__, url_prefix="/ai-commands")

@ai_commands_bp.route("/execute", methods=["POST"])
@admin_required
def execute_ai_command():
    db = get_db()
    admin = g.current_user
    data = request.get_json() or {}

    command_str = data.get("command", "").strip()
    doc_name = data.get("document_name")

    if not command_str:
        return jsonify({"detail": "command is required"}), 400

    def find_target_document(name_query: str) -> Document:
        doc = db.query(Document).filter(Document.title.ilike(f"%{name_query}%")).first()
        if not doc:
            doc = db.query(Document).filter(Document.file_path.ilike(f"%{name_query}%")).first()
        return doc

    if "create exam" in command_str.lower():
        if not doc_name:
            parts = command_str.lower().split("from")
            if len(parts) > 1:
                doc_name = parts[1].strip()

        if not doc_name:
            return jsonify({"detail": "Please specify a document name for exam generation."}), 400

        target_doc = find_target_document(doc_name)
        if not target_doc:
            return jsonify({"detail": f"Document matching '{doc_name}' not found in repository."}), 404

        chunks = db.query(DocumentChunk).filter(DocumentChunk.document_id == target_doc.id).order_by(DocumentChunk.chunk_index.asc()).all()
        doc_text = "\n".join([c.content for c in chunks]) or f"Content of document {target_doc.title}"

        exam_data = groq_service.generate_exam_from_document(
            document_title=target_doc.title,
            document_text=doc_text
        )

        db_exam = Exam(
            title=exam_data.get("title", f"Exam: {target_doc.title}"),
            description=exam_data.get("description", f"AI Generated from {target_doc.title}"),
            duration_minutes=exam_data.get("duration_minutes", 30),
            passing_score=exam_data.get("passing_score", 70.0),
            status=ExamStatus.DRAFT,
            source_document_name=target_doc.title,
            created_by=admin.id
        )
        db.add(db_exam)
        db.commit()
        db.refresh(db_exam)

        questions = exam_data.get("questions", [])
        for q in questions:
            db_q = Question(
                exam_id=db_exam.id,
                question_type=q.get("question_type", "MCQ"),
                question_text=q.get("question_text", "Sample Question"),
                option_a=q.get("option_a"),
                option_b=q.get("option_b"),
                option_c=q.get("option_c"),
                option_d=q.get("option_d"),
                correct_option=str(q.get("correct_option", "A")),
                explanation=q.get("explanation"),
                points=float(q.get("points", 1.0))
            )
            db.add(db_q)
        db.commit()

        log_audit_event(
            db, action="AI_CREATE_EXAM", entity_type="EXAM", user_id=admin.id, entity_id=db_exam.id,
            details=f"Generated exam from PDF {target_doc.title}"
        )

        return jsonify({
            "status": "success",
            "message": f"Exam '{db_exam.title}' generated successfully with {len(questions)} questions.",
            "entity_type": "EXAM",
            "entity_id": db_exam.id
        }), 200

    elif "create announcement" in command_str.lower():
        if not doc_name:
            parts = command_str.lower().split("from")
            if len(parts) > 1:
                doc_name = parts[1].strip()

        if not doc_name:
            return jsonify({"detail": "Please specify a document name for announcement generation."}), 400

        target_doc = find_target_document(doc_name)
        if not target_doc:
            return jsonify({"detail": f"Document matching '{doc_name}' not found in repository."}), 404

        chunks = db.query(DocumentChunk).filter(DocumentChunk.document_id == target_doc.id).order_by(DocumentChunk.chunk_index.asc()).all()
        doc_text = "\n".join([c.content for c in chunks]) or f"Content of document {target_doc.title}"

        ann_data = groq_service.generate_announcement_from_document(
            document_title=target_doc.title,
            document_text=doc_text
        )

        db_ann = Announcement(
            title=ann_data.get("title", f"Announcement: {target_doc.title}"),
            content=ann_data.get("content", f"Key updates from {target_doc.title}"),
            source_document_name=target_doc.title,
            is_published=True,
            created_by=admin.id
        )
        db.add(db_ann)
        db.commit()
        db.refresh(db_ann)

        all_users = db.query(User).filter(User.is_active == True).all()
        for u in all_users:
            notif = Notification(
                user_id=u.id,
                title="AI Announcement Released",
                message=db_ann.title,
                type="ANNOUNCEMENT"
            )
            db.add(notif)
        db.commit()

        log_audit_event(
            db, action="AI_CREATE_ANNOUNCEMENT", entity_type="ANNOUNCEMENT", user_id=admin.id, entity_id=db_ann.id
        )

        return jsonify({
            "status": "success",
            "message": f"Announcement '{db_ann.title}' created and broadcasted successfully.",
            "entity_type": "ANNOUNCEMENT",
            "entity_id": db_ann.id
        }), 200

    else:
        return jsonify({
            "detail": "Unrecognized AI command. Supported: 'Create Exam from <PDF Name>' or 'Create Announcement from <PDF Name>'"
        }), 400
