import logging
import json
import re
import hashlib
import random
from typing import Dict, Any, Tuple
from app.core.database import SessionLocal
from app.models.models import StudyPlanWeek, StudyPlan
from app.services.groq_service import GroqService
from app.services.vector_service import vector_service

logger = logging.getLogger(__name__)

# Global in-memory session store for Voice Mock Interviews
interview_sessions: Dict[str, Dict[str, Any]] = {}

# Exact 3 Predefined HR Questions
PREDEFINED_HR_QUESTIONS = [
    "Tell me about yourself.",
    "What are your strengths?",
    "What are your weaknesses?"
]

# Exact 4 Predefined Concept Questions for Week 1
WEEK_1_EXACT_CONCEPT_QUESTIONS = [
    "What is Artificial Intelligence?",
    "In what year did Alan Turing propose the Turing Test?",
    "What is Machine Learning?",
    "What are the applications of Artificial Intelligence?"
]


def _extract_content_grounded_interview_questions(lessons):
    """
    Parses key concepts, definitions, headers, and technical sentences directly from the 4 uploaded lesson texts.
    Generates 5 direct technical questions without ANY meta references like 'Day 1 concept' or 'Day 2'.
    """
    tech_questions = []
    
    for d in sorted(lessons, key=lambda x: x.day_number):
        content = (d.lesson_content or "").strip()
        t_title = (d.lesson_title or d.topic or "").strip()
        if t_title.lower().startswith("day "):
            t_title = f"Module {d.day_number}"
        
        headers = re.findall(r'#{1,4}\s*([^\n]+)', content)
        bolds = re.findall(r'\*\*([^*]+)\*\*', content)
        sentences = [s.strip() for s in re.split(r'[.\n]', content) if len(s.strip()) > 20 and not s.startswith('#')]
        
        target_concept = None
        if headers:
            target_concept = headers[0].strip()
        elif bolds:
            target_concept = bolds[0].strip()
        elif t_title and not t_title.lower().startswith("module "):
            target_concept = t_title
        
        if target_concept:
            tech_questions.append(f"What is {target_concept} and how does it function according to your lesson material?")
        elif sentences:
            sent = sentences[0]
            words = [w for w in re.findall(r'\b[A-Za-z]{4,}\b', sent) if w.lower() not in ['this', 'that', 'from', 'with', 'which', 'where', 'using', 'into', 'their', 'have', 'were', 'about', 'these']]
            term = words[0] if words else "the core technical topic"
            tech_questions.append(f"Explain how {term} operates based on your lesson content.")
        else:
            tech_questions.append(f"Explain the primary technical principle covered in {t_title or 'your lesson'}.")

    if len(lessons) >= 4:
        c1 = (lessons[0].lesson_title or "the first module").strip()
        c4 = (lessons[3].lesson_title or "the fourth module").strip()
        if c1.lower().startswith("day "): c1 = "the initial module"
        if c4.lower().startswith("day "): c4 = "the advanced module"
        tech_questions.append(f"What are the main technical connections between {c1} and {c4}?")
    else:
        tech_questions.append("What are the key real-world applications of the technical concepts covered across your lessons?")

    return tech_questions[:5]


def get_or_create_interview_session(session_id: str, week_id: str, user_id: str = None) -> Dict[str, Any]:
    if session_id in interview_sessions:
        session_state = interview_sessions[session_id]
        if user_id:
            session_state["user_id"] = user_id
        return session_state

    db = SessionLocal()
    try:
        week = db.query(StudyPlanWeek).filter(StudyPlanWeek.id == week_id).first()
        if not week:
            logger.error(f"StudyPlanWeek ID {week_id} not found.")
            return None

        plan = week.plan
        plan_title = plan.title if plan else "Study Plan"
        week_num = week.week_number

        hr_questions = list(PREDEFINED_HR_QUESTIONS)

        if week_num == 1:
            # Week 1 uses exact four concept questions in exact sequence
            tech_questions = list(WEEK_1_EXACT_CONCEPT_QUESTIONS)
        else:
            # Week 2+ reads lesson content and generates concept questions
            retrieved_chunks = vector_service.get_week_vectors(week.id)
            lessons = [d for d in week.days if d.has_lesson and d.day_number <= 4 and d.lesson_content and d.lesson_content.strip()]
            
            full_knowledge_base = ""
            for d in sorted(lessons, key=lambda x: x.day_number):
                full_knowledge_base += f"\n\n=== UPLOADED LESSON CONTENT DAY {d.day_number} ({d.lesson_title or d.topic}) ===\n{d.lesson_content.strip()}"

            if retrieved_chunks:
                for idx, chunk in enumerate(retrieved_chunks):
                    full_knowledge_base += f"\n\n--- [RETRIEVED VECTOR CHUNK #{idx+1} ({chunk.get('document_title')})] ---\n{chunk['content']}"

            prompt = f"""You are an expert AI Technical Interviewer conducting a weekly mock interview for '{plan_title}' - Week {week_num}.

CRITICAL INSTRUCTIONS FOR QUESTION GENERATION:
Read, study, and learn every paragraph, definition, concept, and technical term in all 4 days of content.

Generate 5 direct, specific technical interview questions that test the candidate's understanding of the concepts explained in the text.

STRICT RULES:
1. DO NOT use generic phrases like "What is the Day 1 concept?", "What is Day 2?", "What is covered in Week 1?", "What is the concept?", or "Based on Day 1...".
2. Ask direct technical questions.
3. Every question MUST be a standalone technical question asking directly about specific concepts present in the lesson content.
4. DO NOT ask generic meta questions.

COMPLETE UPLOADED LESSON CONTENT:
{full_knowledge_base}

Return ONLY raw JSON with key "technical_questions" containing a list of 5 question strings:
{{
  "technical_questions": [
    "Direct technical question 1...",
    "Direct technical question 2...",
    "Direct technical question 3...",
    "Direct technical question 4...",
    "Direct technical question 5..."
  ]
}}
"""
            tech_questions = []
            try:
                raw_res = GroqService.generate_response(prompt=prompt, system_prompt="You are a strict JSON generator. Return ONLY JSON.")
                match = re.search(r'\{.*\}', raw_res, re.DOTALL)
                if match:
                    data = json.loads(match.group(0))
                    tech_questions = data.get("technical_questions", [])
            except Exception as e:
                logger.error(f"Failed to generate technical interview questions via LLM: {e}")

            filtered_tech = []
            for q_str in tech_questions:
                if re.search(r'\b(day\s*\d|day\s*concept|week\s*\d\s*concept|module\s*\d)\b', q_str, re.IGNORECASE):
                    continue
                filtered_tech.append(q_str)
            
            if len(filtered_tech) < 5:
                fallback_qs = _extract_content_grounded_interview_questions(lessons)
                for fq in fallback_qs:
                    if len(filtered_tech) < 5 and fq not in filtered_tech:
                        filtered_tech.append(fq)
            
            tech_questions = filtered_tech[:5]

        # Combine 3 Predefined HR Questions + Concept Questions
        all_questions = hr_questions + tech_questions

        session_state = {
            "session_id": session_id,
            "week_id": week_id,
            "week_number": week_num,
            "plan_title": plan_title,
            "user_id": user_id,
            "step": 0, # Current question index
            "questions": all_questions,
            "user_answers": [],
            "evaluations": [], # [{question, answer, is_correct, feedback}]
            "completed": False
        }
        interview_sessions[session_id] = session_state
        return session_state
    finally:
        db.close()

def handle_voice_interview_workflow(session_id: str, user_message: str, user_id: str = None) -> Tuple[bool, str]:
    """
    Handles step-by-step Voice Mock Interview logic for session_id.startswith('mock_interview_').
    Returns (is_handled, voice_response_text).
    """
    if not session_id.startswith("mock_interview_"):
        return False, ""

    parts = session_id.split("mock_interview_")
    if len(parts) < 2 or not parts[1]:
        return False, ""

    week_id = parts[1]
    state = get_or_create_interview_session(session_id, week_id, user_id=user_id)
    if not state:
        return True, "Sorry, I could not find the details for this week's mock interview."

    if state.get("completed", False):
        return True, f"Your Week {state['week_number']} Mock Interview is already completed. Excellent job!"

    step = state["step"]
    questions = state["questions"]
    clean_msg = user_message.strip()

    # Initial Trigger Call (e.g. user clicks Day 6 or sends initial "start")
    if clean_msg.lower() in ["start", "begin", "hello", "hi", "init"] and step == 0 and len(state["user_answers"]) == 0:
        greeting = f"Welcome to Week {state['week_number']} AI Voice Mock Interview. Let's begin with our first HR question: {questions[0]}"
        return True, greeting

    # Evaluate user's answer to current question Q[step]
    current_q = questions[step]
    state["user_answers"].append(clean_msg)

    # RAG Retrieval for Technical Questions (step >= 3)
    retrieved_context = ""
    if step >= 3:
        try:
            chunks = vector_service.search_week_vectors(week_id, current_q, top_k=3)
            if chunks:
                for idx, ch in enumerate(chunks):
                    retrieved_context += f"\n--- [RETRIEVED CHUNK #{idx+1} ({ch.get('document_title')})] ---\n{ch['content']}"
        except Exception as v_err:
            logger.error(f"Error retrieving ChromaDB chunks for interview evaluation: {v_err}")

    # Evaluate answer using LLM
    eval_prompt = f"""You are an AI Technical Interviewer evaluating a candidate's voice answer.

LESSON CONTENT FROM KNOWLEDGE BASE:
{retrieved_context if retrieved_context else "N/A (HR Question)"}

INTERVIEW QUESTION: "{current_q}"
CANDIDATE ANSWER: "{clean_msg}"

EVALUATION INSTRUCTIONS:
- Compare the candidate's answer with the lesson content above.
- If correct: Appreciate the user with a short positive response highlighting what they explained well.
- If partially correct: Acknowledge what was correct, then explain what key detail was missing.
- If incorrect: Politely explain the correct answer.
- DO NOT simply say "Correct" or "Wrong". Give constructive, conversational 1-2 sentence feedback.

Return ONLY raw JSON:
{{
  "is_correct": true,
  "feedback": "Conversational 1-2 sentence feedback..."
}}
"""
    is_correct = True
    feedback_sentence = "Thank you for your answer."
    try:
        raw_eval = GroqService.generate_response(prompt=eval_prompt, system_prompt="You are a strict JSON evaluator. Return ONLY JSON.")
        match = re.search(r'\{.*\}', raw_eval, re.DOTALL)
        if match:
            data = json.loads(match.group(0))
            is_correct = data.get("is_correct", True)
            feedback_sentence = data.get("feedback", feedback_sentence)
    except Exception as e:
        logger.error(f"Error evaluating answer: {e}")

    state["evaluations"].append({
        "question": current_q,
        "answer": clean_msg,
        "is_correct": is_correct,
        "feedback": feedback_sentence
    })

    # Move to next question
    state["step"] += 1
    next_step = state["step"]

    # Check if there are more questions
    if next_step < len(questions):
        next_q = questions[next_step]
        if next_step == 3:
            # Transition from HR to Week Concept questions
            voice_text = f"{feedback_sentence} Thank you! Now let's transition to Week {state['week_number']} Concept Questions. Question 1: {next_q}"
        elif next_step > 3:
            q_num = next_step - 2
            voice_text = f"{feedback_sentence} Question {q_num}: {next_q}"
        else:
            voice_text = f"{feedback_sentence} Next HR question: {next_q}"
        return True, voice_text

    # All questions completed! Calculate final scores & overall feedback
    state["completed"] = True
    evals = state["evaluations"]

    # Mark Day 6 as completed in user progress DB & unlock Week 2
    db = SessionLocal()
    try:
        from app.models.models import StudyPlanDay, UserStudyPlanProgress
        day6 = db.query(StudyPlanDay).filter(
            StudyPlanDay.week_id == week_id,
            StudyPlanDay.day_number == 6
        ).first()

        if day6:
            plan_id = day6.week.plan_id if day6.week else None
            uid = state.get("user_id") or user_id
            if uid and plan_id:
                prog = db.query(UserStudyPlanProgress).filter(
                    UserStudyPlanProgress.user_id == uid,
                    UserStudyPlanProgress.plan_id == plan_id
                ).first()
                if not prog:
                    prog = UserStudyPlanProgress(
                        user_id=uid,
                        plan_id=plan_id,
                        current_week_number=state["week_number"],
                        current_day_number=6,
                        completed_days_json="[]",
                        completed_weeks_json="[]"
                    )
                    db.add(prog)

                c_days = json.loads(prog.completed_days_json or "[]")
                c_weeks = json.loads(prog.completed_weeks_json or "[]")
                if day6.id not in c_days:
                    c_days.append(day6.id)
                if week_id not in c_weeks:
                    c_weeks.append(week_id)

                prog.completed_days_json = json.dumps(c_days)
                prog.completed_weeks_json = json.dumps(c_weeks)
                prog.current_week_number = min(6, state["week_number"] + 1)
                prog.current_day_number = 1
                db.commit()
                logger.info(f"Successfully marked Day 6 Interview & Week {week_id} as COMPLETED for user {uid}. Next week unlocked.")
    except Exception as exc:
        logger.error(f"Failed to auto-advance progression on interview completion: {exc}")
    finally:
        db.close()

    total_concept_q = len(questions) - 3
    correct_count = sum(1 for ev in evals if ev.get("is_correct", True))
    tech_correct = sum(1 for ev in evals[3:] if ev.get("is_correct", True))

    knowledge_score = min(100, int((tech_correct / float(total_concept_q)) * 100))
    comm_score = min(100, int(85 + (correct_count * 2)))
    conf_score = min(100, int(80 + (correct_count * 2.5)))

    overall_feedback = f"Outstanding effort! You successfully answered all questions for Week {state['week_number']}. You demonstrated strong communication and solid technical grasp of the curriculum."

    final_response = f"""{feedback_sentence}

Congratulations! Week {state['week_number']} Mock Interview Completed.

Scores:
- Knowledge Score: {knowledge_score}%
- Communication Score: {comm_score}%
- Confidence Score: {conf_score}%

Overall Feedback: {overall_feedback}

Interview Completed."""

    return True, final_response
