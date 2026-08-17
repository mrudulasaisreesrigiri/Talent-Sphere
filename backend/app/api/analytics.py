from flask import Blueprint, jsonify, g
from app.core.deps import token_required, admin_required, get_db
from app.models.models import (
    User, Document, Exam, ExamAttempt, ExamResult, AttemptStatus, StudyPlan
)
from app.schemas.schemas import DashboardAnalyticsOut

analytics_bp = Blueprint("analytics", __name__, url_prefix="/analytics")

@analytics_bp.route("/admin", methods=["GET"])
@admin_required
def get_admin_analytics():
    db = get_db()

    total_users = db.query(User).count()
    total_docs = db.query(Document).count()
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

    docs = db.query(Document).order_by(Document.created_at.desc()).limit(6).all()
    document_trends = [
        {"name": d.title[:15] + "...", "size_mb": round(d.file_size / (1024 * 1024), 2)}
        for d in docs
    ]

    monthly_analytics = [
        {"month": "Jan", "attempts": 0, "avg_score": 0},
        {"month": "Feb", "attempts": 0, "avg_score": 0},
        {"month": "Mar", "attempts": 0, "avg_score": 0},
        {"month": "Apr", "attempts": len(completed_attempts), "avg_score": average_score}
    ]

    analytics_data = DashboardAnalyticsOut(
        total_users=total_users,
        total_documents=total_docs,
        total_study_plans=total_study_plans,
        total_exams=total_exams,
        students_attempted=students_attempted,
        highest_score=highest_score,
        lowest_score=lowest_score,
        average_score=average_score,
        performance_trends=performance_trends,
        exam_trends=exam_trends,
        document_trends=document_trends,
        monthly_analytics=monthly_analytics
    ).model_dump(mode="json")

    return jsonify(analytics_data), 200

@analytics_bp.route("/user/me", methods=["GET"])
@token_required
def get_user_personal_analytics():
    db = get_db()
    current_user = g.current_user

    all_published_exams = db.query(Exam).filter(Exam.status == "PUBLISHED").count()
    my_attempts = db.query(ExamAttempt).filter(
        ExamAttempt.user_id == current_user.id,
        ExamAttempt.status == AttemptStatus.COMPLETED
    ).all()

    completed_exams = len(my_attempts)
    upcoming_exams = max(0, all_published_exams - completed_exams)

    scores = [a.score for a in my_attempts]
    highest_score = max(scores) if scores else 0.0
    lowest_score = min(scores) if scores else 0.0
    average_score = round(sum(scores) / len(scores), 2) if scores else 0.0

    attempt_history = [
        {
            "date": a.started_at.strftime("%b %d"),
            "score": a.score,
            "passed": a.passed
        }
        for a in my_attempts
    ]

    return jsonify({
        "upcoming_exams": upcoming_exams,
        "completed_exams": completed_exams,
        "average_score": average_score,
        "highest_score": highest_score,
        "lowest_score": lowest_score,
        "attempt_history": attempt_history
    }), 200
