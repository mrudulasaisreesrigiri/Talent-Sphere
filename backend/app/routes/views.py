import os
from datetime import datetime
from flask import Blueprint, render_template, redirect, url_for, request, jsonify, g, make_response
from app.core.deps import get_current_user, get_db
from app.models.models import (
    User, UserRole, Document, DocumentChunk, Exam, Question,
    ExamAttempt, ExamResult, Announcement, AuditLog, AttemptStatus, StudyPlan, StudyPlanWeek, StudyPlanDay
)
from app.schemas.schemas import DashboardAnalyticsOut, ExamOut, QuestionOut, ExamAttemptOut

views_bp = Blueprint("views", __name__)

def get_optional_user():
    user, _ = get_current_user()
    return user

@views_bp.route("/")
def index():
    user = get_optional_user()
    if not user:
        return redirect("/login")
    if user.role == UserRole.ADMIN:
        return redirect("/admin-dashboard")
    return redirect("/user-dashboard")

@views_bp.route("/login")
def login_page():
    user = get_optional_user()
    if user:
        if user.role == UserRole.ADMIN:
            return redirect("/admin-dashboard")
        return redirect("/user-dashboard")
    resp = make_response(render_template("login.html", current_user=None))
    resp.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    resp.headers["Pragma"] = "no-cache"
    resp.headers["Expires"] = "0"
    return resp

@views_bp.route("/admin-dashboard")
@views_bp.route("/admin/dashboard")
def admin_dashboard():
    user = get_optional_user()
    if not user or user.role != UserRole.ADMIN:
        return redirect("/login")

    db = get_db()
    total_users = db.query(User).count()
    total_study_plans = db.query(StudyPlan).count()
    total_exams = db.query(Exam).count()

    completed_attempts = db.query(ExamAttempt).filter(ExamAttempt.status == AttemptStatus.COMPLETED).all()
    students_attempted = len(set(a.user_id for a in completed_attempts))

    scores = [a.score for a in completed_attempts]
    highest_score = max(scores) if scores else 0.0
    lowest_score = min(scores) if scores else 0.0
    average_score = round(sum(scores) / len(scores), 2) if scores else 0.0

    pass_count = sum(1 for s in scores if s >= 70.0)
    fail_count = len(scores) - pass_count

    performance_trends = [
        {"name": "Passed (≥70%)", "value": pass_count},
        {"name": "Needs Improvement (<70%)", "value": fail_count}
    ]

    exams = db.query(Exam).all()
    exam_trends = []
    for ex in exams[:6]:
        ex_attempts = [a for a in completed_attempts if a.exam_id == ex.id]
        avg_s = round(sum(a.score for a in ex_attempts) / len(ex_attempts), 1) if ex_attempts else 0.0
        exam_trends.append({
            "exam_name": ex.title[:15] + "..." if len(ex.title) > 15 else ex.title,
            "attempts": len(ex_attempts),
            "avg_score": avg_s
        })

    analytics = {
        "total_users": total_users,
        "total_study_plans": total_study_plans,
        "total_exams": total_exams,
        "students_attempted": students_attempted,
        "highest_score": highest_score,
        "lowest_score": lowest_score,
        "average_score": average_score,
        "performance_trends": performance_trends,
        "exam_trends": exam_trends
    }

    return render_template("admin_dashboard.html", current_user=user, analytics=analytics)

@views_bp.route("/user-dashboard")
@views_bp.route("/dashboard")
@views_bp.route("/home")
def user_dashboard():
    user = get_optional_user()
    if not user:
        return redirect("/login")

    db = get_db()
    all_published_exams = db.query(Exam).filter(Exam.status == "PUBLISHED").count()
    my_attempts = db.query(ExamAttempt).filter(
        ExamAttempt.user_id == user.id,
        ExamAttempt.status == AttemptStatus.COMPLETED
    ).all()

    completed_exams = len(my_attempts)
    upcoming_exams = max(0, all_published_exams - completed_exams)

    scores = [a.score for a in my_attempts]
    highest_score = max(scores) if scores else 0.0
    lowest_score = min(scores) if scores else 0.0
    average_score = round(sum(scores) / len(scores), 2) if scores else 0.0

    attempt_history = [
        {"date": a.started_at.strftime("%b %d"), "score": a.score, "passed": a.passed}
        for a in my_attempts
    ]

    analytics = {
        "upcoming_exams": upcoming_exams,
        "completed_exams": completed_exams,
        "average_score": average_score,
        "highest_score": highest_score,
        "lowest_score": lowest_score,
        "attempt_history": attempt_history
    }

    announcements = db.query(Announcement).filter(Announcement.is_published == True).order_by(Announcement.created_at.desc()).limit(3).all()

    return render_template("user_dashboard.html", current_user=user, analytics=analytics, announcements=announcements)

@views_bp.route("/user-management")
@views_bp.route("/admin/users")
def user_management():
    user = get_optional_user()
    if not user or user.role != UserRole.ADMIN:
        return redirect("/login")

    db = get_db()
    users = db.query(User).order_by(User.created_at.desc()).all()
    return render_template("user_management.html", current_user=user, users=users)

@views_bp.route("/documents")
def document_management():
    # Standalone documents section has been replaced by Study Plans
    return redirect("/study-plans")

@views_bp.route("/knowledge-search")
@views_bp.route("/search")
def knowledge_search():
    user = get_optional_user()
    if not user:
        return redirect("/login")
    return render_template("knowledge_search.html", current_user=user)

@views_bp.route("/ai-assistant")
def ai_assistant_page():
    user = get_optional_user()
    if not user:
        return redirect("/login")
    return render_template("ai_assistant.html", current_user=user)

@views_bp.route("/exams")
def exams_page():
    user = get_optional_user()
    if not user:
        return redirect("/login")

    db = get_db()
    query = db.query(Exam)
    if user.role == UserRole.STUDENT:
        query = query.filter(Exam.status == "PUBLISHED")

    exams = query.order_by(Exam.created_at.desc()).all()
    for ex in exams:
        ex.question_count = db.query(Question).filter(Question.exam_id == ex.id).count()

    return render_template("exams.html", current_user=user, exams=exams)

@views_bp.route("/exams/<exam_id>/take")
@views_bp.route("/take-exam/<exam_id>")
def take_exam_page(exam_id):
    user = get_optional_user()
    if not user:
        return redirect("/login")

    db = get_db()
    exam = db.query(Exam).filter(Exam.id == exam_id).first()

    # Robust fallback: if exam_id was passed as a week_id or day_id, or if exam wasn't generated yet
    if not exam:
        week = db.query(StudyPlanWeek).filter(StudyPlanWeek.id == exam_id).first()
        if not week:
            day = db.query(StudyPlanDay).filter(StudyPlanDay.id == exam_id).first()
            if day and day.week:
                week = day.week
        if week:
            if week.exam_id:
                exam = db.query(Exam).filter(Exam.id == week.exam_id).first()
            if not exam:
                from app.services.study_plan_ai import generate_week_exam_ai
                plan = week.plan
                if plan:
                    exam = generate_week_exam_ai(week, plan, db)

    if not exam:
        return render_template("take_exam_error.html", current_user=user, message="Exam not found or has not been generated yet. Please ensure Day 1 to Day 4 lesson PDFs are uploaded.") if os.path.exists("backend/app/templates/take_exam_error.html") else ("Exam not found", 404)

    actual_exam_id = exam.id
    questions = db.query(Question).filter(Question.exam_id == actual_exam_id).all()

    # If questions are empty, trigger auto-generation from the 4 PDFs
    if not questions:
        week = db.query(StudyPlanWeek).filter(StudyPlanWeek.exam_id == actual_exam_id).first()
        if week and week.plan:
            from app.services.study_plan_ai import generate_week_exam_ai
            exam = generate_week_exam_ai(week, week.plan, db)
            if exam:
                actual_exam_id = exam.id
                questions = db.query(Question).filter(Question.exam_id == actual_exam_id).all()

    attempt = db.query(ExamAttempt).filter(
        ExamAttempt.exam_id == actual_exam_id,
        ExamAttempt.user_id == user.id
    ).first()

    if not attempt:
        attempt = ExamAttempt(
            exam_id=actual_exam_id,
            user_id=user.id,
            status=AttemptStatus.IN_PROGRESS
        )
        db.add(attempt)
        db.commit()
        db.refresh(attempt)

    exam_dict = ExamOut.model_validate(exam).model_dump(mode="json")
    questions_list = [QuestionOut.model_validate(q).model_dump(mode="json") for q in questions]
    attempt_dict = ExamAttemptOut.model_validate(attempt).model_dump(mode="json")

    return render_template("take_exam.html", current_user=user, exam=exam_dict, questions=questions_list, attempt=attempt_dict)

@views_bp.route("/announcements")
def announcements_page():
    user = get_optional_user()
    if not user:
        return redirect("/login")

    db = get_db()
    announcements = db.query(Announcement).filter(Announcement.is_published == True).order_by(Announcement.created_at.desc()).all()
    return render_template("announcements.html", current_user=user, announcements=announcements)

@views_bp.route("/admin/audit-logs")
def audit_logs_page():
    user = get_optional_user()
    if not user or user.role != UserRole.ADMIN:
        return redirect("/login")

    db = get_db()
    logs = db.query(AuditLog).order_by(AuditLog.timestamp.desc()).limit(100).all()
    return render_template("audit_logs.html", current_user=user, logs=logs)

@views_bp.route("/profile")
def profile_page():
    user = get_optional_user()
    if not user:
        return redirect("/login")
    return render_template("profile.html", current_user=user)

@views_bp.route("/study-plans")
def study_plans_page():
    user = get_optional_user()
    if not user:
        return redirect("/login")

    db = get_db()
    plans = db.query(StudyPlan).order_by(StudyPlan.created_at.desc()).all()
    return render_template("study_plans.html", current_user=user, study_plans=plans)

@views_bp.route("/logout")
def logout_route():
    resp = redirect("/login")
    resp.set_cookie("access_token", "", max_age=0, path="/")
    return resp

