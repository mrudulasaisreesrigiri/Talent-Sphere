import logging
import json
import re
from app.models.models import Exam, Question, ExamStatus, StudyPlanWeek, StudyPlan, Notification
from app.services.groq_service import GroqService
from app.services.vector_service import vector_service

logger = logging.getLogger(__name__)

# Exact 8 Questions provided for Week 1 Exam
WEEK_1_EXACT_EXAM_QUESTIONS = [
    {
        "question_type": "MCQ",
        "question_text": "Which of the following is a primary goal of Artificial Intelligence?",
        "option_a": "To replace all computer hardware",
        "option_b": "To simulate human intelligence in machines",
        "option_c": "To increase internet speed",
        "option_d": "To design computer chips",
        "correct_option": "B",
        "explanation": "The primary goal of AI is to simulate human intelligence processes in machines.",
        "points": 1.0
    },
    {
        "question_type": "MCQ",
        "question_text": "Which AI technology enables computers to understand and process human language?",
        "option_a": "Computer Vision",
        "option_b": "Natural Language Processing",
        "option_c": "Cloud Computing",
        "option_d": "Data Mining",
        "correct_option": "B",
        "explanation": "Natural Language Processing (NLP) enables computers to understand, interpret, and process human language.",
        "points": 1.0
    },
    {
        "question_type": "MCQ",
        "question_text": "Which of the following is NOT an application of Artificial Intelligence?",
        "option_a": "Medical Diagnosis",
        "option_b": "Recommendation Systems",
        "option_c": "Weather Forecasting using AI",
        "option_d": "Manual Typewriter",
        "correct_option": "D",
        "explanation": "Manual Typewriter is a mechanical device, not an AI application.",
        "points": 1.0
    },
    {
        "question_type": "MCQ",
        "question_text": "Which of the following best describes Machine Learning?",
        "option_a": "Writing programs without data",
        "option_b": "A method where computers learn from data to make predictions",
        "option_c": "Designing computer hardware",
        "option_d": "Managing computer networks",
        "correct_option": "B",
        "explanation": "Machine Learning is a subset of AI where systems learn patterns from data to make predictions.",
        "points": 1.0
    },
    {
        "question_type": "One Word",
        "question_text": "Which branch of AI helps computers learn from data?",
        "option_a": None, "option_b": None, "option_c": None, "option_d": None,
        "correct_option": "Machine Learning",
        "explanation": "Machine Learning is the branch of AI focused on learning from data.",
        "points": 1.0
    },
    {
        "question_type": "One Word",
        "question_text": "Name one AI-based virtual assistant.",
        "option_a": None, "option_b": None, "option_c": None, "option_d": None,
        "correct_option": "Siri",
        "explanation": "Siri, Alexa, and Google Assistant are AI-based virtual assistants.",
        "points": 1.0
    },
    {
        "question_type": "DESCRIPTIVE",
        "question_text": "Explain any five characteristics of Artificial Intelligence.",
        "option_a": None, "option_b": None, "option_c": None, "option_d": None,
        "correct_option": "Automation, learning capabilities, problem-solving, pattern recognition, and adaptability.",
        "explanation": "Core characteristics include automation, continuous learning, reasoning, pattern recognition, and adaptability.",
        "points": 2.0
    },
    {
        "question_type": "DESCRIPTIVE",
        "question_text": "Describe the advantages and disadvantages of Artificial Intelligence with suitable examples.",
        "option_a": None, "option_b": None, "option_c": None, "option_d": None,
        "correct_option": "Advantages: Efficiency, 24/7 availability, accuracy. Disadvantages: High implementation costs, job displacement, lack of human emotion.",
        "explanation": "Key advantages include automation and high efficiency; key disadvantages include high costs and lack of empathy.",
        "points": 2.0
    }
]


def _generate_content_grounded_fallback(lessons, plan, week):
    """
    Parses key concepts, definitions, headers, and technical sentences directly from the 4 uploaded lesson texts.
    Generates 8 direct technical questions testing real concepts without ANY meta references to day titles or day numbers.
    """
    text_blocks = []
    all_sentences = []

    for d in sorted(lessons, key=lambda x: x.day_number):
        t_title = (d.lesson_title or d.topic or "").strip()
        if t_title.lower().startswith("day "):
            t_title = f"Module {d.day_number}"
        content = (d.lesson_content or "").strip()
        sentences = [s.strip() for s in re.split(r'[.\n]', content) if len(s.strip()) > 15 and not s.startswith('#')]
        
        headers = re.findall(r'#{1,4}\s*([^\n]+)', content)
        bolds = re.findall(r'\*\*([^*]+)\*\*', content)
        
        concept_name = headers[0].strip() if headers else (bolds[0].strip() if bolds else t_title)
        text_blocks.append((d.day_number, concept_name, sentences, content))
        all_sentences.extend(sentences)

    questions = []

    for idx in range(min(3, len(text_blocks))):
        day_num, concept_name, sentences, raw_text = text_blocks[idx]
        target_sentence = sentences[0] if sentences else raw_text[:120]
        
        other_sentences = [s for s in all_sentences if s != target_sentence and len(s) > 20]

        opt_a = target_sentence
        opt_b = other_sentences[0] if len(other_sentences) > 0 else "Execution occurs asynchronously without state tracking."
        opt_c = other_sentences[1] if len(other_sentences) > 1 else "Direct memory allocation without index verification."
        opt_d = other_sentences[2] if len(other_sentences) > 2 else "Unvalidated sequential loop bypass."

        questions.append({
            "question_type": "MCQ",
            "question_text": f"Which of the following statements is correct regarding {concept_name}?",
            "option_a": opt_a,
            "option_b": opt_b,
            "option_c": opt_c,
            "option_d": opt_d,
            "correct_option": "A",
            "explanation": f"Stated directly in the lesson material: '{target_sentence}'",
            "points": 1.0
        })

    for idx in [0, min(3, len(text_blocks)-1)]:
        day_num, concept_name, sentences, raw_text = text_blocks[idx]
        words = [w for w in re.findall(r'\b[A-Z][a-zA-Z0-9_-]{2,}\b', raw_text) if w not in ['DAY', 'Day', 'Week', 'The', 'This', 'That', 'With', 'From', 'Where', 'When']]
        word_ans = words[0] if words else "Architecture"
        questions.append({
            "question_type": "One Word",
            "question_text": f"What key technical term refers to the core mechanism of {concept_name}?",
            "option_a": None, "option_b": None, "option_c": None, "option_d": None,
            "correct_option": word_ans,
            "explanation": f"Core technical term referenced in lesson content for {concept_name}.",
            "points": 1.0
        })

    for idx in [min(1, len(text_blocks)-1), min(2, len(text_blocks)-1)]:
        day_num, concept_name, sentences, raw_text = text_blocks[idx]
        target_sent = sentences[min(1, len(sentences)-1)] if len(sentences) > 1 else (sentences[0] if sentences else raw_text[:120])
        words = [w for w in re.findall(r'\b[A-Za-z]{4,}\b', target_sent) if w.lower() not in ['this', 'that', 'from', 'with', 'which', 'where', 'their', 'there', 'using', 'into']]
        blank_word = words[0] if words else "system"
        q_blank_text = target_sent.replace(blank_word, "_____", 1)
        questions.append({
            "question_type": "FillBlank",
            "question_text": f"Fill in the blank based on the lesson content: {q_blank_text}",
            "option_a": None, "option_b": None, "option_c": None, "option_d": None,
            "correct_option": blank_word,
            "explanation": f"Original statement in lesson content: '{target_sent}'",
            "points": 1.0
        })

    c1_name = text_blocks[0][1]
    c4_name = text_blocks[-1][1]
    questions.append({
        "question_type": "DESCRIPTIVE",
        "question_text": f"Explain in detail the technical principles, practical workflow, and key mechanisms of {c1_name} and {c4_name}.",
        "option_a": None, "option_b": None, "option_c": None, "option_d": None,
        "correct_option": f"Detailed technical explanation connecting the core mechanisms described in {c1_name} and {c4_name}.",
        "explanation": f"Grounded in lesson content for {c1_name} and {c4_name}.",
        "points": 2.0
    })

    return questions


def generate_week_exam_ai(week: StudyPlanWeek, plan: StudyPlan, db):
    """
    EXAM GENERATION PIPELINE:
    Generates assessment exam from the combined extracted text of all 4 uploaded Study Plan PDFs:
    Day 1 PDF + Day 2 PDF + Day 3 PDF + Day 4 PDF.
    Contains a good mixture of beginner-level questions based on the four PDFs:
    - Multiple-choice questions (MCQs)
    - One-word answers
    - Descriptive questions
    Saves Exam and Questions in DB, updates status to 'READY', and associates with StudyPlanWeek.
    """
    from pypdf import PdfReader
    import os

    # Ensure all 4 days have extracted text (fallback to disk if needed)
    lessons = [d for d in week.days if d.has_lesson and d.day_number <= 4]
    if len(lessons) < 4:
        logger.info(f"Week {week.week_number} has only {len(lessons)}/4 lesson day slots. Waiting for all 4 lessons.")
        return None

    # Verify and load text for each of Day 1..4
    for d in lessons:
        if (not d.lesson_content or len(d.lesson_content.strip()) < 10):
            if d.pdf_extracted_text and len(d.pdf_extracted_text.strip()) >= 10:
                d.lesson_content = d.pdf_extracted_text
            elif d.pdf_file_path and os.path.exists(os.path.abspath(d.pdf_file_path)):
                try:
                    reader = PdfReader(os.path.abspath(d.pdf_file_path))
                    extracted = ""
                    for p_idx, page in enumerate(reader.pages):
                        p_text = page.extract_text() or ""
                        extracted += f"\n--- Page {p_idx + 1} ---\n{p_text}"
                    if extracted.strip():
                        d.pdf_extracted_text = extracted.strip()
                        d.lesson_content = extracted.strip()
                        db.commit()
                except Exception as ex:
                    logger.error(f"Failed extracting PDF text for Day {d.id}: {ex}")

    valid_lessons = [d for d in lessons if (d.lesson_content and len(d.lesson_content.strip()) >= 5) or (d.pdf_extracted_text and len(d.pdf_extracted_text.strip()) >= 5)]
    if len(valid_lessons) < 4:
        logger.info(f"Week {week.week_number} has only {len(valid_lessons)}/4 lessons with extracted text. Waiting for all 4 PDFs.")
        return None

    # Check if a valid exam already exists with questions for this week
    if week.exam_id:
        existing_exam = db.query(Exam).filter(Exam.id == week.exam_id).first()
        if existing_exam:
            q_cnt = db.query(Question).filter(Question.exam_id == existing_exam.id).count()
            if q_cnt > 0:
                logger.info(f"Valid exam already exists for Week {week.week_number} (ID: {existing_exam.id}) with {q_cnt} questions.")
                week.exam_status = "READY"
                db.commit()
                return existing_exam

    existing_by_name = db.query(Exam).filter(
        Exam.source_document_name == f"{plan.title} - Week {week.week_number}"
    ).first()
    if existing_by_name:
        q_cnt = db.query(Question).filter(Question.exam_id == existing_by_name.id).count()
        if q_cnt > 0:
            logger.info(f"Exam found by source document name for Week {week.week_number}: {existing_by_name.id}")
            week.exam_id = existing_by_name.id
            week.exam_status = "READY"
            db.commit()
            return existing_by_name

    try:
        week.exam_status = "GENERATING"
        db.commit()

        # Build knowledge base from all 4 uploaded PDFs: Day 1 + Day 2 + Day 3 + Day 4
        full_knowledge_base = ""
        for d in sorted(lessons, key=lambda x: x.day_number):
            day_title = d.pdf_title or d.lesson_title or d.topic or f"Day {d.day_number}"
            day_text = (d.lesson_content or d.pdf_extracted_text or "").strip()
            full_knowledge_base += f"\n\n=== LESSON CONTENT DAY {d.day_number} ({day_title}) ===\n{day_text}"

        prompt = f"""You are an expert Senior Technical Examiner creating a comprehensive assessment exam for a course module.

CRITICAL INSTRUCTIONS:
You are provided with the complete extracted text from all four lesson PDFs uploaded for this week:
Day 1 PDF + Day 2 PDF + Day 3 PDF + Day 4 PDF.

ALL 4-DAY LESSON PDF CONTENT:
{full_knowledge_base}

STRICT QUESTION REQUIREMENTS:
1. Every question MUST be strictly grounded in the concepts, definitions, tools, mechanisms, and statements present in the 4 uploaded PDFs above.
2. DO NOT create generic questions unrelated to these 4 PDFs.
3. Generate a balanced mixture of 8 beginner-friendly technical questions:
   - 4 Multiple Choice Questions (MCQ): Provide 4 distinct options (A, B, C, D) testing key concepts across Days 1, 2, 3, and 4. Include clear explanation.
   - 2 One-Word Answer Questions: Ask for a specific technical term, tool, or component directly stated in the text.
   - 2 Descriptive Questions: Ask the learner to explain core concepts or workflows detailed in the PDFs.

Output a valid JSON object with the exact format:
{{
  "questions": [
    {{
      "question_type": "MCQ",
      "question_text": "<Question text testing specific concept from the PDF>",
      "option_a": "<Option A>",
      "option_b": "<Option B>",
      "option_c": "<Option C>",
      "option_d": "<Option D>",
      "correct_option": "A",
      "explanation": "<Explanation grounded in the PDF text>",
      "points": 1.0
    }},
    {{
      "question_type": "One Word",
      "question_text": "<Question asking for a specific technical term from the text>",
      "option_a": null, "option_b": null, "option_c": null, "option_d": null,
      "correct_option": "<Exact Term>",
      "explanation": "<Reference to lesson text>",
      "points": 1.0
    }},
    {{
      "question_type": "DESCRIPTIVE",
      "question_text": "<Descriptive question asking to explain a mechanism from the PDFs>",
      "option_a": null, "option_b": null, "option_c": null, "option_d": null,
      "correct_option": "<Expected technical rubric points>",
      "explanation": "<Reference to lesson text>",
      "points": 2.0
    }}
  ]
}}

Return ONLY valid JSON. No preamble or markdown wrapper."""

        raw_response = ""
        try:
            raw_response = GroqService.generate_response(prompt=prompt, system_prompt="You are a strict JSON generator. Return ONLY valid JSON.")
        except Exception as e:
            logger.error(f"Groq API call failed: {e}")

        parsed_questions = []
        if raw_response:
            try:
                match = re.search(r'\{.*\}', raw_response, re.DOTALL)
                if match:
                    data = json.loads(match.group(0))
                    raw_qs = data.get("questions", [])
                    for q in raw_qs:
                        qt = q.get("question_text", "")
                        if qt and not any(meta in qt.lower() for meta in ["what is covered", "what content is", "summarize week", "learning outcomes", "based on day", "highlighted in day"]):
                            parsed_questions.append(q)
            except Exception as e:
                logger.error(f"Failed to parse LLM JSON response: {e}")

        if len(parsed_questions) < 6:
            logger.info("Using content-grounded text extraction for AI exam questions.")
            parsed_questions = _generate_content_grounded_fallback(lessons, plan, week)

        # 2. Create Exam Record in Database
        exam = Exam(
            title=f"{plan.title} - Week {week.week_number} Comprehensive Exam",
            description=f"Automated AI-generated technical assessment exam for Week {week.week_number} of {plan.title}.",
            duration_minutes=30,
            passing_score=70.0,
            status=ExamStatus.PUBLISHED,
            source_document_name=f"{plan.title} - Week {week.week_number}",
            created_by=plan.created_by
        )
        db.add(exam)
        db.commit()
        db.refresh(exam)

        # 3. Insert Questions into Database
        for q_data in parsed_questions:
            q_type = q_data.get("question_type", "MCQ")
            q = Question(
                exam_id=exam.id,
                question_type=q_type,
                question_text=str(q_data.get("question_text", "")).strip(),
                option_a=str(q_data.get("option_a", "")).strip() if q_data.get("option_a") else None,
                option_b=str(q_data.get("option_b", "")).strip() if q_data.get("option_b") else None,
                option_c=str(q_data.get("option_c", "")).strip() if q_data.get("option_c") else None,
                option_d=str(q_data.get("option_d", "")).strip() if q_data.get("option_d") else None,
                correct_option=str(q_data.get("correct_option", "A")).strip(),
                explanation=str(q_data.get("explanation", "")).strip() if q_data.get("explanation") else None,
                points=float(q_data.get("points", 1.0))
            )
            db.add(q)

        week.exam_id = exam.id
        week.exam_status = "READY"
        db.commit()

        # 4. Notify Admin
        admin_id = plan.created_by
        if admin_id:
            notif = Notification(
                user_id=admin_id,
                title=f"Week {week.week_number} Exam Generated Successfully.",
                message=f"AI has generated an 8-question technical exam for Week {week.week_number}.",
                type="EXAM_GENERATED"
            )
            db.add(notif)
            db.commit()

        logger.info(f"Successfully generated AI Week {week.week_number} Exam (ID: {exam.id})")
        return exam

    except Exception as e:
        db.rollback()
        week.exam_status = "FAILED"
        db.commit()
        logger.error(f"Error during generate_week_exam_ai: {e}", exc_info=True)
        return None
