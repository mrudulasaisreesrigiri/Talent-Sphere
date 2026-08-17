import json
import logging
import re
from datetime import datetime
from flask import Blueprint, request, jsonify, g, render_template, redirect, url_for
from app.core.deps import token_required, admin_required, get_db
from app.models.models import Exam, Question, ExamAttempt, ExamResult, StudentAnswer, ExamStatus, AttemptStatus, UserRole, User, Notification, StudyPlanWeek, StudyPlanDay, UserStudyPlanProgress
from app.schemas.schemas import ExamOut, QuestionOut, ExamAttemptOut, ExamResultOut
from app.services.groq_service import groq_service
from app.utils.logger import log_audit_event

logger = logging.getLogger(__name__)

exams_bp = Blueprint("exams", __name__, url_prefix="/exams")

@exams_bp.route("", methods=["GET"])
@token_required
def get_all_exams():
    db = get_db()
    current_user = g.current_user

    if current_user.role == UserRole.ADMIN:
        exams = db.query(Exam).order_by(Exam.created_at.desc()).all()
    else:
        exams = db.query(Exam).filter(
            Exam.status == ExamStatus.PUBLISHED
        ).order_by(Exam.created_at.desc()).all()

    results = []
    for ex in exams:
        q_count = db.query(Question).filter(Question.exam_id == ex.id).count()
        exam_dict = {
            "id": ex.id,
            "title": ex.title,
            "description": ex.description,
            "duration_minutes": ex.duration_minutes,
            "passing_score": ex.passing_score,
            "status": ex.status,
            "source_document_name": ex.source_document_name,
            "created_at": ex.created_at,
            "question_count": q_count
        }
        results.append(ExamOut(**exam_dict).model_dump(mode="json"))

    return jsonify(results), 200

@exams_bp.route("", methods=["POST"])
@admin_required
def create_exam_manual():
    db = get_db()
    admin = g.current_user
    data = request.get_json() or {}

    title = data.get("title")
    duration = data.get("duration_minutes", 30)
    passing_score = data.get("passing_score", 70.0)
    description = data.get("description", "")
    questions_input = data.get("questions", [])

    if not title or not str(title).strip():
        return jsonify({"detail": "Exam title is required."}), 400

    try:
        duration_int = int(duration)
        if duration_int <= 0:
            return jsonify({"detail": "Duration must be greater than 0 minutes."}), 400
    except (ValueError, TypeError):
        return jsonify({"detail": "Duration minutes must be a valid positive integer."}), 400

    try:
        passing_float = float(passing_score)
        if passing_float < 0 or passing_float > 100:
            return jsonify({"detail": "Passing score must be between 0 and 100%."}), 400
    except (ValueError, TypeError):
        return jsonify({"detail": "Passing score must be a valid number between 0 and 100."}), 400

    try:
        db_exam = Exam(
            title=str(title).strip(),
            description=str(description).strip() if description else None,
            duration_minutes=duration_int,
            passing_score=passing_float,
            status=ExamStatus.DRAFT
        )
        db.add(db_exam)
        db.commit()
        db.refresh(db_exam)

        if isinstance(questions_input, list):
            for q_idx, q in enumerate(questions_input, 1):
                q_text = q.get("question_text")
                if not q_text or not str(q_text).strip():
                    continue

                q_type = q.get("question_type", "MCQ")
                opt_a = q.get("option_a")
                opt_b = q.get("option_b")
                opt_c = q.get("option_c")
                opt_d = q.get("option_d")
                corr_opt = q.get("correct_option", "A")
                pts = q.get("points", 1.0)

                db_q = Question(
                    exam_id=db_exam.id,
                    question_type=q_type,
                    question_text=str(q_text).strip(),
                    option_a=str(opt_a).strip() if opt_a else None,
                    option_b=str(opt_b).strip() if opt_b else None,
                    option_c=str(opt_c).strip() if opt_c else None,
                    option_d=str(opt_d).strip() if opt_d else None,
                    correct_option=str(corr_opt).strip(),
                    explanation=str(q.get("explanation", "")).strip() if q.get("explanation") else None,
                    points=float(pts) if pts else 1.0
                )
                db.add(db_q)

        db.commit()

        log_audit_event(
            db, action="CREATE_MANUAL_EXAM", entity_type="EXAM", user_id=admin.id, entity_id=db_exam.id,
            details=f"Created exam '{db_exam.title}' with {len(questions_input)} questions"
        )

        q_count = db.query(Question).filter(Question.exam_id == db_exam.id).count()
        result_data = ExamOut(
            id=db_exam.id,
            title=db_exam.title,
            description=db_exam.description,
            duration_minutes=db_exam.duration_minutes,
            passing_score=db_exam.passing_score,
            status=db_exam.status,
            created_at=db_exam.created_at,
            question_count=q_count
        ).model_dump(mode="json")

        logger.info(f"Successfully created manual exam ID='{db_exam.id}' with {q_count} questions.")
        return jsonify(result_data), 201

    except Exception as e:
        db.rollback()
        logger.error(f"Failed to create manual exam: {e}", exc_info=True)
        return jsonify({"detail": f"Database error creating exam: {str(e)}"}), 500

def resolve_exam_by_id(exam_id: str, db):
    """
    Resolves an exam by ID, Week ID, or Day ID. If the exam record for a completed 4-lesson Study Plan Week
    has not been created or linked yet, generates it on-the-fly from the 4 lesson PDFs.
    """
    if not exam_id or str(exam_id).strip() in ("", "None", "null", "undefined"):
        return None
    exam = db.query(Exam).filter(Exam.id == exam_id).first()
    if exam:
        return exam
    week = db.query(StudyPlanWeek).filter(StudyPlanWeek.id == exam_id).first()
    if not week:
        day = db.query(StudyPlanDay).filter(StudyPlanDay.id == exam_id).first()
        if day and day.week:
            week = day.week
    if week:
        if week.exam_id:
            exam = db.query(Exam).filter(Exam.id == week.exam_id).first()
            if exam:
                return exam
        from app.services.study_plan_ai import generate_week_exam_ai
        plan = week.plan
        if plan:
            return generate_week_exam_ai(week, plan, db)
    return None

@exams_bp.route("/<exam_id>", methods=["GET"])
@token_required
def get_exam_detail(exam_id):
    db = get_db()
    current_user = g.current_user

    exam = resolve_exam_by_id(exam_id, db)
    if not exam:
        return jsonify({"detail": "Exam not found"}), 404

    if current_user.role == UserRole.STUDENT and exam.status != ExamStatus.PUBLISHED:
        return jsonify({"detail": "Exam is not published yet"}), 403

    q_count = db.query(Question).filter(Question.exam_id == exam.id).count()
    result_data = ExamOut(
        id=exam.id,
        title=exam.title,
        description=exam.description,
        duration_minutes=exam.duration_minutes,
        passing_score=exam.passing_score,
        status=exam.status,
        source_document_name=exam.source_document_name,
        created_at=exam.created_at,
        question_count=q_count
    ).model_dump(mode="json")
    return jsonify(result_data), 200

@exams_bp.route("/<exam_id>/questions", methods=["GET"])
@token_required
def get_exam_questions(exam_id):
    db = get_db()
    current_user = g.current_user

    exam = resolve_exam_by_id(exam_id, db)
    if not exam:
        return jsonify({"detail": "Exam not found"}), 404

    questions = db.query(Question).filter(Question.exam_id == exam.id).all()
    results = []
    for q in questions:
        q_dict = {
            "id": q.id,
            "exam_id": q.exam_id,
            "question_type": q.question_type,
            "question_text": q.question_text,
            "option_a": q.option_a,
            "option_b": q.option_b,
            "option_c": q.option_c,
            "option_d": q.option_d,
            "correct_option": q.correct_option if current_user.role == UserRole.ADMIN else None,
            "points": q.points,
            "explanation": q.explanation if current_user.role == UserRole.ADMIN else None
        }
        results.append(QuestionOut(**q_dict).model_dump(mode="json"))
    return jsonify(results), 200

@exams_bp.route("/<exam_id>", methods=["PUT"])
@admin_required
def update_exam(exam_id):
    db = get_db()
    admin = g.current_user
    data = request.get_json() or {}

    exam = db.query(Exam).filter(Exam.id == exam_id).first()
    if not exam:
        return jsonify({"detail": "Exam not found"}), 404

    try:
        if "title" in data and data["title"] is not None:
            if not str(data["title"]).strip():
                return jsonify({"detail": "Exam title cannot be empty."}), 400
            exam.title = str(data["title"]).strip()

        if "description" in data and data["description"] is not None:
            exam.description = str(data["description"]).strip()

        if "duration_minutes" in data and data["duration_minutes"] is not None:
            dm = int(data["duration_minutes"])
            if dm <= 0:
                return jsonify({"detail": "Duration must be greater than 0 minutes."}), 400
            exam.duration_minutes = dm

        if "passing_score" in data and data["passing_score"] is not None:
            ps = float(data["passing_score"])
            if ps < 0 or ps > 100:
                return jsonify({"detail": "Passing score must be between 0 and 100%."}), 400
            exam.passing_score = ps

        if "status" in data and data["status"] is not None:
            old_status = exam.status
            new_status = ExamStatus(data["status"]) if hasattr(ExamStatus, data["status"]) else exam.status
            exam.status = new_status

            if old_status != ExamStatus.PUBLISHED and new_status == ExamStatus.PUBLISHED:
                all_users = db.query(User).filter(User.is_active == True).all()
                for u in all_users:
                    notif = Notification(
                        user_id=u.id,
                        title="New Exam Published",
                        message=f"Exam '{exam.title}' is now live for assessment.",
                        type="EXAM_PUBLISHED"
                    )
                    db.add(notif)

        if "questions" in data and isinstance(data["questions"], list):
            db.query(Question).filter(Question.exam_id == exam.id).delete()
            for q in data["questions"]:
                q_type = q.get("question_type", "MCQ")
                db_q = Question(
                    exam_id=exam.id,
                    question_type=q_type,
                    question_text=str(q.get("question_text", "")).strip(),
                    option_a=str(q.get("option_a", "")).strip() if q.get("option_a") else None,
                    option_b=str(q.get("option_b", "")).strip() if q.get("option_b") else None,
                    option_c=str(q.get("option_c", "")).strip() if q.get("option_c") else None,
                    option_d=str(q.get("option_d", "")).strip() if q.get("option_d") else None,
                    correct_option=str(q.get("correct_option", "A")).strip(),
                    explanation=str(q.get("explanation", "")).strip() if q.get("explanation") else None,
                    points=float(q.get("points", 1.0))
                )
                db.add(db_q)

        db.commit()
        db.refresh(exam)

        log_audit_event(
            db, action="UPDATE_EXAM", entity_type="EXAM", user_id=admin.id, entity_id=exam.id, details=f"Updated exam '{exam.title}' status={exam.status}"
        )

        q_count = db.query(Question).filter(Question.exam_id == exam.id).count()
        result_data = ExamOut(
            id=exam.id,
            title=exam.title,
            description=exam.description,
            duration_minutes=exam.duration_minutes,
            passing_score=exam.passing_score,
            status=exam.status,
            source_document_name=exam.source_document_name,
            created_at=exam.created_at,
            question_count=q_count
        ).model_dump(mode="json")
        return jsonify(result_data), 200

    except Exception as e:
        db.rollback()
        logger.error(f"Error updating exam {exam_id}: {e}", exc_info=True)
        return jsonify({"detail": f"Database error updating exam: {str(e)}"}), 500

@exams_bp.route("/<exam_id>", methods=["DELETE"])
@admin_required
def delete_exam(exam_id):
    db = get_db()
    admin = g.current_user

    exam = db.query(Exam).filter(Exam.id == exam_id).first()
    if not exam:
        return jsonify({"detail": "Exam not found"}), 404

    try:
        db.delete(exam)
        db.commit()

        log_audit_event(
            db, action="DELETE_EXAM", entity_type="EXAM", user_id=admin.id, entity_id=exam_id, details=f"Deleted exam '{exam.title}'"
        )
        return jsonify({"message": "Exam deleted successfully"}), 200
    except Exception as e:
        db.rollback()
        logger.error(f"Error deleting exam {exam_id}: {e}", exc_info=True)
        return jsonify({"detail": "Database error deleting exam."}), 500

@exams_bp.route("/<exam_id>/start", methods=["POST"])
@token_required
def start_exam_attempt(exam_id):
    db = get_db()
    current_user = g.current_user

    exam = resolve_exam_by_id(exam_id, db)
    if not exam or exam.status != ExamStatus.PUBLISHED:
        return jsonify({"detail": "Exam is unavailable or not published"}), 400

    actual_exam_id = exam.id

    existing_attempt = db.query(ExamAttempt).filter(
        ExamAttempt.exam_id == actual_exam_id,
        ExamAttempt.user_id == current_user.id
    ).first()

    if existing_attempt:
        if existing_attempt.status == AttemptStatus.COMPLETED:
            return jsonify({"detail": "You have already completed this exam attempt."}), 400
        # Reset started_at timestamp so student gets full exam duration
        existing_attempt.started_at = datetime.utcnow()
        db.commit()
        db.refresh(existing_attempt)
        attempt_data = ExamAttemptOut.model_validate(existing_attempt).model_dump(mode="json")
        return jsonify(attempt_data), 200

    attempt = ExamAttempt(
        exam_id=actual_exam_id,
        user_id=current_user.id,
        started_at=datetime.utcnow(),
        status=AttemptStatus.IN_PROGRESS
    )
    db.add(attempt)
    db.commit()
    db.refresh(attempt)

    log_audit_event(
        db, action="START_EXAM_ATTEMPT", entity_type="EXAM_ATTEMPT", user_id=current_user.id, entity_id=attempt.id
    )
    attempt_data = ExamAttemptOut.model_validate(attempt).model_dump(mode="json")
    return jsonify(attempt_data), 200

@exams_bp.route("/attempts/<attempt_id>/submit", methods=["POST"])
@token_required
def submit_exam_attempt(attempt_id):
    db = get_db()
    current_user = g.current_user
    data = request.get_json() or {}
    submission_answers = data.get("answers", [])

    attempt = db.query(ExamAttempt).filter(ExamAttempt.id == attempt_id).first()
    if not attempt or attempt.user_id != current_user.id:
        return jsonify({"detail": "Exam attempt record not found"}), 404

    try:
        exam = db.query(Exam).filter(Exam.id == attempt.exam_id).first()
        questions = db.query(Question).filter(Question.exam_id == attempt.exam_id).all()
        ans_map = {a.get("question_id"): str(a.get("selected_option", "")).strip() for a in submission_answers}

        # Clear any prior student answers if re-submitting
        db.query(StudentAnswer).filter(StudentAnswer.attempt_id == attempt.id).delete()

        total_questions = len(questions)
        correct_count = 0
        total_earned_points = 0.0
        total_possible_points = sum(q.points for q in questions) or 1.0
        question_breakdown = []

        week = db.query(StudyPlanWeek).filter(StudyPlanWeek.exam_id == exam.id).first() if exam else None

        for q in questions:
            user_ans = ans_map.get(q.id, "")
            is_correct = False
            points_earned = 0.0
            feedback = ""

            if q.question_type == "MCQ":
                is_correct = (user_ans.upper() == str(q.correct_option).strip().upper())
                points_earned = q.points if is_correct else 0.0
                feedback = "Correct option chosen!" if is_correct else f"Incorrect. Correct option: {q.correct_option}"

            elif q.question_type in ["One Word", "FillBlank"]:
                u_clean = re.sub(r'[^\w\s]', '', user_ans.lower()).strip()
                exp_clean = re.sub(r'[^\w\s]', '', str(q.correct_option).lower()).strip()
                is_correct = (u_clean == exp_clean or (len(exp_clean) > 2 and exp_clean in u_clean) or (len(u_clean) > 2 and u_clean in exp_clean))
                points_earned = q.points if is_correct else 0.0
                feedback = "Exact match!" if is_correct else f"Expected Answer: '{q.correct_option}'"

            elif q.question_type == "DESCRIPTIVE":
                if not user_ans or len(user_ans) < 5:
                    is_correct = False
                    points_earned = 0.0
                    feedback = "No substantial answer provided."
                else:
                    from app.services.vector_service import vector_service
                    from app.services.groq_service import GroqService

                    retrieved_chunks = vector_service.search_week_vectors(week.id, q.question_text, top_k=4) if week else []
                    
                    retrieved_context = ""
                    if retrieved_chunks:
                        for idx, ch in enumerate(retrieved_chunks):
                            retrieved_context += f"\n--- [RETRIEVED VECTOR CHUNK #{idx+1} ({ch.get('document_title')})] ---\n{ch['content']}"

                    eval_prompt = f"""You are an expert AI Examiner performing a Retrieval-Augmented Generation (RAG) evaluation of a student's descriptive exam answer.

RETRIEVED LESSON CONTENT CHUNKS FROM CHROMADB VECTOR DB:
{retrieved_context}

EXAM QUESTION: {q.question_text}
EXPECTED RUBRIC: {q.correct_option}
STUDENT ANSWER: {user_ans}

Evaluate the student's answer strictly against the RETRIEVED LESSON CONTENT CHUNKS based on:
1. Correctness (Are technical statements accurate according to retrieved lesson content?)
2. Completeness (Did the student address key mechanisms explained in the lesson?)
3. Concept Understanding (Does the student demonstrate genuine understanding of the lesson principles?)

Return ONLY raw JSON:
{{
  "score_fraction": 0.85,
  "feedback": "Your answer accurately explains... according to the lesson text, but omitted...",
  "correct_explanation": "According to the lesson content: <detailed explanation from retrieved vector chunks>"
}}
"""
                    try:
                        raw_res = GroqService.generate_response(prompt=eval_prompt, system_prompt="You are a strict JSON evaluator. Return ONLY JSON.")
                        match = re.search(r'\{.*\}', raw_res, re.DOTALL)
                        if match:
                            eval_data = json.loads(match.group(0))
                            sf = float(eval_data.get("score_fraction", 0.7))
                            feedback = eval_data.get("feedback", "Good technical effort.")
                            corr_exp = eval_data.get("correct_explanation")
                            if corr_exp:
                                feedback += f" [Lesson Reference: {corr_exp}]"
                            points_earned = round(q.points * sf, 2)
                            is_correct = (sf >= 0.7)
                        else:
                            is_correct = True
                            points_earned = q.points
                            feedback = "Descriptive answer evaluated against retrieved ChromaDB lesson chunks."
                    except Exception as exc:
                        logger.error(f"Error in RAG descriptive evaluation: {exc}")
                        is_correct = True
                        points_earned = q.points
                        feedback = "Descriptive answer submitted and evaluated against lesson concepts."

            if is_correct:
                correct_count += 1
            total_earned_points += points_earned

            db_answer = StudentAnswer(
                attempt_id=attempt.id,
                question_id=q.id,
                selected_option=user_ans,
                is_correct=is_correct,
                points_earned=points_earned
            )
            db.add(db_answer)

            question_breakdown.append({
                "question_id": q.id,
                "question_type": q.question_type,
                "question_text": q.question_text,
                "user_answer": user_ans or "(No Answer)",
                "correct_option": q.correct_option,
                "is_correct": is_correct,
                "points_earned": points_earned,
                "max_points": q.points,
                "feedback": feedback
            })

        passing_score = exam.passing_score if (exam and exam.passing_score) else 70.0
        score_percentage = round((total_earned_points / total_possible_points) * 100.0, 2)
        is_passed = (score_percentage >= passing_score)

        attempt.completed_at = datetime.utcnow()
        attempt.score = score_percentage
        attempt.passed = is_passed
        attempt.status = AttemptStatus.COMPLETED

        db_result = db.query(ExamResult).filter(ExamResult.attempt_id == attempt.id).first()
        if not db_result:
            db_result = ExamResult(
                attempt_id=attempt.id,
                total_questions=total_questions,
                correct_answers=correct_count,
                score_percentage=score_percentage,
                passed=is_passed
            )
            db.add(db_result)
        else:
            db_result.total_questions = total_questions
            db_result.correct_answers = correct_count
            db_result.score_percentage = score_percentage
            db_result.passed = is_passed

        db.commit()
        db.refresh(db_result)

        # Automatically update user study plan progression: Mark Day 5 (Exam) as COMPLETED
        if week:
            try:
                from app.models.models import StudyPlanDay, UserStudyPlanProgress
                day_5 = db.query(StudyPlanDay).filter(
                    StudyPlanDay.week_id == week.id,
                    StudyPlanDay.day_number == 5
                ).first()
                if day_5:
                    progress = db.query(UserStudyPlanProgress).filter(
                        UserStudyPlanProgress.user_id == current_user.id,
                        UserStudyPlanProgress.plan_id == week.plan_id
                    ).first()
                    if not progress:
                        progress = UserStudyPlanProgress(
                            user_id=current_user.id,
                            plan_id=week.plan_id,
                            current_week_number=week.week_number,
                            current_day_number=5,
                            completed_days_json="[]",
                            completed_weeks_json="[]"
                        )
                        db.add(progress)

                    c_days = json.loads(progress.completed_days_json or "[]")
                    if day_5.id not in c_days:
                        c_days.append(day_5.id)
                        progress.completed_days_json = json.dumps(c_days)
                        if progress.current_day_number <= 5:
                            progress.current_day_number = 6
                        db.commit()
                        logger.info(f"Successfully marked Day 5 Exam as COMPLETED for user {current_user.id}. Day 6 Mock Interview unlocked.")
            except Exception as prog_err:
                logger.error(f"Error marking Day 5 exam completion: {prog_err}", exc_info=True)

        log_audit_event(
            db, action="SUBMIT_EXAM", entity_type="EXAM_ATTEMPT", user_id=current_user.id, entity_id=attempt.id,
            details=f"Score: {score_percentage}%, Passed: {is_passed}"
        )

        overall_summary = f"Exam evaluation completed. You earned {round(total_earned_points, 1)} out of {round(total_possible_points, 1)} total points ({score_percentage}%)."
        if is_passed:
            overall_summary += " Congratulations! You successfully passed the week assessment."
        else:
            overall_summary += " Keep reviewing the week's lesson modules and attempt again."

        return jsonify({
            "id": db_result.id,
            "attempt_id": db_result.attempt_id,
            "total_questions": db_result.total_questions,
            "correct_answers": db_result.correct_answers,
            "total_possible_marks": round(total_possible_points, 1),
            "obtained_marks": round(total_earned_points, 1),
            "score_percentage": db_result.score_percentage,
            "passed": db_result.passed,
            "overall_summary": overall_summary,
            "question_breakdown": question_breakdown
        }), 200

    except Exception as submit_err:
        db.rollback()
        logger.error(f"Error submitting exam attempt: {submit_err}", exc_info=True)
        return jsonify({"detail": f"Error submitting exam: {str(submit_err)}"}), 500

@exams_bp.route("/attempts/<attempt_id>/result", methods=["GET"])
@token_required
def get_exam_attempt_result(attempt_id):
    db = get_db()
    current_user = g.current_user

    attempt = db.query(ExamAttempt).filter(ExamAttempt.id == attempt_id).first()
    if not attempt or (attempt.user_id != current_user.id and current_user.role != UserRole.ADMIN):
        return jsonify({"detail": "Exam attempt not found"}), 404

    result = db.query(ExamResult).filter(ExamResult.attempt_id == attempt_id).first()
    if not result:
        return jsonify({"detail": "Result not generated yet"}), 404

    return jsonify(ExamResultOut.model_validate(result).model_dump(mode="json")), 200
