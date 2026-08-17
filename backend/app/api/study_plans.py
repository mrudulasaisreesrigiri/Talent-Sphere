import os
import logging
import json
import pypdf
from werkzeug.utils import secure_filename
from flask import Blueprint, request, jsonify, send_file, g
from app.core.config import settings
from app.core.deps import token_required, admin_required, get_db
from app.models.models import (
    StudyPlan, StudyPlanWeek, StudyPlanDay, UserRole, UserStudyPlanProgress,
    Document, DocumentChunk, Exam, Question
)
from app.schemas.schemas import StudyPlanOut, StudyPlanDayOut
from app.services.pdf_service import pdf_service
from app.services.vector_service import vector_service
from app.utils.logger import log_audit_event

logger = logging.getLogger(__name__)

study_plans_bp = Blueprint("study_plans", __name__, url_prefix="/study-plans")

def get_pdf_page_count(file_path: str) -> int:
    """Calculate the total number of pages from a physical PDF file."""
    try:
        if file_path and os.path.exists(file_path):
            reader = pypdf.PdfReader(file_path)
            return len(reader.pages)
    except Exception as e:
        logger.warning(f"Could not read PDF page count from {file_path}: {e}")
    return 0

def save_study_plan_day_pdf(day: StudyPlanDay, file_obj, pdf_title: str, admin_id: str, db):
    """
    Saves an uploaded PDF specifically as a Study Plan Day document.
    Stores physical PDF file, extracts text, updates StudyPlanDay record,
    and indexes content in ChromaDB for study plan lessons.
    DOES NOT register this PDF in the general documents repository.
    """
    if not file_obj or not pdf_title:
        return None

    os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
    orig_name = secure_filename(file_obj.filename) or f"day_{day.day_number}.pdf"
    if not orig_name.lower().endswith(".pdf"):
        orig_name = f"{orig_name}.pdf"

    unique_filename = f"study_day_{day.id}_{orig_name}"
    file_path = os.path.abspath(os.path.join(settings.UPLOAD_DIR, unique_filename))
    file_obj.save(file_path)

    # Extract text page-by-page and chunk data
    try:
        chunks_data = pdf_service.extract_text_with_metadata(file_path)
    except Exception as pe:
        logger.error(f"Error extracting text from PDF {file_path}: {pe}")
        chunks_data = []

    extracted_text = "\n\n".join([c["content"] for c in chunks_data if c.get("content")])
    if not extracted_text.strip():
        extracted_text = f"Study Plan Lesson Material: {pdf_title}"

    # Update StudyPlanDay fields directly without creating a general Document row
    day.pdf_title = pdf_title.strip()
    day.lesson_title = pdf_title.strip()
    day.pdf_file_path = file_path
    day.pdf_extracted_text = extracted_text
    day.lesson_content = extracted_text
    day.document_id = None
    db.commit()
    db.refresh(day)

    # Embed lesson into study plan vector namespace for AI exam generation and RAG
    week = day.week
    plan = week.plan if week else None
    if week and plan:
        try:
            vector_service.add_study_plan_lesson_vector(
                plan_id=plan.id,
                week_id=week.id,
                day_id=day.id,
                day_number=day.day_number,
                lesson_title=day.pdf_title,
                lesson_content=day.pdf_extracted_text
            )
        except Exception as ve:
            logger.error(f"Error embedding lesson into ChromaDB: {ve}")

    return day

@study_plans_bp.route("", methods=["GET"])
@token_required
def get_study_plans():
    """
    Get all study plans with nested 6-Week and 6-Day breakdown.
    Visible to both Admin and Students.
    """
    db = get_db()
    plans = db.query(StudyPlan).order_by(StudyPlan.created_at.desc()).all()
    results = [StudyPlanOut.model_validate(p).model_dump(mode="json") for p in plans]
    return jsonify(results), 200

@study_plans_bp.route("", methods=["POST"])
@admin_required
def create_study_plan():
    """
    Create a new study plan with Day 1–Day 4 PDF document uploads.
    Automatically generates 6 Weeks and 6 Days per week.
    Extracts text from Day 1–4 PDFs and associates each PDF with its respective day.
    """
    db = get_db()
    admin = g.current_user

    # Handle both multipart/form-data and JSON payloads
    if request.content_type and "multipart/form-data" in request.content_type:
        title = request.form.get("title")
        description = request.form.get("description", "")
        category = request.form.get("category", "General")
        status = request.form.get("status", "ACTIVE")
    else:
        data = request.get_json() or {}
        title = data.get("title")
        description = data.get("description", "")
        category = data.get("category", "General")
        status = data.get("status", "ACTIVE")

    if not title or not str(title).strip():
        return jsonify({"detail": "Title is required for Study Plan."}), 400

    plan = StudyPlan(
        title=str(title).strip(),
        description=str(description).strip() if description else None,
        category=str(category).strip() if category else "General",
        duration_weeks=6,
        status=str(status).strip() if status else "ACTIVE",
        created_by=admin.id
    )
    db.add(plan)
    db.commit()
    db.refresh(plan)

    # Automatically generate Week 1..6 and Day 1..6 per week
    created_weeks = []
    for w_num in range(1, 7):
        week = StudyPlanWeek(
            plan_id=plan.id,
            week_number=w_num,
            title=f"Week {w_num}",
            description=f"Core curriculum topics and learning goals for Week {w_num} of {plan.title}."
        )
        db.add(week)
        db.commit()
        db.refresh(week)
        created_weeks.append(week)

        for d_num in range(1, 7):
            has_lesson = (d_num <= 4)
            day = StudyPlanDay(
                week_id=week.id,
                day_number=d_num,
                title=f"Day {d_num}",
                topic=f"Week {w_num} Day {d_num} - {'Lesson Module' if has_lesson else 'Revision & Self-Study'}",
                content_summary=f"Daily study summary for Week {w_num}, Day {d_num}.",
                has_lesson=has_lesson,
                lesson_title=f"Week {w_num} Day {d_num}: Core Concepts" if has_lesson else None,
                lesson_content=None
            )
            db.add(day)

    db.commit()
    db.refresh(plan)

    # Check for Day 1..4 PDF uploads (for Week 1) in multipart/form-data
    if request.files:
        week_1 = created_weeks[0]
        w1_days = {d.day_number: d for d in week_1.days}

        for d_num in range(1, 5):
            file_key = f"day{d_num}_file"
            title_key = f"day{d_num}_title"
            file_obj = request.files.get(file_key) or request.files.get(f"day_{d_num}_file") or request.files.get(f"day_{d_num}_pdf")
            pdf_title = request.form.get(title_key) or request.form.get(f"day_{d_num}_title") or f"Week 1 Day {d_num} PDF"

            if file_obj and file_obj.filename and d_num in w1_days:
                save_study_plan_day_pdf(w1_days[d_num], file_obj, pdf_title, admin.id, db)

        # Check if all 4 lessons are saved to trigger Week 1 Exam generation
        lessons_saved = [d for d in week_1.days if d.has_lesson and d.day_number <= 4 and d.lesson_content and len(d.lesson_content.strip()) > 10]
        if len(lessons_saved) == 4 and not week_1.exam_id:
            try:
                from app.services.study_plan_ai import generate_week_exam_ai
                generate_week_exam_ai(week_1, plan, db)
            except Exception as e:
                logger.error(f"Failed auto-generating week 1 exam: {e}")

    log_audit_event(
        db, action="CREATE_STUDY_PLAN", entity_type="STUDY_PLAN", user_id=admin.id, entity_id=plan.id,
        details=f"Created 6-Week Study Plan '{plan.title}' with PDF document uploads"
    )

    result_data = StudyPlanOut.model_validate(plan).model_dump(mode="json")
    return jsonify(result_data), 201

@study_plans_bp.route("/<plan_id>", methods=["GET"])
@token_required
def get_study_plan(plan_id):
    db = get_db()
    plan = db.query(StudyPlan).filter(StudyPlan.id == plan_id).first()
    if not plan:
        return jsonify({"detail": "Study Plan not found."}), 404
    return jsonify(StudyPlanOut.model_validate(plan).model_dump(mode="json")), 200

@study_plans_bp.route("/days/<day_id>", methods=["GET"])
@token_required
def get_study_plan_day(day_id):
    """
    Get detailed Study Plan Day data including PDF title, extracted text, and document metadata.
    Accessible to all authenticated users (Admin and Students).
    """
    db = get_db()
    day = db.query(StudyPlanDay).filter(StudyPlanDay.id == day_id).first()
    if not day:
        return jsonify({"detail": "Study Plan Day not found."}), 404

    return jsonify(StudyPlanDayOut.model_validate(day).model_dump(mode="json")), 200

@study_plans_bp.route("/days/<day_id>/pdf", methods=["GET"])
@token_required
def view_study_plan_day_pdf(day_id):
    """
    Serves original uploaded PDF file for a Study Plan Day inline with Content-Type: application/pdf.
    Renders actual PDF document pages, layout, and images natively in the browser viewer.
    """
    db = get_db()
    current_user = g.current_user

    day = db.query(StudyPlanDay).filter(StudyPlanDay.id == day_id).first()
    if not day:
        return jsonify({"detail": "Study Plan Day not found."}), 404

    # Enforce day locking for non-admin students
    user_role_str = current_user.role.value if hasattr(current_user.role, 'value') else str(current_user.role)
    if user_role_str.upper() != "ADMIN":
        week = day.week
        plan = week.plan if week else None
        if plan:
            progress = db.query(UserStudyPlanProgress).filter(
                UserStudyPlanProgress.user_id == current_user.id,
                UserStudyPlanProgress.plan_id == plan.id
            ).first()

            curr_w = progress.current_week_number if progress else 1
            curr_d = progress.current_day_number if progress else 1

            is_unlocked = False
            if week.week_number < curr_w:
                is_unlocked = True
            elif week.week_number == curr_w:
                is_unlocked = (day.day_number <= curr_d)

            if not is_unlocked:
                return jsonify({"detail": f"Day {day.day_number} is locked. Please complete previous study plan modules to unlock."}), 403

    # Locate physical PDF file
    abs_path = None
    if day.pdf_file_path and os.path.exists(os.path.abspath(day.pdf_file_path)):
        abs_path = os.path.abspath(day.pdf_file_path)
    elif day.document_id:
        doc = db.query(Document).filter(Document.id == day.document_id).first()
        if doc and os.path.exists(os.path.abspath(doc.file_path)):
            abs_path = os.path.abspath(doc.file_path)
        elif doc:
            file_name = os.path.basename(doc.file_path)
            fallback = os.path.abspath(os.path.join(settings.UPLOAD_DIR, file_name))
            if os.path.exists(fallback):
                abs_path = fallback

    if not abs_path or not os.path.exists(abs_path):
        return jsonify({"detail": "Original PDF file not found on server disk for this study plan day."}), 404

    filename = (day.pdf_title or day.lesson_title or f"Day_{day.day_number}").strip()
    if not filename.lower().endswith(".pdf"):
        filename = f"{filename}.pdf"

    log_audit_event(
        db, action="VIEW_STUDY_PLAN_PDF", entity_type="STUDY_PLAN_DAY", user_id=current_user.id, entity_id=day.id
    )

    response = send_file(
        abs_path,
        as_attachment=False,
        download_name=filename,
        mimetype="application/pdf"
    )
    response.headers["Content-Disposition"] = f'inline; filename="{filename}"'
    response.headers["Content-Type"] = "application/pdf"
    return response

@study_plans_bp.route("/days/<day_id>/upload-pdf", methods=["POST", "PUT"])
@study_plans_bp.route("/days/<day_id>/lesson", methods=["PUT", "POST"])
@admin_required
def update_day_lesson_pdf(day_id):
    """
    Upload / update PDF document and title for a specific Day (Day 1..4 only).
    Extracts text, creates/updates Document record, indexes in ChromaDB,
    and auto-generates AI Week Exam when all 4 days are ready.
    Restricted to ADMIN role.
    """
    db = get_db()
    admin = g.current_user

    day = db.query(StudyPlanDay).filter(StudyPlanDay.id == day_id).first()
    if not day:
        return jsonify({"detail": "Study Plan Day not found."}), 404

    if not day.has_lesson or day.day_number > 4:
        return jsonify({"detail": "Only Day 1, Day 2, Day 3, and Day 4 support lesson PDF documents."}), 400

    # 1. Handle Multipart PDF file upload
    if request.files and ("file" in request.files or "pdf_file" in request.files):
        file_obj = request.files.get("file") or request.files.get("pdf_file")
        pdf_title = (
            request.form.get("title") or
            request.form.get("lesson_title") or
            request.form.get("pdf_title") or
            day.pdf_title or
            f"Day {day.day_number} PDF"
        )
        if not file_obj or not file_obj.filename:
            return jsonify({"detail": "Please select a valid PDF file to upload."}), 400

        save_study_plan_day_pdf(day, file_obj, pdf_title, admin.id, db)

    # 2. Handle JSON or text update (fallback)
    elif request.is_json:
        data = request.get_json() or {}
        if "lesson_title" in data and data["lesson_title"]:
            day.pdf_title = str(data["lesson_title"]).strip()
            day.lesson_title = str(data["lesson_title"]).strip()
        if "lesson_content" in data and data["lesson_content"]:
            day.pdf_extracted_text = str(data["lesson_content"]).strip()
            day.lesson_content = str(data["lesson_content"]).strip()
        db.commit()
        db.refresh(day)

    # Check if all 4 lessons (Day 1..4) of this week are saved, and auto-generate AI Week Exam
    week = day.week
    plan = week.plan if week else None
    exam_generated = False
    if week and plan:
        lessons_saved = [d for d in week.days if d.has_lesson and d.day_number <= 4 and d.lesson_content and len(d.lesson_content.strip()) > 10]
        if len(lessons_saved) == 4 and not week.exam_id:
            try:
                from app.services.study_plan_ai import generate_week_exam_ai
                generate_week_exam_ai(week, plan, db)
                exam_generated = True
            except Exception as e:
                logger.error(f"Failed auto-generating week exam: {e}")

    log_audit_event(
        db, action="UPDATE_LESSON_PDF", entity_type="STUDY_PLAN_DAY", user_id=admin.id, entity_id=day.id,
        details=f"Uploaded PDF '{day.pdf_title}' for Day {day.day_number}" + (" (Triggered AI Week Exam Generation)" if exam_generated else "")
    )

    return jsonify(StudyPlanDayOut.model_validate(day).model_dump(mode="json")), 200

@study_plans_bp.route("/<plan_id>", methods=["PUT"])
@admin_required
def update_study_plan(plan_id):
    """
    Update an existing study plan metadata.
    Restricted to ADMIN role.
    """
    db = get_db()
    admin = g.current_user
    data = request.get_json() or {}

    plan = db.query(StudyPlan).filter(StudyPlan.id == plan_id).first()
    if not plan:
        return jsonify({"detail": "Study Plan not found."}), 404

    if "title" in data and data["title"] is not None:
        if not str(data["title"]).strip():
            return jsonify({"detail": "Title cannot be empty."}), 400
        plan.title = str(data["title"]).strip()

    if "description" in data and data["description"] is not None:
        plan.description = str(data["description"]).strip()

    if "category" in data and data["category"] is not None:
        plan.category = str(data["category"]).strip()

    if "status" in data and data["status"] is not None:
        plan.status = str(data["status"]).strip()

    db.commit()
    db.refresh(plan)

    log_audit_event(
        db, action="UPDATE_STUDY_PLAN", entity_type="STUDY_PLAN", user_id=admin.id, entity_id=plan.id,
        details=f"Updated Study Plan '{plan.title}'"
    )

    return jsonify(StudyPlanOut.model_validate(plan).model_dump(mode="json")), 200

@study_plans_bp.route("/<plan_id>", methods=["DELETE"])
@admin_required
def delete_study_plan(plan_id):
    """
    Delete a study plan and all associated automated weeks, days, and PDFs.
    Restricted to ADMIN role.
    """
    db = get_db()
    admin = g.current_user

    plan = db.query(StudyPlan).filter(StudyPlan.id == plan_id).first()
    if not plan:
        return jsonify({"detail": "Study Plan not found."}), 404

    # Purge vectors from ChromaDB for all days of this plan
    for week in plan.weeks:
        for day in week.days:
            if day.document_id:
                vector_service.delete_document_chunks(day.document_id)
            vector_service.delete_document_chunks(f"sp_day_{day.id}")

    db.delete(plan)
    db.commit()

    log_audit_event(
        db, action="DELETE_STUDY_PLAN", entity_type="STUDY_PLAN", user_id=admin.id, entity_id=plan_id,
        details=f"Deleted Study Plan '{plan.title}'"
    )

    return jsonify({"message": "Study Plan deleted successfully"}), 200

@study_plans_bp.route("/weeks/<week_id>/regenerate-exam", methods=["POST"])
@admin_required
def regenerate_week_exam(week_id):
    """
    Manually trigger/regenerate AI Week Exam for a week using Day 1..4 PDF content.
    Restricted to ADMIN role.
    """
    db = get_db()
    admin = g.current_user

    week = db.query(StudyPlanWeek).filter(StudyPlanWeek.id == week_id).first()
    if not week:
        return jsonify({"detail": "Study Plan Week not found."}), 404

    plan = week.plan
    if not plan:
        return jsonify({"detail": "Study Plan not found."}), 404

    lessons_saved = [d for d in week.days if d.has_lesson and d.day_number <= 4 and d.lesson_content and len(d.lesson_content.strip()) > 10]
    if len(lessons_saved) < 4:
        return jsonify({"detail": "All 4 lessons (Day 1 to Day 4 PDFs) must be uploaded before generating the Week Exam."}), 400

    week.exam_id = None
    week.exam_status = "GENERATING"
    db.commit()

    from app.services.study_plan_ai import generate_week_exam_ai
    exam = generate_week_exam_ai(week, plan, db)

    if not exam:
        return jsonify({"detail": "AI Exam Generation failed. Please try again."}), 500

    return jsonify({"message": f"Week {week.week_number} Exam Generated Successfully.", "exam_id": exam.id}), 200

@study_plans_bp.route("/weeks/<week_id>/exam", methods=["GET"])
@token_required
def get_or_generate_week_exam(week_id):
    """
    Get or dynamically generate the Day 5 assessment exam for this week from the 4 lesson PDFs.
    Ensures that when a user reaches Day 5 and clicks 'Take Exam', the exam is guaranteed to exist.
    """
    db = get_db()
    week = db.query(StudyPlanWeek).filter(StudyPlanWeek.id == week_id).first()
    if not week:
        return jsonify({"detail": "Study Plan Week not found."}), 404

    plan = week.plan
    if not plan:
        return jsonify({"detail": "Study Plan not found."}), 404

    exam = None
    if week.exam_id:
        exam = db.query(Exam).filter(Exam.id == week.exam_id).first()

    if not exam or db.query(Question).filter(Question.exam_id == exam.id).count() == 0:
        from app.services.study_plan_ai import generate_week_exam_ai
        exam = generate_week_exam_ai(week, plan, db)

    if not exam:
        return jsonify({"detail": "Unable to load or generate exam for this week. Please ensure Day 1 to Day 4 lesson PDFs are uploaded."}), 400

    q_count = db.query(Question).filter(Question.exam_id == exam.id).count()
    return jsonify({
        "id": exam.id,
        "week_id": week.id,
        "plan_id": plan.id,
        "title": exam.title,
        "description": exam.description,
        "duration_minutes": exam.duration_minutes,
        "passing_score": exam.passing_score,
        "status": exam.status.value if hasattr(exam.status, 'value') else str(exam.status),
        "question_count": q_count
    }), 200

@study_plans_bp.route("/<plan_id>/progress", methods=["GET"])
@token_required
def get_user_progress(plan_id):
    """
    Get user progression state for a study plan.
    """
    db = get_db()
    user = g.current_user

    progress = db.query(UserStudyPlanProgress).filter(
        UserStudyPlanProgress.user_id == user.id,
        UserStudyPlanProgress.plan_id == plan_id
    ).first()

    if not progress:
        progress = UserStudyPlanProgress(
            user_id=user.id,
            plan_id=plan_id,
            current_week_number=1,
            current_day_number=1,
            completed_days_json="[]",
            completed_weeks_json="[]"
        )
        db.add(progress)
        db.commit()
        db.refresh(progress)

    try:
        completed_days = json.loads(progress.completed_days_json or "[]")
    except Exception:
        completed_days = []

    try:
        completed_weeks = json.loads(progress.completed_weeks_json or "[]")
    except Exception:
        completed_weeks = []

    return jsonify({
        "plan_id": plan_id,
        "user_id": user.id,
        "current_week_number": progress.current_week_number,
        "current_day_number": progress.current_day_number,
        "completed_days": completed_days,
        "completed_weeks": completed_weeks
    }), 200

@study_plans_bp.route("/days/<day_id>/page-progress", methods=["GET"])
@token_required
def get_day_page_progress(day_id):
    """
    Get the current user's viewed pages progress and resume position for a Study Plan Day PDF.
    """
    db = get_db()
    user = g.current_user

    day = db.query(StudyPlanDay).filter(StudyPlanDay.id == day_id).first()
    if not day:
        return jsonify({"detail": "Study Plan Day not found."}), 404

    week = day.week
    plan = week.plan if week else None
    if not plan:
        return jsonify({"detail": "Study Plan not found."}), 404

    progress = db.query(UserStudyPlanProgress).filter(
        UserStudyPlanProgress.user_id == user.id,
        UserStudyPlanProgress.plan_id == plan.id
    ).first()

    day_progress_dict = {}
    if progress and progress.day_page_progress_json:
        try:
            day_progress_dict = json.loads(progress.day_page_progress_json)
        except Exception:
            day_progress_dict = {}

    day_data = day_progress_dict.get(str(day_id), {})
    viewed_pages = day_data.get("viewed_pages", [])
    total_pages = day_data.get("total_pages", 0)
    last_page = day_data.get("last_page", 1)

    # If total_pages was not set or is 0, extract from actual PDF file on disk
    if (not total_pages or total_pages <= 0) and day.pdf_file_path:
        pdf_pages = get_pdf_page_count(day.pdf_file_path)
        if pdf_pages > 0:
            total_pages = pdf_pages
            day_data["total_pages"] = total_pages
            day_progress_dict[str(day_id)] = day_data
            if progress:
                progress.day_page_progress_json = json.dumps(day_progress_dict)
                db.commit()

    is_day_completed = False
    if progress and progress.completed_days_json:
        try:
            c_days = json.loads(progress.completed_days_json)
            is_day_completed = str(day.id) in c_days or day.id in c_days
        except Exception:
            is_day_completed = False

    viewed_set = set(viewed_pages)
    is_all_viewed = (total_pages > 0 and len(viewed_set) >= total_pages and set(range(1, total_pages + 1)).issubset(viewed_set))

    return jsonify({
        "day_id": str(day.id),
        "day_number": day.day_number,
        "title": day.pdf_title or day.lesson_title or day.topic or f"Day {day.day_number}",
        "total_pages": total_pages,
        "viewed_pages": sorted(list(viewed_set)),
        "viewed_count": len(viewed_set),
        "last_page": last_page,
        "is_all_viewed": is_all_viewed or is_day_completed,
        "is_day_completed": is_day_completed
    }), 200

@study_plans_bp.route("/days/<day_id>/page-progress", methods=["POST"])
@token_required
def update_day_page_progress(day_id):
    """
    Record viewed page(s) and update resume position for the current user.
    """
    db = get_db()
    user = g.current_user
    data = request.get_json() or {}

    day = db.query(StudyPlanDay).filter(StudyPlanDay.id == day_id).first()
    if not day:
        return jsonify({"detail": "Study Plan Day not found."}), 404

    week = day.week
    plan = week.plan if week else None
    if not plan:
        return jsonify({"detail": "Study Plan not found."}), 404

    progress = db.query(UserStudyPlanProgress).filter(
        UserStudyPlanProgress.user_id == user.id,
        UserStudyPlanProgress.plan_id == plan.id
    ).first()

    if not progress:
        progress = UserStudyPlanProgress(
            user_id=user.id,
            plan_id=plan.id,
            current_week_number=1,
            current_day_number=1,
            completed_days_json="[]",
            completed_weeks_json="[]",
            day_page_progress_json="{}"
        )
        db.add(progress)
        db.commit()
        db.refresh(progress)

    day_progress_dict = {}
    if progress.day_page_progress_json:
        try:
            day_progress_dict = json.loads(progress.day_page_progress_json)
        except Exception:
            day_progress_dict = {}

    day_data = day_progress_dict.get(str(day_id), {
        "viewed_pages": [],
        "total_pages": 0,
        "last_page": 1,
        "is_all_viewed": False
    })

    viewed_set = set(day_data.get("viewed_pages", []))

    # Support full list of viewed pages (sent from frontend)
    if "viewed_pages" in data and isinstance(data["viewed_pages"], list):
        for p in data["viewed_pages"]:
            try:
                p_int = int(p)
                if p_int > 0:
                    viewed_set.add(p_int)
            except (ValueError, TypeError):
                pass

    if "viewed_page" in data:
        try:
            p = int(data["viewed_page"])
            if p > 0:
                viewed_set.add(p)
        except (ValueError, TypeError):
            pass

    total_pages = data.get("total_pages") or day_data.get("total_pages", 0)
    try:
        total_pages = int(total_pages)
    except (ValueError, TypeError):
        total_pages = day_data.get("total_pages", 0)

    if (not total_pages or total_pages <= 0) and day.pdf_file_path:
        pdf_pages = get_pdf_page_count(day.pdf_file_path)
        if pdf_pages > 0:
            total_pages = pdf_pages

    last_page = data.get("last_page") or day_data.get("last_page", 1)
    try:
        last_page = int(last_page)
    except (ValueError, TypeError):
        last_page = 1

    is_all_viewed = (total_pages > 0 and len(viewed_set) >= total_pages and set(range(1, total_pages + 1)).issubset(viewed_set))

    day_data["viewed_pages"] = sorted(list(viewed_set))
    day_data["total_pages"] = total_pages
    day_data["last_page"] = last_page
    day_data["is_all_viewed"] = is_all_viewed

    day_progress_dict[str(day_id)] = day_data
    progress.day_page_progress_json = json.dumps(day_progress_dict)
    db.commit()

    return jsonify({
        "message": "Page progress updated successfully.",
        "day_id": str(day.id),
        "total_pages": total_pages,
        "viewed_pages": sorted(list(viewed_set)),
        "viewed_count": len(viewed_set),
        "last_page": last_page,
        "is_all_viewed": is_all_viewed
    }), 200

@study_plans_bp.route("/days/<day_id>/complete", methods=["POST"])
@token_required
def complete_study_plan_day(day_id):
    """
    Mark a Study Plan Day as completed for the current user.
    Enforces that all pages have been viewed if a PDF exists for this day.
    Unlocks the next Day / Exam / Mock Interview / Next Week,
    and permanently unlocks the PDF document in the user's Documents section.
    """
    db = get_db()
    user = g.current_user
    req_data = request.get_json(silent=True) or {}

    day = db.query(StudyPlanDay).filter(StudyPlanDay.id == day_id).first()
    if not day:
        return jsonify({"detail": "Study Plan Day not found."}), 404

    week = day.week
    plan = week.plan if week else None
    if not plan:
        return jsonify({"detail": "Study Plan not found."}), 404

    progress = db.query(UserStudyPlanProgress).filter(
        UserStudyPlanProgress.user_id == user.id,
        UserStudyPlanProgress.plan_id == plan.id
    ).first()

    if not progress:
        progress = UserStudyPlanProgress(
            user_id=user.id,
            plan_id=plan.id,
            current_week_number=1,
            current_day_number=1,
            completed_days_json="[]",
            completed_weeks_json="[]",
            day_page_progress_json="{}"
        )
        db.add(progress)
        db.commit()
        db.refresh(progress)

    day_progress_dict = {}
    if progress.day_page_progress_json:
        try:
            day_progress_dict = json.loads(progress.day_page_progress_json)
        except Exception:
            day_progress_dict = {}

    day_data = day_progress_dict.get(str(day_id), {
        "viewed_pages": [],
        "total_pages": 0,
        "last_page": 1,
        "is_all_viewed": False
    })
    viewed_set = set(day_data.get("viewed_pages", []))

    # Merge any pages sent with complete request
    if "viewed_pages" in req_data and isinstance(req_data["viewed_pages"], list):
        for p in req_data["viewed_pages"]:
            try:
                p_int = int(p)
                if p_int > 0:
                    viewed_set.add(p_int)
            except (ValueError, TypeError):
                pass

    total_pages = req_data.get("total_pages") or day_data.get("total_pages", 0)
    try:
        total_pages = int(total_pages)
    except (ValueError, TypeError):
        total_pages = day_data.get("total_pages", 0)

    if (not total_pages or total_pages <= 0) and day.pdf_file_path:
        pdf_pages = get_pdf_page_count(day.pdf_file_path)
        if pdf_pages > 0:
            total_pages = pdf_pages

    is_all_viewed = (total_pages > 0 and len(viewed_set) >= total_pages and set(range(1, total_pages + 1)).issubset(viewed_set))
    day_data["viewed_pages"] = sorted(list(viewed_set))
    day_data["total_pages"] = total_pages
    day_data["is_all_viewed"] = is_all_viewed
    day_progress_dict[str(day_id)] = day_data
    progress.day_page_progress_json = json.dumps(day_progress_dict)
    db.commit()

    # Verification: If day has a PDF, ensure all pages have been viewed (unless admin)
    user_role_str = user.role.value if hasattr(user.role, 'value') else str(user.role)
    if day.pdf_file_path and user_role_str.upper() != "ADMIN":
        if not is_all_viewed:
            return jsonify({
                "detail": "Please read/view all pages of this lesson before marking it as completed.",
                "total_pages": total_pages,
                "viewed_count": len(viewed_set),
                "viewed_pages": sorted(list(viewed_set)),
                "is_all_viewed": False
            }), 400

    try:
        completed_days = json.loads(progress.completed_days_json or "[]")
    except Exception:
        completed_days = []

    try:
        completed_weeks = json.loads(progress.completed_weeks_json or "[]")
    except Exception:
        completed_weeks = []

    if day.id not in completed_days:
        completed_days.append(day.id)

    if day.day_number == 6:
        if week.id not in completed_weeks:
            completed_weeks.append(week.id)
        if progress.current_week_number <= week.week_number:
            progress.current_week_number = min(6, week.week_number + 1)
            progress.current_day_number = 1
    else:
        if progress.current_day_number <= day.day_number:
            progress.current_day_number = min(6, day.day_number + 1)

    progress.completed_days_json = json.dumps(completed_days)
    progress.completed_weeks_json = json.dumps(completed_weeks)
    db.commit()

    # When Day 4 is completed, Day 5 (Take Exam) becomes available.
    # Ensure the Week Exam is generated from all 4 PDFs and associated with week.exam_id.
    generated_exam_id = week.exam_id
    if day.day_number == 4 or all(d.id in completed_days for d in week.days if d.day_number <= 4):
        from app.services.study_plan_ai import generate_week_exam_ai
        plan = week.plan
        if plan:
            exam = generate_week_exam_ai(week, plan, db)
            if exam:
                generated_exam_id = exam.id

    return jsonify({
        "message": f"Day {day.day_number} marked as completed. Next lesson is now unlocked.",
        "completed_days": completed_days,
        "completed_weeks": completed_weeks,
        "current_week_number": progress.current_week_number,
        "current_day_number": progress.current_day_number,
        "pdf_title": day.pdf_title,
        "week_id": week.id,
        "exam_id": generated_exam_id
    }), 200
