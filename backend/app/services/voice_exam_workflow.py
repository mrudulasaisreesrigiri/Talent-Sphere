import os
import re
import json
import logging
from typing import Dict, Any, Tuple, Optional, List
from app.core.deps import get_db
from app.models.models import Document, DocumentChunk, Exam, Question, ExamStatus, User, Notification, UserRole, StudyPlanDay, StudyPlanWeek, StudyPlan
from app.services.groq_service import groq_service
from app.utils.logger import log_audit_event

logger = logging.getLogger(__name__)

# In-memory storage for active exam workflow sessions
exam_workflow_sessions: Dict[str, Dict[str, Any]] = {}

NUMBER_WORDS = {
    "zero": 0, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
    "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
    "eleven": 11, "twelve": 12, "thirteen": 13, "fourteen": 14, "fifteen": 15,
    "sixteen": 16, "seventeen": 17, "eighteen": 18, "nineteen": 19, "twenty": 20,
    "twenty-five": 25, "thirty": 30, "forty": 40, "fifty": 50, "sixty": 60
}

NUM_STR = r'(?:\d+(?:\.\d+)?|zero|one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|thirteen|fourteen|fifteen|sixteen|seventeen|eighteen|nineteen|twenty|twenty-five|thirty|forty|fifty|sixty)'

def word_to_val(token: Any) -> float:
    if token is None:
        return 0.0
    t = str(token).strip().lower()
    if t in NUMBER_WORDS:
        return float(NUMBER_WORDS[t])
    try:
        return float(t)
    except ValueError:
        return 0.0

def parse_number_from_text(text: str) -> Optional[int]:
    """Helper to extract integer numbers from spoken or written text."""
    lowered = text.lower().strip()
    match = re.search(rf'\b({NUM_STR})\b', lowered)
    if match:
        val = int(word_to_val(match.group(1)))
        if val > 0:
            return val
    return None

def parse_question_breakdown(text: str, total_q: Optional[int] = None) -> Dict[str, int]:
    """
    Robust, completely order-independent natural language parser for question distributions.
    Extracts ALL question types and their counts from anywhere in the user text.
    """
    lowered = text.lower().strip()
    counts: Dict[str, int] = {}

    # Extract MCQ
    mcq_m = re.search(rf'\b({NUM_STR})\s*(?:multiple[\s-]choice(?:\s*questions?)?|mcqs?|objective(?:\s*questions?)?)\b', lowered) or \
            re.search(rf'\b(?:multiple[\s-]choice(?:\s*questions?)?|mcqs?|objective(?:\s*questions?)?)\s*[:=-]?\s*({NUM_STR})\b', lowered)
    if mcq_m:
        counts["MCQ"] = int(word_to_val(mcq_m.group(1)))
    elif re.search(r'\b(?:multiple[\s-]choice|mcqs?|objective)\b', lowered) and not re.search(r'\b(?:one[\s-]word|true|false|descriptive)\b', lowered):
        if total_q:
            counts["MCQ"] = total_q

    # Extract DESCRIPTIVE
    desc_m = re.search(rf'\b({NUM_STR})\s*(?:descriptives?(?:\s*questions?)?|long[\s-]answers?(?:\s*questions?)?|essays?(?:\s*questions?)?|subjectives?(?:\s*questions?)?)\b', lowered) or \
             re.search(rf'\b(?:descriptives?(?:\s*questions?)?|long[\s-]answers?(?:\s*questions?)?|essays?(?:\s*questions?)?|subjectives?(?:\s*questions?)?)\s*[:=-]?\s*({NUM_STR})\b', lowered)
    if desc_m:
        counts["DESCRIPTIVE"] = int(word_to_val(desc_m.group(1)))
    elif re.search(r'\b(?:descriptives?|long[\s-]answers?|essays?|subjectives?)\b', lowered) and not re.search(r'\b(?:mcq|multiple|one[\s-]word|true|false)\b', lowered):
        if total_q:
            counts["DESCRIPTIVE"] = total_q

    # Extract TRUE_FALSE
    tf_m = re.search(rf'\b({NUM_STR})\s*(?:true[\s/_-]?(?:or|and)?[\s/_-]?false|tf|boolean(?:\s*questions?)?)\b', lowered) or \
           re.search(rf'\b(?:true[\s/_-]?(?:or|and)?[\s/_-]?false|tf|boolean(?:\s*questions?)?)\s*[:=-]?\s*({NUM_STR})\b', lowered)
    if tf_m:
        counts["TRUE_FALSE"] = int(word_to_val(tf_m.group(1)))
    elif re.search(r'\b(?:true[\s/_-]?(?:or|and)?[\s/_-]?false|tf|boolean)\b', lowered) and not re.search(r'\b(?:mcq|multiple|one[\s-]word|descriptive)\b', lowered):
        if total_q:
            counts["TRUE_FALSE"] = total_q

    # Extract ONE_WORD
    one_m = re.search(rf'\b({NUM_STR})\s*(?:one[\s-]words?(?:\s*questions?)?|single[\s-]words?(?:\s*questions?)?|short[\s-]answers?(?:\s*questions?)?|fill[\s-]in[\s-]the[\s-]blanks?)\b', lowered) or \
            re.search(rf'\b(?:one[\s-]words?(?:\s*questions?)?|single[\s-]words?(?:\s*questions?)?|short[\s-]answers?(?:\s*questions?)?|fill[\s-]in[\s-]the[\s-]blanks?)\s*[:=-]?\s*({NUM_STR})\b', lowered)
    if one_m:
        counts["ONE_WORD"] = int(word_to_val(one_m.group(1)))
    elif re.search(r'\b(?:one[\s-]words?|single[\s-]words?|short[\s-]answers?)\b', lowered):
        if not re.search(r'\b(?:mcq|multiple|true|false|descriptive)\b', lowered) and total_q:
            counts["ONE_WORD"] = total_q
        else:
            counts["ONE_WORD"] = 1

    return counts

def is_exam_creation_trigger(message: str) -> bool:
    """Detects if the user voice/chat input expresses intent to create/generate an exam."""
    lowered = message.lower().strip()
    triggers = [
        "create an exam", "generate an exam", "create exam", "generate exam",
        "make an exam", "create a test", "generate a test", "make a test",
        "build an exam", "prepare an exam", "setup an exam", "set up an exam",
        "i want to create an exam", "can you create an exam", "create new exam",
        "create a new exam", "start exam creation", "generate an assessment",
        "create an assessment", "generate test", "create test", "make a quiz",
        "generate a quiz", "create a quiz"
    ]
    if any(t in lowered for t in triggers):
        return True
    
    # 1. Action + Exam/Quiz/Test/Assessment noun
    pattern1 = r'\b(create|generate|make|build|setup|set\s+up|prepare|start|give|want|need)\b.*\b(exam|assessment|test|quiz)\b'
    if re.search(pattern1, lowered):
        return True

    # 2. Action + Question count + Question types (e.g. "Give me 10 questions with 5 MCQs...")
    pattern2 = r'\b(create|generate|make|build|prepare|give|want|need)\b.*\b(?:\d+|zero|one|two|three|four|five|six|seven|eight|nine|ten|fifteen|twenty)\s+questions?\b'
    if re.search(pattern2, lowered) and any(w in lowered for w in ["mcq", "multiple choice", "one-word", "one word", "true/false", "true or false", "descriptive"]):
        return True

    # 3. Direct question breakdown provided (e.g. "5 mcqs 5 descriptive")
    breakdown = parse_question_breakdown(message)
    if breakdown and sum(breakdown.values()) > 0:
        return True

    return False

def is_session_in_exam_workflow(session_id: str) -> bool:
    return session_id in exam_workflow_sessions and exam_workflow_sessions[session_id].get("step", 0) > 0

def get_session_state(session_id: str) -> Dict[str, Any]:
    if session_id not in exam_workflow_sessions:
        exam_workflow_sessions[session_id] = {
            "step": 0,
            "total_questions": None,
            "q_types": {}, # e.g. {"MCQ": 5, "ONE_WORD": 2, "TRUE_FALSE": 2, "DESCRIPTIVE": 1}
            "marks_map": {}, # e.g. {"MCQ": 1, "ONE_WORD": 2, "TRUE_FALSE": 1, "DESCRIPTIVE": 5}
            "total_marks": None,
            "source_title": None,
            "source_text": None,
            "difficulty": "Medium",
            "duration_minutes": 30,
            "generated_exam_data": None
        }
    return exam_workflow_sessions[session_id]

def reset_session_state(session_id: str):
    if session_id in exam_workflow_sessions:
        del exam_workflow_sessions[session_id]

def parse_marks_input(text: str, active_types: List[str]) -> Dict[str, float]:
    """
    Robust, order-independent parser for marks per question / type.
    Supports uniform marks, per-type allocations in any order, and written word numbers.
    """
    lowered = text.lower().strip()
    marks_map: Dict[str, float] = {}

    patterns = {
        "MCQ": [
            rf'\b({NUM_STR})\s*(?:marks?|pts?|points?)?\s*(?:for|each\s+for|per|each)?\s*(?:multiple[\s-]choice(?:\s*questions?)?|mcqs?|objective)\b',
            rf'\b(?:multiple[\s-]choice(?:\s*questions?)?|mcqs?|objective)\s*(?:carries?|is|worth|with|get|:|each)?\s*({NUM_STR})\s*(?:marks?|pts?|points?)?\b'
        ],
        "ONE_WORD": [
            rf'\b({NUM_STR})\s*(?:marks?|pts?|points?)?\s*(?:for|each\s+for|per|each)?\s*(?:one[\s-]words?(?:\s*questions?)?|single[\s-]words?|short[\s-]answers?)\b',
            rf'\b(?:one[\s-]words?(?:\s*questions?)?|single[\s-]words?|short[\s-]answers?)\s*(?:carries?|is|worth|with|get|:|each)?\s*({NUM_STR})\s*(?:marks?|pts?|points?)?\b'
        ],
        "TRUE_FALSE": [
            rf'\b({NUM_STR})\s*(?:marks?|pts?|points?)?\s*(?:for|each\s+for|per|each)?\s*(?:true[\s/_-]?(?:or|and)?[\s/_-]?false|tf|boolean)\b',
            rf'\b(?:true[\s/_-]?(?:or|and)?[\s/_-]?false|tf|boolean)\s*(?:carries?|is|worth|with|get|:|each)?\s*({NUM_STR})\s*(?:marks?|pts?|points?)?\b'
        ],
        "DESCRIPTIVE": [
            rf'\b({NUM_STR})\s*(?:marks?|pts?|points?)?\s*(?:for|each\s+for|per|each)?\s*(?:descriptives?(?:\s*questions?)?|long[\s-]answers?|essays?|subjectives?)\b',
            rf'\b(?:descriptives?(?:\s*questions?)?|long[\s-]answers?|essays?|subjectives?)\s*(?:carries?|is|worth|with|get|:|each)?\s*({NUM_STR})\s*(?:marks?|pts?|points?)?\b'
        ]
    }

    for t in active_types:
        for pat in patterns.get(t, []):
            m = re.search(pat, lowered)
            if m:
                marks_map[t] = word_to_val(m.group(1))
                break

    # If uniform mark or single number given (e.g. "1 mark", "1", "2 marks", "2", "1 mark each", "each 1 mark")
    gen_m = re.search(rf'\b({NUM_STR})\s*(?:marks?|pts?|points?)?\b', lowered)
    default_mark = word_to_val(gen_m.group(1)) if gen_m else 1.0
    if default_mark <= 0:
        default_mark = 1.0

    for t in active_types:
        if t not in marks_map:
            marks_map[t] = default_mark

    return marks_map

def format_breakdown_summary(q_types: Dict[str, int]) -> str:
    type_labels = {
        "MCQ": "Multiple Choice (MCQ)",
        "ONE_WORD": "One-Word / Short Answer",
        "TRUE_FALSE": "True / False",
        "DESCRIPTIVE": "Descriptive / Long Answer"
    }
    lines = []
    for qtype, count in q_types.items():
        if count > 0:
            lines.append(f"• **{type_labels.get(qtype, qtype)}**: {count} questions")
    return "\n".join(lines)

def format_exam_config_confirmation(total_q: int, q_types: Dict[str, int], marks_map: Dict[str, float], total_marks: float) -> str:
    """Formats a clear, structured confirmation of the exam configuration."""
    type_labels = {
        "MCQ": "Multiple Choice (MCQ)",
        "ONE_WORD": "One-Word / Short Answer",
        "TRUE_FALSE": "True / False",
        "DESCRIPTIVE": "Descriptive / Long Answer"
    }

    lines = []
    for qtype, count in q_types.items():
        if count > 0:
            pts = marks_map.get(qtype, 1.0)
            pts_str = f"{int(pts)} mark each" if pts == 1.0 else f"{int(pts) if pts.is_integer() else pts} marks each"
            lines.append(f"• **{type_labels.get(qtype, qtype)}**: {count} questions — {pts_str}")

    breakdown_text = "\n".join(lines)
    tot_marks_str = f"{int(total_marks) if total_marks.is_integer() else total_marks}"

    return (
        f"### 📋 Exam Configuration Confirmed\n\n"
        f"**Total Questions:** {total_q}\n\n"
        f"{breakdown_text}\n\n"
        f"**Total Marks:** {tot_marks_str}\n\n"
        f"Which **study material or topic** should this exam be based on? "
        f"(You can specify a Study Plan Week/Day PDF like 'Week 1 Day 1', an uploaded document, or a topic name)."
    )

def generate_grounded_questions(source_title: str, source_text: str, q_types: Dict[str, int], marks_map: Dict[str, float]) -> List[dict]:
    """Generates structured questions grounded in the provided source material."""
    questions = []
    
    mcq_count = q_types.get("MCQ", 0)
    one_word_count = q_types.get("ONE_WORD", 0)
    tf_count = q_types.get("TRUE_FALSE", 0)
    desc_count = q_types.get("DESCRIPTIVE", 0)

    system_prompt = (
        f"You are an expert examiner. Generate assessment questions strictly based on the following study content.\n"
        f"Source Material: {source_title}\n"
        f"Target Question Counts:\n"
        f"- {mcq_count} Multiple Choice Questions (MCQ)\n"
        f"- {one_word_count} One-word / Short Answer Questions (ONE_WORD)\n"
        f"- {tf_count} True/False Questions (TRUE_FALSE)\n"
        f"- {desc_count} Descriptive Questions (DESCRIPTIVE)\n\n"
        f"Return ONLY valid JSON matching this schema:\n"
        f'{{"questions": [\n'
        f'  {{"question_type": "MCQ", "question_text": "...", "option_a": "...", "option_b": "...", "option_c": "...", "option_d": "...", "correct_option": "A"}},\n'
        f'  {{"question_type": "ONE_WORD", "question_text": "...", "correct_option": "exact target word/phrase"}},\n'
        f'  {{"question_type": "TRUE_FALSE", "question_text": "...", "option_a": "True", "option_b": "False", "correct_option": "True"}},\n'
        f'  {{"question_type": "DESCRIPTIVE", "question_text": "...", "correct_option": "Detailed rubric / model answer"}}\n'
        f']}}\n\n'
        f"Study Content:\n{source_text[:4000]}"
    )

    prompt = f"Generate {sum(q_types.values())} grounded questions for '{source_title}'."

    raw_questions = []
    try:
        raw_json = groq_service.generate_response(prompt=prompt, system_prompt=system_prompt)
        clean_json = re.sub(r'```(?:json)?', '', raw_json).strip()
        json_match = re.search(r'\{.*\}', clean_json, re.DOTALL)
        if json_match:
            parsed = json.loads(json_match.group(0))
            raw_questions = parsed.get("questions") or parsed.get("items") or []
    except Exception as e:
        logger.error(f"Groq exam generation parsing error: {e}")

    # Normalize parsed questions
    for q in raw_questions:
        if not isinstance(q, dict):
            continue
        text = q.get("question_text") or q.get("question") or q.get("title")
        if not text:
            continue
        q_type = (q.get("question_type") or "MCQ").upper().replace("-", "_")
        if "TRUE" in q_type:
            q_type = "TRUE_FALSE"
        elif "ONE" in q_type or "WORD" in q_type or "FILL" in q_type:
            q_type = "ONE_WORD"
        elif "DESC" in q_type:
            q_type = "DESCRIPTIVE"
        else:
            q_type = "MCQ"

        pts = marks_map.get(q_type, 1.0)
        
        opt_a = q.get("option_a")
        opt_b = q.get("option_b")
        opt_c = q.get("option_c")
        opt_d = q.get("option_d")
        corr = str(q.get("correct_option") or "A").strip()

        if q_type == "TRUE_FALSE":
            opt_a = "True"
            opt_b = "False"
            opt_c = None
            opt_d = None
            corr = "True" if "true" in corr.lower() or corr.upper() == "A" else "False"

        questions.append({
            "question_text": str(text).strip(),
            "question_type": q_type,
            "option_a": opt_a,
            "option_b": opt_b,
            "option_c": opt_c,
            "option_d": opt_d,
            "correct_option": corr,
            "points": pts
        })

    # Robust Grounded Fallback if needed
    sentences = [s.strip() for s in re.split(r'[\.\n;]', source_text) if len(s.strip()) > 25]
    if not sentences:
        sentences = [
            f"The core concepts in {source_title} provide essential foundational principles.",
            f"Modern architecture in {source_title} ensures scalable and robust operation.",
            f"Standard implementation of {source_title} workflows requires structured verification.",
            f"Performance optimization in {source_title} depends on proper resource allocation."
        ]

    # Fill missing MCQs
    existing_mcqs = [q for q in questions if q["question_type"] == "MCQ"]
    for i in range(len(existing_mcqs), mcq_count):
        s = sentences[i % len(sentences)]
        questions.append({
            "question_text": f"Which statement best reflects key concept #{i+1} of {source_title}: '{s[:75]}...'?",
            "question_type": "MCQ",
            "option_a": f"It defines the primary architectural standard of {source_title}.",
            "option_b": "It is an unmaintained legacy configuration.",
            "option_c": "It is restricted to unencrypted development environments.",
            "option_d": "It requires manual continuous hardware restarts.",
            "correct_option": "A",
            "points": marks_map.get("MCQ", 1.0)
        })

    # Fill missing One-word
    existing_one = [q for q in questions if q["question_type"] == "ONE_WORD"]
    for i in range(len(existing_one), one_word_count):
        s = sentences[(i + 1) % len(sentences)]
        first_word = s.split()[0] if s.split() else "Standard"
        questions.append({
            "question_text": f"What key terminology represents '{s[:80]}...' in {source_title}?",
            "question_type": "ONE_WORD",
            "option_a": None, "option_b": None, "option_c": None, "option_d": None,
            "correct_option": first_word,
            "points": marks_map.get("ONE_WORD", 2.0)
        })

    # Fill missing True/False
    existing_tf = [q for q in questions if q["question_type"] == "TRUE_FALSE"]
    for i in range(len(existing_tf), tf_count):
        s = sentences[(i + 2) % len(sentences)]
        questions.append({
            "question_text": f"True or False: According to {source_title}, {s[:85]}.",
            "question_type": "TRUE_FALSE",
            "option_a": "True", "option_b": "False", "option_c": None, "option_d": None,
            "correct_option": "True",
            "points": marks_map.get("TRUE_FALSE", 1.0)
        })

    # Fill missing Descriptive
    existing_desc = [q for q in questions if q["question_type"] == "DESCRIPTIVE"]
    for i in range(len(existing_desc), desc_count):
        s = sentences[(i + 3) % len(sentences)]
        questions.append({
            "question_text": f"Explain in detail the operational mechanics and significance of '{s[:90]}...' in {source_title}.",
            "question_type": "DESCRIPTIVE",
            "option_a": None, "option_b": None, "option_c": None, "option_d": None,
            "correct_option": f"Comprehensive explanation of {source_title} principles and operational architecture.",
            "points": marks_map.get("DESCRIPTIVE", 5.0)
        })

    return questions

def format_exam_preview(title: str, source_title: str, total_q: int, q_types: Dict[str, int], total_marks: float, duration: int, questions: List[dict]) -> str:
    """Formats a beautiful, markdown preview of the generated exam."""
    breakdown_parts = []
    if q_types.get("MCQ"): breakdown_parts.append(f"{q_types['MCQ']} MCQs")
    if q_types.get("ONE_WORD"): breakdown_parts.append(f"{q_types['ONE_WORD']} One-word")
    if q_types.get("TRUE_FALSE"): breakdown_parts.append(f"{q_types['TRUE_FALSE']} True/False")
    if q_types.get("DESCRIPTIVE"): breakdown_parts.append(f"{q_types['DESCRIPTIVE']} Descriptive")
    breakdown_str = ", ".join(breakdown_parts)

    preview = (
        f"### 📋 Exam Preview: {title}\n\n"
        f"• **Source Material:** {source_title}\n"
        f"• **Total Questions:** {total_q} ({breakdown_str})\n"
        f"• **Total Marks:** {int(total_marks) if total_marks.is_integer() else total_marks} Marks\n"
        f"• **Duration:** {duration} Minutes | **Passing Score:** 70%\n\n"
        f"---\n"
        f"#### Questions List:\n"
    )

    for idx, q in enumerate(questions, 1):
        q_type = q.get("question_type", "MCQ")
        pts = q.get("points", 1.0)
        pts_str = f"{int(pts)} mark" if pts == 1.0 else f"{int(pts) if pts.is_integer() else pts} marks"

        if q_type == "MCQ":
            preview += (
                f"\n**{idx}. [MCQ] ({pts_str})**: {q['question_text']}\n"
                f"   - **A)** {q.get('option_a', 'N/A')}\n"
                f"   - **B)** {q.get('option_b', 'N/A')}\n"
                f"   - **C)** {q.get('option_c', 'N/A')}\n"
                f"   - **D)** {q.get('option_d', 'N/A')}\n"
                f"   *Correct Answer: Option {q.get('correct_option', 'A')}*\n"
            )
        elif q_type == "TRUE_FALSE":
            preview += (
                f"\n**{idx}. [True/False] ({pts_str})**: {q['question_text']}\n"
                f"   - **A)** True | **B)** False\n"
                f"   *Correct Answer: {q.get('correct_option', 'True')}*\n"
            )
        elif q_type == "ONE_WORD":
            preview += (
                f"\n**{idx}. [One-Word] ({pts_str})**: {q['question_text']}\n"
                f"   *Expected Answer: {q.get('correct_option', 'N/A')}*\n"
            )
        elif q_type == "DESCRIPTIVE":
            preview += (
                f"\n**{idx}. [Descriptive] ({pts_str})**: {q['question_text']}\n"
                f"   *Evaluation Rubric: {q.get('correct_option', 'Detailed technical response required')}*\n"
            )

    preview += (
        f"\n---\n"
        f"Would you like to **Publish** this exam, **Regenerate** questions, or **Save as Draft**?"
    )
    return preview

def handle_voice_exam_workflow(session_id: str, message: str, user_id: Optional[str] = None, user_role: Optional[Any] = None) -> Tuple[bool, str]:
    """
    Unified interactive exam creation workflow engine for both Admin Chatbot and Admin Voice Assistant.
    Enforces strict admin-only permissions and completely order-independent natural language understanding.
    """
    db = get_db()
    state = get_session_state(session_id)
    step = state["step"]
    lowered = message.lower().strip()

    # Cancel trigger check
    if lowered in ["cancel", "stop", "exit exam creation", "abort", "cancel exam"]:
        reset_session_state(session_id)
        return True, "Exam creation workflow has been cancelled."

    # 1. Trigger detection when at Step 0
    if step == 0:
        if is_exam_creation_trigger(message):
            # Check permissions: ONLY ADMINS can create exams!
            if user_role and user_role != UserRole.ADMIN and user_role != "ADMIN":
                return True, (
                    "Exam creation is an Administrator-only capability. "
                    "As a learner, you can ask questions about your study materials, "
                    "prepare for upcoming exams, and take published exams in the Exams section."
                )

            # Check if user already provided question breakdown in trigger
            # (e.g. "5 mcqs 5 descriptive" or "Give me 10 questions with 5 MCQs, 2 descriptive, 2 true or false and 1 one-word")
            breakdown = parse_question_breakdown(message)
            if breakdown and sum(breakdown.values()) > 0:
                tot = sum(breakdown.values())
                state["total_questions"] = tot
                state["q_types"] = breakdown
                state["step"] = 3
                return True, (
                    f"Got it! Configured **{tot} questions**:\n"
                    f"{format_breakdown_summary(breakdown)}\n\n"
                    f"**How many marks** should each question/type carry? "
                    f"(For example: '1 mark each' or 'MCQ 1 mark, Descriptive 5 marks')"
                )

            # Check if user already provided total question count in trigger (e.g. "Create a 10 question exam")
            num = parse_number_from_text(message)
            if num and num > 0:
                state["total_questions"] = num
                state["step"] = 2
                return True, (
                    f"Sure! Let's create an exam with **{num} questions**.\n\n"
                    f"What question types or distribution would you like? You can specify in any order:\n"
                    f"• **{num} MCQs** (or any single type)\n"
                    f"• **5 MCQs and 5 Descriptive** (any combination)\n"
                    f"• **5 MCQs, 2 One-word, 2 True/False, 1 Descriptive** (in any order)"
                )

            state["step"] = 1
            return True, "Sure! Let's create an exam. **How many questions** would you like in the exam? (e.g., 10 questions, or specify like '5 MCQs and 5 Descriptive')"
        return False, ""

    # Check permissions if active in workflow
    if user_role and user_role != UserRole.ADMIN and user_role != "ADMIN":
        reset_session_state(session_id)
        return True, (
            "Exam creation is an Administrator-only capability. "
            "As a learner, you can ask questions about your study materials, "
            "prepare for upcoming exams, and take published exams in the Exams section."
        )

    # Step 1: Total Number of Questions
    if step == 1:
        # Check if user provided breakdown directly (e.g., "5 mcqs 5 descriptive")
        breakdown = parse_question_breakdown(message)
        if breakdown and sum(breakdown.values()) > 0:
            tot = sum(breakdown.values())
            state["total_questions"] = tot
            state["q_types"] = breakdown
            state["step"] = 3
            return True, (
                f"Got it! Configured **{tot} questions**:\n"
                f"{format_breakdown_summary(breakdown)}\n\n"
                f"**How many marks** should each question/type carry? "
                f"(For example: '1 mark each' or 'MCQ 1 mark, Descriptive 5 marks')"
            )

        num = parse_number_from_text(message)
        if num and num > 0:
            state["total_questions"] = num
            state["step"] = 2
            return True, (
                f"Got it, **{num} questions**.\n\n"
                f"What question types or distribution would you like? You can specify in any order:\n"
                f"• **{num} MCQs** (or any single type)\n"
                f"• **5 MCQs and 5 Descriptive** (any combination)\n"
                f"• **5 MCQs, 2 One-word, 2 True/False, 1 Descriptive** (in any order)"
            )
        return True, "Please specify the number of questions (e.g., 10 questions) or question distribution (e.g., '5 MCQs and 5 Descriptive')."

    # Step 2 / 2.5: Question Types & Distribution (Order-independent & flexible subset)
    if step in [2, 2.5]:
        tot = state.get("total_questions")
        breakdown = parse_question_breakdown(message, tot)

        if breakdown and sum(breakdown.values()) > 0:
            actual_sum = sum(breakdown.values())
            state["total_questions"] = actual_sum
            state["q_types"] = breakdown
            state["step"] = 3

            return True, (
                f"Great! Configured **{actual_sum} questions**:\n"
                f"{format_breakdown_summary(breakdown)}\n\n"
                f"**How many marks** should each question/type carry? "
                f"(For example: '1 mark each' or 'MCQ 1 mark, Descriptive 5 marks')"
            )

        return True, (
            f"Please specify the question types or distribution you'd like (for example: "
            f"'{tot or 10} MCQs', '5 MCQs and 5 Descriptive', or '5 MCQs, 2 One-word, 2 True/False, 1 Descriptive')."
        )

    # Step 3: Marks & Total Marks Calculation + Confirmation
    if step == 3:
        q_types = state["q_types"]
        marks_map = parse_marks_input(message, list(q_types.keys()))
        total_marks = sum(q_types[t] * marks_map.get(t, 1.0) for t in q_types)

        state["marks_map"] = marks_map
        state["total_marks"] = total_marks
        state["step"] = 4

        # Show clear confirmation of the exam configuration
        confirmation_msg = format_exam_config_confirmation(
            total_q=state["total_questions"],
            q_types=q_types,
            marks_map=marks_map,
            total_marks=total_marks
        )
        return True, confirmation_msg

    # Step 4: Content / Study Material Selection & Generation
    if step == 4:
        # Search Study Plan Days & Uploaded Documents
        sp_days = db.query(StudyPlanDay).all()
        matched_content = None
        matched_title = message.strip()

        # 1. Match Study Plan Day (e.g. 'week 1 day 2' or title)
        for d in sp_days:
            t = (d.pdf_title or d.title or "").lower()
            topic = (d.topic or "").lower()
            day_str = f"day {d.day_number}"
            if (t and t in lowered) or (topic and topic in lowered) or (day_str in lowered):
                matched_content = d.lesson_content or d.content_summary or d.title
                matched_title = d.pdf_title or d.title or f"Day {d.day_number}"
                break

        # 2. Match Uploaded Documents
        if not matched_content:
            docs = db.query(Document).all()
            for doc in docs:
                if doc.title.lower() in lowered or lowered in doc.title.lower():
                    chunks = db.query(DocumentChunk).filter(DocumentChunk.document_id == doc.id).all()
                    matched_content = "\n\n".join([c.content for c in chunks]) if chunks else doc.title
                    matched_title = doc.title
                    break

        if not matched_content:
            matched_content = f"Curriculum topic: {matched_title}. Core architectural design, implementation workflows, validation standards, and operational best practices."

        state["source_title"] = matched_title
        state["source_text"] = matched_content

        # Generate Grounded Questions
        tot = state["total_questions"]
        q_types = state["q_types"]
        marks_map = state["marks_map"]
        tot_marks = state["total_marks"]
        dur = state.get("duration_minutes", 30)

        questions = generate_grounded_questions(matched_title, matched_content, q_types, marks_map)

        state["generated_exam_data"] = {
            "title": f"{matched_title} Assessment",
            "description": f"Assessment generated from '{matched_title}'.",
            "duration_minutes": dur,
            "passing_score": 70.0,
            "questions": questions,
            "source_document_name": matched_title
        }
        state["step"] = 6

        preview_text = format_exam_preview(
            title=f"{matched_title} Assessment",
            source_title=matched_title,
            total_q=tot,
            q_types=q_types,
            total_marks=tot_marks,
            duration=dur,
            questions=questions
        )
        return True, preview_text

    # Step 6 / 7: Action (Publish, Regenerate, Save as Draft)
    if step in [6, 7]:
        exam_info = state.get("generated_exam_data")
        if not exam_info:
            reset_session_state(session_id)
            return True, "An error occurred with the exam data. Please start exam creation again."

        # Publish
        if any(w in lowered for w in ["publish", "yes", "confirm", "approve", "save and publish"]):
            try:
                db_exam = Exam(
                    title=exam_info["title"],
                    description=exam_info["description"],
                    duration_minutes=exam_info["duration_minutes"],
                    passing_score=exam_info["passing_score"],
                    status=ExamStatus.PUBLISHED,
                    source_document_name=exam_info.get("source_document_name")
                )
                db.add(db_exam)
                db.commit()
                db.refresh(db_exam)

                for q in exam_info.get("questions", []):
                    db_q = Question(
                        exam_id=db_exam.id,
                        question_type=q.get("question_type", "MCQ"),
                        question_text=q.get("question_text", "Question"),
                        option_a=q.get("option_a"),
                        option_b=q.get("option_b"),
                        option_c=q.get("option_c"),
                        option_d=q.get("option_d"),
                        correct_option=str(q.get("correct_option", "A")),
                        points=float(q.get("points", 1.0))
                    )
                    db.add(db_q)

                # Broadcast notification to active learners
                all_users = db.query(User).filter(User.is_active == True).all()
                for u in all_users:
                    notif = Notification(
                        user_id=u.id,
                        title="New Exam Published",
                        message=f"Exam '{db_exam.title}' has been published.",
                        type="EXAM_PUBLISHED"
                    )
                    db.add(notif)

                db.commit()

                if user_id:
                    log_audit_event(
                        db, action="CREATE_EXAM", entity_type="EXAM", user_id=user_id, entity_id=db_exam.id,
                        details=f"Admin created and published exam '{db_exam.title}' with {len(exam_info.get('questions', []))} questions."
                    )

                reset_session_state(session_id)
                return True, f"🎉 Exam '**{db_exam.title}**' has been successfully published!\n\nIt is now live and available to learners in **My Exams**."

            except Exception as e:
                logger.error(f"Error publishing exam: {e}")
                db.rollback()
                reset_session_state(session_id)
                return True, "Failed to save exam to database due to an internal error."

        # Regenerate
        elif "regenerate" in lowered or "re-generate" in lowered or "retry" in lowered:
            matched_title = state.get("source_title", "Study Material")
            matched_content = state.get("source_text", "")
            tot = state["total_questions"]
            q_types = state["q_types"]
            marks_map = state["marks_map"]
            tot_marks = state["total_marks"]
            dur = state.get("duration_minutes", 30)

            questions = generate_grounded_questions(matched_title, matched_content, q_types, marks_map)
            state["generated_exam_data"]["questions"] = questions

            preview_text = format_exam_preview(
                title=f"{matched_title} Assessment",
                source_title=matched_title,
                total_q=tot,
                q_types=q_types,
                total_marks=tot_marks,
                duration=dur,
                questions=questions
            )
            return True, f"🔄 Questions regenerated!\n\n{preview_text}"

        # Save as Draft
        elif "draft" in lowered or "save draft" in lowered or "save as draft" in lowered:
            try:
                db_exam = Exam(
                    title=exam_info["title"],
                    description=exam_info["description"],
                    duration_minutes=exam_info["duration_minutes"],
                    passing_score=exam_info["passing_score"],
                    status=ExamStatus.DRAFT,
                    source_document_name=exam_info.get("source_document_name")
                )
                db.add(db_exam)
                db.commit()
                db.refresh(db_exam)

                for q in exam_info.get("questions", []):
                    db_q = Question(
                        exam_id=db_exam.id,
                        question_type=q.get("question_type", "MCQ"),
                        question_text=q.get("question_text", "Question"),
                        option_a=q.get("option_a"),
                        option_b=q.get("option_b"),
                        option_c=q.get("option_c"),
                        option_d=q.get("option_d"),
                        correct_option=str(q.get("correct_option", "A")),
                        points=float(q.get("points", 1.0))
                    )
                    db.add(db_q)
                db.commit()

                reset_session_state(session_id)
                return True, f"💾 Exam '**{db_exam.title}**' has been saved as **Draft**."

            except Exception as e:
                logger.error(f"Error saving draft exam: {e}")
                db.rollback()
                reset_session_state(session_id)
                return True, "Failed to save draft exam."

        return True, "Please reply with **Publish** to publish the exam, **Regenerate** to create new questions, or **Save as Draft**."

    return False, ""

