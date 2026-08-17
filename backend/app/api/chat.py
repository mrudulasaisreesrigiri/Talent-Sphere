import json
import logging
from flask import Blueprint, request, jsonify, g, Response, stream_with_context
from app.core.deps import token_required, get_db
from app.core.database import SessionLocal
from app.models.models import ChatHistory, Document, UserStudyPlanProgress, StudyPlanDay, StudyPlan, StudyPlanWeek
from app.schemas.schemas import ChatMessageOut, Citation
from app.services.vector_service import vector_service
from app.services.ai_service import ai_service
from app.services.voice_exam_workflow import handle_voice_exam_workflow
from app.services.voice_interview_workflow import handle_voice_interview_workflow
from app.utils.logger import log_audit_event

logger = logging.getLogger(__name__)

chat_bp = Blueprint("chat", __name__, url_prefix="/chat")

def get_user_study_plan_rag_context(db, current_user, raw_chunks: list):
    """
    Filters RAG vector chunks and compiles Study Plan curriculum metadata based on the
    current user's individual Study Plan completion status (UserStudyPlanProgress).

    Rules enforced:
    1. Chunks from Locked Study Plan PDFs are COMPLETELY FILTERED OUT before reaching the LLM.
    2. Chunks from Unlocked Study Plan PDFs are retained and labeled with 'Week X, Day Y – [Title]'.
    3. Standalone uploaded documents are retained normally.
    4. Compiles unlocked_study_days and locked_study_days curriculum metadata so the chatbot
       knows the titles/topics of locked days to direct users to unlock them.
    """
    # 1. Gather all day IDs marked as completed by this specific user
    progress_records = db.query(UserStudyPlanProgress).filter(
        UserStudyPlanProgress.user_id == current_user.id
    ).all()

    completed_day_ids = set()
    active_week_num = 1
    active_day_num = 1

    for prog in progress_records:
        if prog.current_week_number:
            active_week_num = prog.current_week_number
        if prog.current_day_number:
            active_day_num = prog.current_day_number
        if prog.completed_days_json:
            try:
                days_list = json.loads(prog.completed_days_json)
                if isinstance(days_list, list):
                    completed_day_ids.update(str(d) for d in days_list)
            except Exception:
                pass

    # 2. Query StudyPlanDay records for active study plan(s)
    user_plan_ids = [prog.plan_id for prog in progress_records if prog.plan_id]
    if user_plan_ids:
        active_plan_ids = user_plan_ids
    else:
        active_plans = db.query(StudyPlan).filter(StudyPlan.status == "ACTIVE").order_by(StudyPlan.created_at.desc()).all()
        if not active_plans:
            active_plans = db.query(StudyPlan).order_by(StudyPlan.created_at.desc()).limit(1).all()
        active_plan_ids = [p.id for p in active_plans]

    # All days across all plans for vector mapping
    all_days = db.query(StudyPlanDay).all()
    study_day_map = {str(d.id): d for d in all_days}
    week_map = {str(w.id): w for w in db.query(StudyPlanWeek).all()}

    # Current active plan days for curriculum metadata
    current_plan_days = (
        db.query(StudyPlanDay)
        .join(StudyPlanWeek, StudyPlanDay.week_id == StudyPlanWeek.id)
        .filter(StudyPlanWeek.plan_id.in_(active_plan_ids))
        .all()
    ) if active_plan_ids else all_days

    # Map document_id -> StudyPlanDay
    doc_to_day_map = {}
    for d in all_days:
        if d.document_id:
            doc_to_day_map[str(d.document_id)] = d

    # Also map Document records where is_study_plan_doc == True
    study_docs = db.query(Document).filter(Document.is_study_plan_doc == True).all()
    for doc in study_docs:
        if doc.study_plan_day_id and str(doc.study_plan_day_id) in study_day_map:
            doc_to_day_map[str(doc.id)] = study_day_map[str(doc.study_plan_day_id)]

    unlocked_days_metadata = []
    locked_days_metadata = []
    seen_day_keys = set()

    for d in current_plan_days:
        week_obj = week_map.get(str(d.week_id))
        w_num = week_obj.week_number if week_obj else 1
        day_key = f"{w_num}_{d.day_number}"

        title = (d.pdf_title or d.lesson_title or d.title or f"Day {d.day_number}").strip()
        pdf_title = (d.pdf_title or f"{title}.pdf" if not title.endswith(".pdf") else title).strip()
        day_label = f"Week {w_num}, Day {d.day_number} – {title}"

        # Only include days with actual lesson/PDF content (Days 1..4)
        if d.day_number > 4 or day_key in seen_day_keys:
            continue
        seen_day_keys.add(day_key)

        item = {
            "day_id": str(d.id),
            "week_id": str(d.week_id),
            "week_number": w_num,
            "day_number": d.day_number,
            "title": title,
            "pdf_title": pdf_title,
            "label": day_label,
            "topic": d.topic or title,
            "document_id": str(d.document_id) if d.document_id else None
        }

        # Check if unlocked: completed or currently reachable
        is_day_unlocked = (
            str(d.id) in completed_day_ids or
            (w_num < active_week_num) or
            (w_num == active_week_num and d.day_number <= active_day_num) or
            (w_num == 1 and d.day_number == 1)
        )

        if is_day_unlocked:
            unlocked_days_metadata.append(item)
        else:
            locked_days_metadata.append(item)

    unlocked_days_metadata.sort(key=lambda x: (x["week_number"], x["day_number"]))
    locked_days_metadata.sort(key=lambda x: (x["week_number"], x["day_number"]))
    unlocked_day_ids = {d["day_id"] for d in unlocked_days_metadata}

    # 3. Filter vector chunks: KEEP only verified standalone docs OR verified unlocked study plan docs
    filtered_chunks = []
    for chunk in raw_chunks:
        doc_id = str(chunk.get("document_id") or "")
        doc_title = str(chunk.get("document_title") or "")
        is_sp_vector = (
            doc_id.startswith("sp_day_") or
            bool(chunk.get("day_id")) or
            bool(chunk.get("week_id")) or
            bool(chunk.get("plan_id")) or
            doc_title.startswith("Day ") or
            doc_title.startswith("Week ")
        )

        matched_day = None
        if doc_id.startswith("sp_day_"):
            raw_day_id = doc_id.replace("sp_day_", "")
            matched_day = study_day_map.get(raw_day_id)
        elif doc_id in doc_to_day_map:
            matched_day = doc_to_day_map[doc_id]
        elif chunk.get("day_id") and str(chunk.get("day_id")) in study_day_map:
            matched_day = study_day_map[str(chunk.get("day_id"))]

        if matched_day:
            # Check if this day belongs to user's active study plan
            week_obj = week_map.get(str(matched_day.week_id))
            day_plan_id = str(week_obj.plan_id) if week_obj else None
            if active_plan_ids and day_plan_id and day_plan_id not in [str(pid) for pid in active_plan_ids]:
                # Chunk belongs to an inactive/unrelated study plan -> DROP
                continue

            # Chunk is definitely from user's active Study Plan
            is_unlocked = str(matched_day.id) in unlocked_day_ids or str(matched_day.id) in completed_day_ids
            if is_unlocked:
                w_num = week_obj.week_number if week_obj else 1
                title = (matched_day.pdf_title or matched_day.lesson_title or f"Day {matched_day.day_number}").strip()
                chunk["document_title"] = f"Week {w_num}, Day {matched_day.day_number} – {title}"
                chunk["is_study_plan"] = True
                chunk["week_number"] = w_num
                chunk["day_number"] = matched_day.day_number
                filtered_chunks.append(chunk)
            else:
                # User has NOT unlocked this day -> DROP chunk completely!
                continue
        elif is_sp_vector:
            # Stale/orphan study plan vector from previous test/deleted plan -> DROP!
            continue
        else:
            # Check standalone document in database
            doc = db.query(Document).filter(Document.id == doc_id).first()
            if not doc:
                # Orphan chunk not present in DB -> DROP
                continue

            if doc.is_study_plan_doc:
                if doc.study_plan_day_id and (str(doc.study_plan_day_id) in unlocked_day_ids or str(doc.study_plan_day_id) in completed_day_ids):
                    day_rec = study_day_map.get(str(doc.study_plan_day_id))
                    week_obj = week_map.get(str(day_rec.week_id)) if day_rec else None
                    w_num = week_obj.week_number if week_obj else 1
                    day_num = day_rec.day_number if day_rec else 1
                    title = (doc.title or f"Day {day_num}").strip()
                    chunk["document_title"] = f"Week {w_num}, Day {day_num} – {title}"
                    chunk["is_study_plan"] = True
                    chunk["week_number"] = w_num
                    chunk["day_number"] = day_num
                    filtered_chunks.append(chunk)
                else:
                    # Locked Study Plan document -> DROP
                    continue
            else:
                # Standalone uploaded document (Document Management)
                chunk["document_title"] = doc.title
                chunk["is_study_plan"] = False
                filtered_chunks.append(chunk)

    return filtered_chunks, unlocked_days_metadata, locked_days_metadata

@chat_bp.route("", methods=["POST"])
@token_required
def send_chat_message():
    """
    Standard non-streaming chat message route used by Chatbot and Voice Assistant.
    """
    db = get_db()
    current_user = g.current_user
    data = request.get_json() or {}

    user_message = data.get("message")
    session_id = data.get("session_id", "default")

    if not user_message or not user_message.strip():
        return jsonify({"detail": "message is required"}), 400

    clean_message = user_message.strip()
    logger.info(f"=== [CHAT API REQUEST] User='{current_user.email}', Session='{session_id}', Query='{clean_message}' ===")

    # 1. Check Voice Mock Interview workflow
    if session_id.startswith("mock_interview_"):
        is_handled, voice_response = handle_voice_interview_workflow(session_id, clean_message, user_id=current_user.id)
        if is_handled:
            user_msg = ChatHistory(user_id=current_user.id, session_id=session_id, role="user", message=clean_message)
            assistant_msg = ChatHistory(user_id=current_user.id, session_id=session_id, role="assistant", message=voice_response)
            db.add(user_msg)
            db.add(assistant_msg)
            db.commit()
            db.refresh(assistant_msg)

            return jsonify({
                "id": assistant_msg.id,
                "session_id": assistant_msg.session_id,
                "role": assistant_msg.role,
                "message": assistant_msg.message,
                "citations": [],
                "created_at": assistant_msg.created_at.isoformat()
            }), 200

    # 2. Check Exam Creation Workflow (Admin Only)
    from app.services.voice_exam_workflow import is_exam_creation_trigger, is_session_in_exam_workflow
    if is_exam_creation_trigger(clean_message) or is_session_in_exam_workflow(session_id) or session_id == "voice_session" or session_id.startswith("voice"):
        is_handled, exam_response = handle_voice_exam_workflow(session_id, clean_message, current_user.id, current_user.role)
        if is_handled:
            user_msg = ChatHistory(user_id=current_user.id, session_id=session_id, role="user", message=clean_message)
            assistant_msg = ChatHistory(user_id=current_user.id, session_id=session_id, role="assistant", message=exam_response)
            db.add(user_msg)
            db.add(assistant_msg)
            db.commit()
            db.refresh(assistant_msg)

            return jsonify({
                "id": assistant_msg.id,
                "session_id": assistant_msg.session_id,
                "role": assistant_msg.role,
                "message": assistant_msg.message,
                "citations": [],
                "created_at": assistant_msg.created_at.isoformat()
            }), 200

    # Retrieve multi-turn conversation memory history for regular chat
    past_messages_db = db.query(ChatHistory).filter(
        ChatHistory.user_id == current_user.id,
        ChatHistory.session_id == session_id
    ).order_by(ChatHistory.created_at.asc()).all()

    conversation_history = [
        {"role": m.role, "message": m.message} for m in past_messages_db[-10:]
    ]

    # Save user message to ChatHistory
    user_msg = ChatHistory(
        user_id=current_user.id,
        session_id=session_id,
        role="user",
        message=clean_message
    )
    db.add(user_msg)
    db.commit()

    is_casual = ai_service.is_casual_message(clean_message)
    if is_casual:
        filtered_chunks = []
        unlocked_study_days = []
        locked_study_days = []
    else:
        # Step 1: Perform RAG Vector Search across uploaded PDF documents
        raw_retrieved_chunks = vector_service.search_similar(query=clean_message, top_k=30)

        # Step 2: Filter chunks by user's Study Plan progress & gather curriculum metadata
        filtered_chunks, unlocked_study_days, locked_study_days = get_user_study_plan_rag_context(
            db, current_user, raw_retrieved_chunks
        )
        filtered_chunks = filtered_chunks[:8]

    # Step 3: Pass RAG context, conversation memory & Study Plan metadata to AIService
    answer_text, citations = ai_service.generate_response(
        user_query=clean_message,
        retrieved_chunks=filtered_chunks,
        conversation_history=conversation_history,
        unlocked_study_days=unlocked_study_days,
        locked_study_days=locked_study_days
    )

    citations_json = json.dumps(citations) if citations else None

    assistant_msg = ChatHistory(
        user_id=current_user.id,
        session_id=session_id,
        role="assistant",
        message=answer_text,
        citations=citations_json
    )
    db.add(assistant_msg)
    db.commit()
    db.refresh(assistant_msg)

    log_audit_event(
        db, action="AI_CHAT_QUERY", entity_type="CHAT", user_id=current_user.id, details=f"Query: {clean_message[:50]}"
    )

    cit_objects = [Citation(**c).model_dump(mode="json") for c in citations] if citations else []

    return jsonify({
        "id": assistant_msg.id,
        "session_id": assistant_msg.session_id,
        "role": assistant_msg.role,
        "message": assistant_msg.message,
        "citations": cit_objects,
        "created_at": assistant_msg.created_at.isoformat()
    }), 200

@chat_bp.route("/stream", methods=["POST"])
@token_required
def stream_chat_message():
    """
    Token-by-token Server-Sent Events (SSE) streaming chat route.
    """
    db = get_db()
    current_user = g.current_user
    current_user_id = current_user.id
    data = request.get_json() or {}

    user_message = data.get("message")
    session_id = data.get("session_id", "default")

    if not user_message or not user_message.strip():
        return jsonify({"detail": "message is required"}), 400

    clean_message = user_message.strip()
    logger.info(f"=== [CHAT STREAM API] User='{current_user.email}', Session='{session_id}', Query='{clean_message}' ===")

    # 1. Check Voice Mock Interview workflow
    if session_id.startswith("mock_interview_"):
        is_handled, voice_response = handle_voice_interview_workflow(session_id, clean_message, user_id=current_user.id)
        if is_handled:
            def generate_interview_sse():
                db_stream = SessionLocal()
                try:
                    user_msg = ChatHistory(user_id=current_user_id, session_id=session_id, role="user", message=clean_message)
                    assistant_msg = ChatHistory(user_id=current_user_id, session_id=session_id, role="assistant", message=voice_response)
                    db_stream.add(user_msg)
                    db_stream.add(assistant_msg)
                    db_stream.commit()
                    db_stream.refresh(assistant_msg)
                    msg_id = assistant_msg.id
                except Exception as e:
                    logger.error(f"Error saving interview chat history: {e}")
                    msg_id = None
                finally:
                    db_stream.close()

                words = voice_response.split(" ")
                for i, w in enumerate(words):
                    chunk_text = w if i == len(words) - 1 else w + " "
                    chunk_payload = json.dumps({"token": chunk_text, "done": False})
                    yield f"data: {chunk_payload}\n\n"

                final_payload = json.dumps({"token": "", "done": True, "id": msg_id, "citations": []})
                yield f"data: {final_payload}\n\n"

            return Response(stream_with_context(generate_interview_sse()), mimetype="text/event-stream")

    # 2. Check Exam Creation Workflow (Admin Only)
    from app.services.voice_exam_workflow import is_exam_creation_trigger, is_session_in_exam_workflow
    if is_exam_creation_trigger(clean_message) or is_session_in_exam_workflow(session_id) or session_id == "voice_session" or session_id.startswith("voice"):
        is_handled, exam_response = handle_voice_exam_workflow(session_id, clean_message, current_user_id, current_user.role)
        if is_handled:
            def generate_workflow_sse():
                db_stream = SessionLocal()
                try:
                    user_msg = ChatHistory(user_id=current_user_id, session_id=session_id, role="user", message=clean_message)
                    assistant_msg = ChatHistory(user_id=current_user_id, session_id=session_id, role="assistant", message=exam_response)
                    db_stream.add(user_msg)
                    db_stream.add(assistant_msg)
                    db_stream.commit()
                    db_stream.refresh(assistant_msg)
                    msg_id = assistant_msg.id
                except Exception as e:
                    logger.error(f"Error saving workflow chat history: {e}")
                    msg_id = None
                finally:
                    db_stream.close()

                # Stream out exam_response text in readable chunks
                words = exam_response.split(" ")
                for i, w in enumerate(words):
                    chunk_text = w if i == len(words) - 1 else w + " "
                    chunk_payload = json.dumps({"token": chunk_text, "done": False})
                    yield f"data: {chunk_payload}\n\n"

                final_payload = json.dumps({"token": "", "done": True, "id": msg_id, "citations": []})
                yield f"data: {final_payload}\n\n"

            return Response(stream_with_context(generate_workflow_sse()), mimetype="text/event-stream")

    # Retrieve multi-turn conversation memory history for regular chatbot/voice query
    past_messages_db = db.query(ChatHistory).filter(
        ChatHistory.user_id == current_user_id,
        ChatHistory.session_id == session_id
    ).order_by(ChatHistory.created_at.asc()).all()

    conversation_history = [
        {"role": m.role, "message": m.message} for m in past_messages_db[-10:]
    ]

    # Save user message
    user_msg = ChatHistory(
        user_id=current_user_id,
        session_id=session_id,
        role="user",
        message=clean_message
    )
    db.add(user_msg)
    db.commit()

    is_casual = ai_service.is_casual_message(clean_message)
    if is_casual:
        filtered_chunks = []
        unlocked_study_days = []
        locked_study_days = []
    else:
        # Step 1: Perform RAG Vector Similarity Search
        raw_retrieved_chunks = vector_service.search_similar(query=clean_message, top_k=15)

        # Step 2: Filter chunks by user's Study Plan progress & gather curriculum metadata
        filtered_chunks, unlocked_study_days, locked_study_days = get_user_study_plan_rag_context(
            db, current_user, raw_retrieved_chunks
        )
        filtered_chunks = filtered_chunks[:6]

    def generate_sse():
        full_tokens = []
        final_citations = []
        msg_id = None

        try:
            for token, citations in ai_service.generate_response_stream(
                user_query=clean_message,
                retrieved_chunks=filtered_chunks,
                conversation_history=conversation_history,
                unlocked_study_days=unlocked_study_days,
                locked_study_days=locked_study_days
            ):
                full_tokens.append(token)
                if citations:
                    final_citations = citations

                chunk_payload = json.dumps({
                    "token": token,
                    "done": False
                })
                yield f"data: {chunk_payload}\n\n"

            complete_text = "".join(full_tokens)
            citations_json = json.dumps(final_citations) if final_citations else None

            db_stream = SessionLocal()
            try:
                assistant_msg = ChatHistory(
                    user_id=current_user_id,
                    session_id=session_id,
                    role="assistant",
                    message=complete_text,
                    citations=citations_json
                )
                db_stream.add(assistant_msg)
                db_stream.commit()
                db_stream.refresh(assistant_msg)
                msg_id = assistant_msg.id
            except Exception as dberr:
                db_stream.rollback()
                logger.error(f"Error persisting streamed chat message: {dberr}")
            finally:
                db_stream.close()

            cit_objects = [Citation(**c).model_dump(mode="json") for c in final_citations] if final_citations else []

            final_payload = json.dumps({
                "token": "",
                "done": True,
                "id": msg_id,
                "citations": cit_objects
            })
            yield f"data: {final_payload}\n\n"

        except Exception as err:
            logger.error(f"Error in SSE streaming generator: {err}", exc_info=True)
            err_payload = json.dumps({"token": f"\n\n[Stream Error: {str(err)}]", "done": True})
            yield f"data: {err_payload}\n\n"

    return Response(stream_with_context(generate_sse()), mimetype="text/event-stream")

@chat_bp.route("/history", methods=["GET"])
@token_required
def get_chat_history():
    db = get_db()
    current_user = g.current_user
    session_id = request.args.get("session_id", default="default", type=str)
    search = request.args.get("search", default=None, type=str)

    query = db.query(ChatHistory).filter(
        ChatHistory.user_id == current_user.id,
        ChatHistory.session_id == session_id
    )
    if search:
        query = query.filter(ChatHistory.message.ilike(f"%{search}%"))

    messages = query.order_by(ChatHistory.created_at.asc()).all()
    results = []
    for m in messages:
        cits = []
        if m.citations:
            try:
                raw_cits = json.loads(m.citations)
                cits = [Citation(**c).model_dump(mode="json") for c in raw_cits]
            except Exception:
                pass

        results.append({
            "id": m.id,
            "session_id": m.session_id,
            "role": m.role,
            "message": m.message,
            "citations": cits,
            "created_at": m.created_at.isoformat()
        })
    return jsonify(results), 200

@chat_bp.route("/history", methods=["DELETE"])
@token_required
def clear_chat_history():
    """
    Permanently deletes chat history records for the authenticated user.
    If session_id is provided, deletes messages for that specific session.
    If session_id is omitted or 'all', permanently deletes all chat messages for this user.
    """
    db = get_db()
    current_user = g.current_user
    session_id = request.args.get("session_id", default=None, type=str)

    query = db.query(ChatHistory).filter(ChatHistory.user_id == current_user.id)
    
    if session_id and session_id.lower() != "all":
        query = query.filter(ChatHistory.session_id == session_id)
        deleted_count = query.delete(synchronize_session=False)
        db.commit()
        logger.info(f"User '{current_user.email}' permanently deleted {deleted_count} messages from session '{session_id}'.")
        return jsonify({
            "message": f"Successfully deleted {deleted_count} messages from session '{session_id}'",
            "deleted_count": deleted_count,
            "session_id": session_id
        }), 200
    else:
        deleted_count = query.delete(synchronize_session=False)
        db.commit()
        logger.info(f"User '{current_user.email}' permanently cleared all {deleted_count} chat messages across all sessions.")
        return jsonify({
            "message": f"Successfully cleared all {deleted_count} chat history records",
            "deleted_count": deleted_count
        }), 200

@chat_bp.route("/sessions", methods=["GET"])
@token_required
def get_chat_sessions():
    db = get_db()
    current_user = g.current_user

    sessions = db.query(ChatHistory.session_id).filter(
        ChatHistory.user_id == current_user.id
    ).distinct().all()
    
    session_list = [s[0] for s in sessions]
    if "default" not in session_list:
        session_list.insert(0, "default")
        
    return jsonify(session_list), 200

@chat_bp.route("/sessions/<session_id>", methods=["DELETE"])
@token_required
def delete_chat_session(session_id):
    """
    Permanently deletes all messages belonging to the given session_id for the logged-in user.
    """
    db = get_db()
    current_user = g.current_user

    deleted_count = db.query(ChatHistory).filter(
        ChatHistory.user_id == current_user.id,
        ChatHistory.session_id == session_id
    ).delete(synchronize_session=False)
    db.commit()
    logger.info(f"User '{current_user.email}' deleted chat session '{session_id}' ({deleted_count} records).")
    return jsonify({
        "message": f"Chat session '{session_id}' deleted successfully",
        "deleted_count": deleted_count,
        "session_id": session_id
    }), 200

@chat_bp.route("/clear", methods=["DELETE", "POST"])
@token_required
def clear_all_chat_history_alias():
    """
    Convenience alias to clear all chat history for the authenticated user.
    """
    return clear_chat_history()
