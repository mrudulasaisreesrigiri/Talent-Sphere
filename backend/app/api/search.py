from flask import Blueprint, request, jsonify, g
from app.core.deps import token_required, get_db
from app.models.models import Document, UserRole, UserStudyPlanProgress, StudyPlanDay
from app.schemas.schemas import KnowledgeSearchResult
from app.services.vector_service import vector_service
import json

search_bp = Blueprint("search", __name__, url_prefix="/search")

@search_bp.route("", methods=["GET"])
@token_required
def knowledge_search():
    db = get_db()
    current_user = g.current_user
    query_str = request.args.get("q", default="", type=str)
    top_k = request.args.get("top_k", default=6, type=int)

    if not query_str or len(query_str) < 2:
        return jsonify([]), 200

    results = vector_service.search_similar(query=query_str, top_k=top_k * 2)

    # If user is a student, gather completed study plan day IDs
    completed_days_set = set()
    if current_user.role == UserRole.STUDENT:
        progress_records = db.query(UserStudyPlanProgress).filter(
            UserStudyPlanProgress.user_id == current_user.id
        ).all()
        for p in progress_records:
            if p.completed_days_json:
                try:
                    c_days = json.loads(p.completed_days_json)
                    if isinstance(c_days, list):
                        completed_days_set.update(str(d) for d in c_days)
                except Exception:
                    pass

    study_plan_days = db.query(StudyPlanDay).all()
    sp_day_by_doc_id = {str(d.document_id): d for d in study_plan_days if d.document_id}
    study_day_map = {str(d.id): d for d in study_plan_days}

    search_output = []
    for r in results:
        doc_id = str(r.get("document_id") or "")
        doc_title = r.get("document_title") or "Document"

        if current_user.role == UserRole.STUDENT:
            matched_day = None
            if doc_id.startswith("sp_day_"):
                raw_day_id = doc_id.replace("sp_day_", "")
                matched_day = study_day_map.get(raw_day_id)
            elif doc_id in sp_day_by_doc_id:
                matched_day = sp_day_by_doc_id[doc_id]
            elif r.get("day_id") and str(r.get("day_id")) in study_day_map:
                matched_day = study_day_map[str(r.get("day_id"))]

            if matched_day and str(matched_day.id) not in completed_days_set:
                # Locked study plan PDF chunk -> skip for student
                continue

        if doc_id and not doc_title:
            doc = db.query(Document).filter(Document.id == doc_id).first()
            if doc:
                doc_title = doc.title

        res_item = KnowledgeSearchResult(
            document_id=doc_id or "unknown",
            document_title=doc_title,
            page_number=r.get("page_number", 1),
            content=r.get("content", ""),
            score=r.get("score", 0.0)
        ).model_dump(mode="json")
        search_output.append(res_item)
        if len(search_output) >= top_k:
            break

    return jsonify(search_output), 200
