import os
import shutil
from flask import Blueprint, request, jsonify, send_file, g
from app.core.config import settings
from app.core.deps import token_required, admin_required, get_db
from app.models.models import User, UserRole, Document, DocumentChunk, Notification
from app.schemas.schemas import DocumentOut
from app.services.pdf_service import pdf_service
from app.services.vector_service import vector_service
from app.utils.logger import log_audit_event

documents_bp = Blueprint("documents", __name__, url_prefix="/documents")

@documents_bp.route("", methods=["GET"])
@token_required
def get_documents():
    db = get_db()
    current_user = g.current_user
    skip = request.args.get("skip", default=0, type=int)
    limit = request.args.get("limit", default=100, type=int)

    from app.models.models import UserStudyPlanProgress, StudyPlanDay
    import json

    results = []

    # 1. Fetch all normal standalone repository documents (uploaded via Documents -> Upload)
    standalone_docs = db.query(Document).filter(
        (Document.is_study_plan_doc == False) | (Document.is_study_plan_doc == None)
    ).order_by(Document.created_at.desc()).all()

    for doc in standalone_docs:
        chunk_count = db.query(DocumentChunk).filter(DocumentChunk.document_id == doc.id).count()
        doc_data = DocumentOut(
            id=doc.id,
            title=doc.title,
            file_path=doc.file_path,
            file_size=doc.file_size,
            mime_type=doc.mime_type,
            uploaded_by=doc.uploaded_by,
            is_study_plan_doc=False,
            study_plan_day_id=None,
            created_at=doc.created_at,
            chunk_count=chunk_count
        ).model_dump(mode="json")
        results.append(doc_data)

    # 2. Gather completed Study Plan days specifically for current_user
    progress_records = db.query(UserStudyPlanProgress).filter(
        UserStudyPlanProgress.user_id == current_user.id
    ).all()
    completed_days_set = set()
    for p in progress_records:
        if p.completed_days_json:
            try:
                c_days = json.loads(p.completed_days_json)
                if isinstance(c_days, list):
                    completed_days_set.update(str(d) for d in c_days)
            except Exception:
                pass

    # 3. If current user has completed study plan days, include those completed day PDFs
    if completed_days_set:
        completed_days = db.query(StudyPlanDay).filter(
            StudyPlanDay.id.in_(completed_days_set),
            StudyPlanDay.pdf_file_path.isnot(None)
        ).all()

        for day in completed_days:
            if day.pdf_file_path:
                abs_path = os.path.abspath(day.pdf_file_path)
                file_size = os.path.getsize(abs_path) if os.path.exists(abs_path) else 0
                sp_doc_data = DocumentOut(
                    id=f"sp_doc_{day.id}",
                    title=day.pdf_title or day.lesson_title or f"Day {day.day_number} PDF",
                    file_path=day.pdf_file_path,
                    file_size=file_size,
                    mime_type="application/pdf",
                    uploaded_by=None,
                    is_study_plan_doc=True,
                    study_plan_day_id=str(day.id),
                    created_at=day.created_at,
                    chunk_count=1
                ).model_dump(mode="json")
                results.append(sp_doc_data)

    # Sort combined documents by created_at descending
    results.sort(key=lambda x: x.get("created_at") or "", reverse=True)
    paginated_results = results[skip:skip+limit]

    return jsonify(paginated_results), 200

@documents_bp.route("/upload", methods=["POST"])
@admin_required
def upload_document():
    db = get_db()
    admin = g.current_user

    title = request.form.get("title")
    file = request.files.get("file")

    if not title or not file:
        return jsonify({"detail": "title and file are required"}), 400

    if not file.filename.lower().endswith(".pdf"):
        return jsonify({"detail": "Only PDF files are allowed."}), 400

    # Ensure Upload Directory exists
    os.makedirs(settings.UPLOAD_DIR, exist_ok=True)

    file_name = f"{admin.id}_{file.filename}"
    file_path = os.path.abspath(os.path.join(settings.UPLOAD_DIR, file_name))
    file.save(file_path)

    file_size = os.path.getsize(file_path)

    # Store document metadata in database
    db_doc = Document(
        title=title,
        file_path=file_path,
        file_size=file_size,
        mime_type="application/pdf",
        uploaded_by=admin.id
    )
    db.add(db_doc)
    db.commit()
    db.refresh(db_doc)

    # Process PDF and extract chunks into ChromaDB and MySQL
    try:
        chunks_data = pdf_service.extract_text_with_metadata(file_path)
        vector_ids = vector_service.add_chunks(
            document_id=db_doc.id,
            document_title=db_doc.title,
            chunks=chunks_data
        )

        for idx, chunk_info in enumerate(chunks_data):
            vec_id = vector_ids[idx] if idx < len(vector_ids) else f"vec_{db_doc.id}_{idx}"
            db_chunk = DocumentChunk(
                document_id=db_doc.id,
                chunk_index=chunk_info["chunk_index"],
                page_number=chunk_info["page_number"],
                content=chunk_info["content"],
                vector_id=vec_id
            )
            db.add(db_chunk)
        db.commit()
    except Exception as e:
        print(f"Error processing PDF vector chunks: {e}")

    # Broadcast notification to all active users
    all_users = db.query(User).filter(User.is_active == True).all()
    for u in all_users:
        notif = Notification(
            user_id=u.id,
            title="New Document Uploaded",
            message=f"A new study document '{title}' has been uploaded to the repository.",
            type="DOC_UPLOAD"
        )
        db.add(notif)
    db.commit()

    log_audit_event(
        db, action="UPLOAD_DOCUMENT", entity_type="DOCUMENT", user_id=admin.id, entity_id=db_doc.id, details=f"Uploaded document {title}"
    )

    chunk_count = db.query(DocumentChunk).filter(DocumentChunk.document_id == db_doc.id).count()
    result_data = DocumentOut(
        id=db_doc.id,
        title=db_doc.title,
        file_path=db_doc.file_path,
        file_size=db_doc.file_size,
        mime_type=db_doc.mime_type,
        uploaded_by=db_doc.uploaded_by,
        created_at=db_doc.created_at,
        chunk_count=chunk_count
    ).model_dump(mode="json")
    return jsonify(result_data), 201

@documents_bp.route("/<doc_id>/rename", methods=["PUT"])
@admin_required
def rename_document(doc_id):
    db = get_db()
    admin = g.current_user
    data = request.get_json() or {}
    new_title = data.get("title")

    if not new_title:
        return jsonify({"detail": "title is required"}), 400

    doc = db.query(Document).filter(Document.id == doc_id).first()
    if not doc:
        return jsonify({"detail": "Document not found"}), 404

    doc.title = new_title
    db.commit()
    db.refresh(doc)

    log_audit_event(
        db, action="RENAME_DOCUMENT", entity_type="DOCUMENT", user_id=admin.id, entity_id=doc.id, details=f"Renamed document to {doc.title}"
    )

    chunk_count = db.query(DocumentChunk).filter(DocumentChunk.document_id == doc.id).count()
    result_data = DocumentOut(
        id=doc.id,
        title=doc.title,
        file_path=doc.file_path,
        file_size=doc.file_size,
        mime_type=doc.mime_type,
        uploaded_by=doc.uploaded_by,
        created_at=doc.created_at,
        chunk_count=chunk_count
    ).model_dump(mode="json")
    return jsonify(result_data), 200

@documents_bp.route("/<doc_id>", methods=["DELETE"])
@admin_required
def delete_document(doc_id):
    db = get_db()
    admin = g.current_user

    doc = db.query(Document).filter(Document.id == doc_id).first()
    if not doc:
        return jsonify({"detail": "Document not found"}), 404

    abs_path = os.path.abspath(doc.file_path)
    if os.path.exists(abs_path):
        try:
            os.remove(abs_path)
        except Exception:
            pass

    vector_service.delete_document_chunks(doc_id)

    db.delete(doc)
    db.commit()

    log_audit_event(
        db, action="DELETE_DOCUMENT", entity_type="DOCUMENT", user_id=admin.id, entity_id=doc_id, details=f"Deleted document {doc.title}"
    )
    return jsonify({"message": "Document deleted successfully"}), 200

@documents_bp.route("/<doc_id>/download", methods=["GET"])
@token_required
def download_document(doc_id):
    """
    Downloads original PDF file. Supports token in session cookie, header, or query param.
    Resolves absolute storage paths to prevent Flask 500 FileNotFoundError.
    Handles both standalone repository documents and unlocked Study Plan documents (sp_doc_<day_id>).
    """
    db = get_db()
    current_user = g.current_user

    from app.models.models import UserStudyPlanProgress, StudyPlanDay
    import json

    abs_path = None
    download_filename = "Document.pdf"

    if str(doc_id).startswith("sp_doc_") or db.query(StudyPlanDay).filter(StudyPlanDay.id == doc_id).first():
        day_id = str(doc_id).replace("sp_doc_", "")
        day = db.query(StudyPlanDay).filter(StudyPlanDay.id == day_id).first()
        if not day or not day.pdf_file_path:
            return jsonify({"detail": "Study Plan PDF document not found on server disk"}), 404

        # If student, verify completion
        if current_user.role == UserRole.STUDENT:
            progress_records = db.query(UserStudyPlanProgress).filter(
                UserStudyPlanProgress.user_id == current_user.id
            ).all()
            completed_days_set = set()
            for p in progress_records:
                if p.completed_days_json:
                    try:
                        c_days = json.loads(p.completed_days_json)
                        if isinstance(c_days, list):
                            completed_days_set.update(str(d) for d in c_days)
                    except Exception:
                        pass
            if str(day.id) not in completed_days_set:
                return jsonify({"detail": "This Study Plan document is locked. Mark the day as completed in your Study Plan to unlock it in your Documents section."}), 403

        abs_path = os.path.abspath(day.pdf_file_path)
        download_filename = (day.pdf_title or day.lesson_title or f"Day_{day.day_number}").strip()
    else:
        doc = db.query(Document).filter(Document.id == doc_id).first()
        if not doc:
            return jsonify({"detail": "Document record not found in database"}), 404
        abs_path = os.path.abspath(doc.file_path)
        download_filename = doc.title.strip()

    # Fallback search if stored path moved
    if not os.path.exists(abs_path):
        file_name = os.path.basename(abs_path)
        fallback_path = os.path.abspath(os.path.join(settings.UPLOAD_DIR, file_name))
        if os.path.exists(fallback_path):
            abs_path = fallback_path
        else:
            return jsonify({"detail": f"Physical document file '{file_name}' not found on server disk."}), 404

    log_audit_event(
        db, action="DOWNLOAD_DOCUMENT", entity_type="DOCUMENT", user_id=current_user.id, entity_id=str(doc_id)
    )

    if not download_filename.lower().endswith(".pdf"):
        download_filename = f"{download_filename}.pdf"

    return send_file(
        abs_path,
        as_attachment=True,
        download_name=download_filename,
        mimetype="application/pdf"
    )

@documents_bp.route("/<doc_id>/view", methods=["GET"])
@token_required
def view_document(doc_id):
    """
    Serves original PDF file inline with 'Content-Type: application/pdf'
    for native browser PDF rendering (zoom, pagination, scrolling, layout).
    Handles both standalone repository documents and unlocked Study Plan documents (sp_doc_<day_id>).
    """
    db = get_db()
    current_user = g.current_user

    from app.models.models import UserStudyPlanProgress, StudyPlanDay
    import json

    abs_path = None
    view_filename = "Document.pdf"

    if str(doc_id).startswith("sp_doc_") or db.query(StudyPlanDay).filter(StudyPlanDay.id == doc_id).first():
        day_id = str(doc_id).replace("sp_doc_", "")
        day = db.query(StudyPlanDay).filter(StudyPlanDay.id == day_id).first()
        if not day or not day.pdf_file_path:
            return jsonify({"detail": "Study Plan PDF document not found on server disk"}), 404

        # If student, verify completion
        if current_user.role == UserRole.STUDENT:
            progress_records = db.query(UserStudyPlanProgress).filter(
                UserStudyPlanProgress.user_id == current_user.id
            ).all()
            completed_days_set = set()
            for p in progress_records:
                if p.completed_days_json:
                    try:
                        c_days = json.loads(p.completed_days_json)
                        if isinstance(c_days, list):
                            completed_days_set.update(str(d) for d in c_days)
                    except Exception:
                        pass
            if str(day.id) not in completed_days_set:
                return jsonify({"detail": "This Study Plan document is locked. Mark the day as completed in your Study Plan to unlock it in your Documents section."}), 403

        abs_path = os.path.abspath(day.pdf_file_path)
        view_filename = (day.pdf_title or day.lesson_title or f"Day_{day.day_number}").strip()
    else:
        doc = db.query(Document).filter(Document.id == doc_id).first()
        if not doc:
            return jsonify({"detail": "Document record not found in database"}), 404
        abs_path = os.path.abspath(doc.file_path)
        view_filename = doc.title.strip()

    # Fallback search if stored path moved
    if not os.path.exists(abs_path):
        file_name = os.path.basename(abs_path)
        fallback_path = os.path.abspath(os.path.join(settings.UPLOAD_DIR, file_name))
        if os.path.exists(fallback_path):
            abs_path = fallback_path
        else:
            return jsonify({"detail": f"Physical document file '{file_name}' not found on server disk."}), 404

    log_audit_event(
        db, action="VIEW_DOCUMENT", entity_type="DOCUMENT", user_id=current_user.id, entity_id=str(doc_id)
    )

    if not view_filename.lower().endswith(".pdf"):
        view_filename = f"{view_filename}.pdf"

    response = send_file(
        abs_path,
        as_attachment=False,
        download_name=view_filename,
        mimetype="application/pdf"
    )
    response.headers["Content-Disposition"] = f'inline; filename="{view_filename}"'
    response.headers["Content-Type"] = "application/pdf"
    return response

