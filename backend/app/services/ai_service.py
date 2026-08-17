import os
import json
import logging
import re
import time
from typing import List, Dict, Any, Tuple, Generator, Optional

from app.core.config import settings
from app.services.vector_service import vector_service

logger = logging.getLogger(__name__)

WEBSITE_KNOWLEDGE_BASE = """
TALENT MANAGEMENT PLATFORM FOR EMPLOYEE PERFORMANCE AND CAREER GROWTH PLATFORM KNOWLEDGE BASE:
1. Study Plan Curriculum & Daily PDF Lessons:
   - Access: 'Study Plans & Lessons' navigation menu.
   - Capability: 6-week structured learning curriculum with daily learning modules (Day 1 to Day 4 lesson PDFs, Day 5 AI Assessment Exam, Day 6 AI Mock Interview).
   - Admin Role: Create Study Plans and upload daily lesson PDFs for Day 1 through Day 4.
   - Student Role: Read daily lesson PDFs sequentially. Embedded PDF viewer tracks page-by-page progress in real-time. Once all pages are viewed, clicking 'Mark as Completed' unlocks the next module.

2. Knowledge Search:
   - Access: 'Knowledge Search' menu.
   - Capability: RAG natural language vector search querying ChromaDB embeddings across all course study documents.
   - Display: Highlights matching lesson snippets, relevance match percentages, and page numbers.

3. Assessment & Exam Engine:
   - Access: 'Exams' menu.
   - Capability: Create manual exam papers or auto-generate exams using AI Commands ('Create Exam from <PDF Name>').
   - Types: MCQs, True/False, Short Answer.
   - Lifecycle: DRAFT, PUBLISHED, ARCHIVED.
   - Exam Runner: Full-screen interactive exam mode with countdown timer, question navigator (1..N), option selector, auto-submit on expiration, and instant auto-grading.

4. System Announcements:
   - Access: 'Announcements' menu.
   - Capability: Broadcast updates for students. Admins can post manual announcements or generate announcements from PDF documents via AI Commands.

5. User Management (Admin Only):
   - Access: 'User Management' menu.
   - Capability: Admin CRUD operations. Create Student/Admin user accounts, edit full names/roles, toggle account status, reset passwords.

6. Voice Assistant (Admin Only):
   - Access: Header topbar microphone icon on every page.
   - Capability: Continuous Web Speech API Speech-to-Text (STT) recording & Text-to-Speech (TTS) audio playback connected to the exact same backend AI RAG pipeline as the Chatbot.

7. AI Command Center (Admin Only):
   - Access: 'AI Commands' button in header topbar.
   - Capability: Execute automated directives like 'Create Exam from <PDF Name>' or 'Create Announcement from <PDF Name>'.

8. Audit Logs (Admin Only):
   - Access: 'Audit Logs' menu.
   - Capability: Audit trail of all platform activities (logins, account changes, document uploads, exam attempts).
"""

# Extensive Topic Knowledge Repository for Fallback Synthesis
TOPIC_KNOWLEDGE_MAP = {
    "python": (
        "### Python Programming Language\n\n"
        "Python is a high-level, interpreted programming language renowned for its clear syntax, high readability, and versatile ecosystem.\n\n"
        "#### Key Architectural Highlights:\n"
        "- **Multi-Paradigm Support**: Fully supports Object-Oriented Programming (OOP), Functional Programming, and Procedural Scripting.\n"
        "- **Data Science & AI Ecosystem**: Powerhouse libraries including `Pandas`, `NumPy`, `PyTorch`, `TensorFlow`, and `Scikit-Learn`.\n"
        "- **Web & Backend Frameworks**: High-performance backend capabilities using `Flask`, `FastAPI`, and `Django`.\n"
        "- **Automatic Memory Management**: Features dynamic typing and garbage collection with reference counting.\n\n"
        "```python\n"
        "# Example: Dynamic Data Science Processing\n"
        "data = [x ** 2 for x in range(10) if x % 2 == 0]\n"
        "print(f'Processed values: {data}')\n"
        "```"
    ),
    "supervised learning": (
        "### Supervised Machine Learning\n\n"
        "Supervised Learning is a core machine learning paradigm where an algorithm learns a mapping function from input features ($X$) to target labels ($Y$) using a labeled training dataset.\n\n"
        "#### How It Works:\n"
        "Think of supervised learning like learning with a teacher who provides both practice questions and correct answers. The model makes predictions, measures errors against ground truth, and adjusts internal parameters.\n\n"
        "#### Primary Classifications:\n"
        "1. **Classification**: Predicting discrete category labels (e.g., Spam vs. Not Spam, Disease Diagnosis).\n"
        "   - *Algorithms*: Logistic Regression, Support Vector Machines (SVM), Decision Trees, Random Forests.\n"
        "2. **Regression**: Predicting continuous numeric values (e.g., House Prices, Stock Predictions).\n"
        "   - *Algorithms*: Linear Regression, Ridge/Lasso, Gradient Boosting (XGBoost).\n\n"
        "#### Concrete Example:\n"
        "To build an email spam filter, you provide 10,000 historical emails labeled as `Spam` or `Legitimate`. The model learns key phrase patterns (e.g., 'free offer', 'verify account') and accurately categorizes incoming unread emails."
    ),
    "machine learning": (
        "### Machine Learning (ML)\n\n"
        "Machine Learning is a branch of Artificial Intelligence focused on building mathematical algorithms that learn patterns from data and improve performance without explicit programming.\n\n"
        "#### Core Paradigms:\n"
        "- **Supervised Learning**: Model learns from labeled data ($X \\rightarrow Y$).\n"
        "- **Unsupervised Learning**: Discovers hidden structures in unlabeled data (e.g., K-Means Clustering, PCA).\n"
        "- **Reinforcement Learning**: Agent learns optimal decision policies through reward signals (e.g., Q-Learning, Deep RL).\n"
        "- **Deep Learning**: Multi-layered Artificial Neural Networks (ANNs, CNNs, Transformers)."
    ),
    "artificial intelligence": (
        "### Artificial Intelligence (AI)\n\n"
        "Artificial Intelligence encompasses computer systems and software engineered to perform cognitive tasks that traditionally require human intelligence.\n\n"
        "#### Dominant Domains:\n"
        "1. **Natural Language Processing (NLP)**: Large Language Models (LLMs), RAG systems, and semantic sentiment analysis.\n"
        "2. **Computer Vision**: Object detection (YOLO), image segmentation, and facial recognition.\n"
        "3. **Generative AI**: Diffusion models (Midjourney, DALL-E) and Autoregressive Transformers (GPT-4, Llama 3)."
    ),
    "database": (
        "### Database Systems & Management (DBMS)\n\n"
        "A Database is an organized electronic system designed to store, manage, and retrieve structured and unstructured data efficiently.\n\n"
        "#### Core Models:\n"
        "- **Relational Databases (RDBMS)**: Structured tables using SQL (MySQL, PostgreSQL). Guarantees **ACID** properties (Atomicity, Consistency, Isolation, Durability).\n"
        "- **NoSQL Databases**: Document (MongoDB), Key-Value (Redis), Graph (Neo4j) optimized for horizontal scaling.\n"
        "- **Vector Databases**: Stores high-dimensional vector embeddings (ChromaDB, Pinecone) enabling cosine similarity search for RAG applications."
    ),
    "operating system": (
        "### Operating Systems (OS)\n\n"
        "An Operating System is master system software that manages computer hardware, software resources, and execution environments.\n\n"
        "#### Key Responsibilities:\n"
        "1. **Process & CPU Management**: Multi-threading, process scheduling algorithms, and deadlock resolution.\n"
        "2. **Memory Management**: Virtual memory, paging, and RAM allocation.\n"
        "3. **File System & Storage**: Inode management, disk scheduling, and access control lists."
    ),
    "network": (
        "### Computer Networking & Protocols\n\n"
        "Networking refers to interconnected computing devices communicating and exchanging data through standardized communication protocols.\n\n"
        "#### Fundamental Layers:\n"
        "- **Application Layer**: HTTP, HTTPS, WebSocket, DNS, SSH.\n"
        "- **Transport Layer**: TCP (reliable connection-oriented) and UDP (low-latency datagrams).\n"
        "- **Network Layer**: IP addressing (IPv4/IPv6) and ICMP routing."
    ),
    "cloud": (
        "### Cloud Computing Infrastructure\n\n"
        "Cloud Computing is the on-demand delivery of computing resources (servers, storage, databases, networking) over the Internet with pay-as-you-go pricing.\n\n"
        "#### Service Models:\n"
        "- **IaaS**: Virtual infrastructure (AWS EC2, Google Compute Engine).\n"
        "- **PaaS**: Managed application deployment platforms (AWS Elastic Beanstalk, Heroku).\n"
        "- **SaaS**: On-demand web applications (Google Workspace, Microsoft 365)."
    )
}

class AIService:
    """
    Unified Shared AI Brain Service used by both Chatbot and Voice Assistant.
    Provides RAG search, conversation memory, prompt building, and Groq LLM generation with intelligent fallback.
    """
    def __init__(self):
        self.api_key = os.environ.get("GROQ_API_KEY", settings.GROQ_API_KEY)
        self.model = os.environ.get("GROQ_MODEL", settings.GROQ_MODEL)
        self.client = None
        self._ensure_client()

    def _ensure_client(self):
        current_key = os.environ.get("GROQ_API_KEY", settings.GROQ_API_KEY)
        if current_key and current_key.strip() and current_key != "your-groq-api-key-here":
            if self.client is None or self.api_key != current_key:
                try:
                    from groq import Groq
                    self.api_key = current_key.strip()
                    self.model = os.environ.get("GROQ_MODEL", settings.GROQ_MODEL)
                    self.client = Groq(api_key=self.api_key)
                    logger.info(f"AIService: Groq LLM client initialized with model '{self.model}'.")
                except Exception as e:
                    logger.error(f"AIService: Failed to initialize Groq client: {e}")

    def is_casual_message(self, query: str) -> bool:
        """
        Determines whether the user's message is casual conversation, greeting, pleasantry,
        acknowledgment, or social small talk, as opposed to a knowledge-based, technical,
        educational, or Study Plan-related question.
        """
        if not query or not query.strip():
            return True

        q = query.strip().lower()
        # Remove trailing and leading punctuation
        q_clean = re.sub(r'^[^\w\s]+|[^\w\s]+$', '', q).strip()

        # 1. Exact common casual phrases & single-word acknowledgments
        exact_casual_phrases = {
            "hi", "hello", "hey", "hey there", "hello there", "hiya", "howdy", "hola", "yo",
            "good morning", "good afternoon", "good evening", "good night", "good day", "greetings",
            "how are you", "how are you doing", "how's it going", "how is it going", "how do you do",
            "what's up", "whats up", "how have you been", "how r u", "how are u",
            "thank you", "thanks", "thank you so much", "thanks a lot", "many thanks", "thx", "appreciate it", "thank u",
            "ok", "okay", "alright", "all right", "got it", "understood", "cool", "great", "nice", "awesome",
            "perfect", "sure", "yep", "yes", "no", "nope", "sounds good", "that makes sense", "fine", "kk", "k",
            "bye", "goodbye", "see you", "see you later", "talk to you later", "cya", "have a nice day", "have a good one", "take care", "bye bye",
            "can you help me", "could you help me", "i need help", "help me", "can you help", "help",
            "who are you", "what is your name", "what are you", "what can you do", "introduce yourself", "tell me about yourself"
        }
        if q_clean in exact_casual_phrases or q in exact_casual_phrases:
            return True

        # 2. Greeting prefixes with polite / assistant address
        greeting_match = re.match(r'^(hi|hello|hey|greetings|good\s+(morning|afternoon|evening|day))\b', q_clean)
        if greeting_match:
            rest = q_clean[greeting_match.end():].strip()
            rest = re.sub(r'^[^\w\s]+|[^\w\s]+$', '', rest).strip()
            if not rest or rest in exact_casual_phrases or rest in {"there", "assistant", "ai", "friend", "bot", "buddy", "everyone", "there how are you"}:
                return True

        # 3. Common polite expressions & check-in patterns
        pleasantry_patterns = [
            r'^(can|could|will|would)\s+you\s+(please\s+)?help\s+(me)?(\s+with\s+something)?$',
            r'^(i\s+have\s+a\s+question|i\s+need\s+some\s+help|just\s+saying\s+hi|testing(\s+1\s*2\s*3)?)$',
            r'^(nice|good)\s+to\s+(meet|see)\s+you$',
            r'^how\s+is\s+your\s+day(\s+going)?$',
            r'^thank(s|\s+you)\s+(very\s+much|a\s+lot|again)?$'
        ]
        for pattern in pleasantry_patterns:
            if re.match(pattern, q_clean):
                return True

        return False

    def classify_query(self, query: str) -> str:
        """
        Classifies query into:
        - 'Casual': Greetings, small talk, pleasantries, acknowledgments, casual conversation.
        - 'WebsiteHelp': Platform navigation and LMS module guides.
        - 'KnowledgeQuery': Technical, educational, knowledge-based, or Study Plan questions.
        """
        if self.is_casual_message(query):
            return "Casual"

        q = query.strip().lower()

        # Platform / Website Help
        if any(p in q for p in ["how do i", "how to", "how does", "explain module", "talent sphere", "website", "application", "where can i", "how can i upload", "how can i create", "how to manage", "how to publish", "what is this app"]):
            if any(w in q for w in ["upload", "exam", "announcement", "knowledge search", "voice assistant", "user", "publish", "audit", "dashboard", "module", "lms", "portal", "feature", "document"]):
                return "WebsiteHelp"

        return "KnowledgeQuery"

    def prepare_rag_context(
        self,
        retrieved_chunks: Optional[List[Dict[str, Any]]],
        user_query: str = "",
        matched_locked: Optional[List[Dict[str, Any]]] = None
    ) -> Tuple[List[Dict[str, Any]], str, bool]:
        """
        Formats retrieved vector chunks into RAG context string & structured citations.
        Filters by similarity score to eliminate low-quality matches.
        """
        citations = []
        context_str = ""
        has_doc_context = False
        relevant_chunks = [c for c in (retrieved_chunks or []) if c.get("score", 0.0) >= 0.20 or c.get("is_study_plan", False)]

        # If query specifically matched a locked study plan day/topic, ensure we don't falsely claim generic introductory docs as sources
        if matched_locked and user_query:
            substantive_chunks = []
            locked_doc_names = {re.sub(r'\.pdf$', '', d.get("pdf_title") or d.get("title") or "").lower() for d in matched_locked}
            for chunk in relevant_chunks:
                chunk_doc = chunk.get("document_title", "").lower()
                is_from_locked = any(ld in chunk_doc for ld in locked_doc_names if len(ld) > 3)
                if not is_from_locked and chunk.get("score", 0.0) >= 0.65:
                    substantive_chunks.append(chunk)

            relevant_chunks = substantive_chunks

        if relevant_chunks:
            has_doc_context = True
            for idx, chunk in enumerate(relevant_chunks):
                doc_name = chunk.get("document_title", "Uploaded Document")
                page_num = chunk.get("page_number", 1)
                content = chunk.get("content", "").strip()
                score = chunk.get("score", 0.0)

                citations.append({
                    "document_name": doc_name,
                    "page_number": page_num,
                    "reference": content[:150] + "..." if len(content) > 150 else content
                })
                context_str += f"\n--- [Source Document #{idx+1}]: {doc_name} (Page {page_num}) [Match: {int(score*100)}%] ---\n{content}\n"

        return citations, context_str, has_doc_context

    def find_matched_locked_days(self, user_query: str, locked_study_days: Optional[List[Dict[str, Any]]]) -> List[Dict[str, Any]]:
        if not locked_study_days or self.is_casual_message(user_query):
            return []

        def norm_word(w: str) -> str:
            w = w.lower().strip()
            if len(w) > 3 and w.endswith('s') and not w.endswith('ss'):
                w = w[:-1]
            return w

        q_lower = user_query.lower()
        q_words = {norm_word(w) for w in re.findall(r'\b[a-zA-Z0-9]{3,}\b', q_lower)}
        scored_matches = []

        common_stop_words = {
            'study', 'plan', 'lesson', 'module', 'topic', 'week', 'core', 'concept',
            'the', 'and', 'for', 'with', 'day', 'pdf', 'overview', 'introduction', 'basic', 'foundation',
            'what', 'explain', 'detail', 'primary', 'classification', 'method',
            'type', 'model', 'learn', 'data', 'system'
        }

        for l_day in locked_study_days:
            title = l_day.get('title', '').lower()
            pdf_title = l_day.get('pdf_title', '').lower()
            topic = l_day.get('topic', '').lower()
            w_num = l_day.get('week_number', 1)
            d_num = l_day.get('day_number', 1)
            day_str = f"day {d_num}"
            week_day_str = f"week {w_num} day {d_num}"
            clean_title = re.sub(r'\.pdf$', '', pdf_title or title).strip()

            score = 0
            # 1. Exact title, pdf title, or day reference match
            if clean_title and len(clean_title) > 3 and clean_title in q_lower:
                score += 15
            elif clean_title and len(clean_title) > 3 and all(norm_word(part) in q_words for part in clean_title.split() if len(part) > 2):
                score += 12
            if week_day_str in q_lower:
                score += 10
            if day_str in q_lower and f"week {w_num}" in q_lower:
                score += 8

            # 2. Significant keyword matches with stopword filtering
            doc_words = {norm_word(w) for w in re.findall(r'\b[a-zA-Z0-9]{3,}\b', f"{title} {pdf_title} {topic}")}
            doc_words -= common_stop_words

            overlap = q_words.intersection(doc_words)
            score += len(overlap) * 4

            if score >= 6:
                scored_matches.append((score, l_day))

        scored_matches.sort(key=lambda x: x[0], reverse=True)
        return [item[1] for item in scored_matches]

    def build_prompt_messages(
        self,
        user_query: str,
        category: str,
        context_str: str,
        has_doc_context: bool,
        conversation_history: Optional[List[Dict[str, str]]] = None,
        unlocked_study_days: Optional[List[Dict[str, Any]]] = None,
        locked_study_days: Optional[List[Dict[str, Any]]] = None
    ) -> List[Dict[str, str]]:

        # 1. Casual Conversational Prompt
        if category == "Casual":
            system_instruction = (
                "You are an articulate, intelligent, helpful, and empathetic AI learning & performance assistant for the Talent Management Platform for Employee Performance and Career Growth.\n\n"
                "The user is engaging in casual conversation, pleasantries, greeting, or general social interaction.\n"
                "Respond naturally, warmly, politely, and conversationally like a normal ChatGPT-style assistant.\n\n"
                "IMPORTANT RULES FOR CASUAL CONVERSATION:\n"
                "- Do NOT include any document source labels (e.g., do NOT include '📄 **Source:...**').\n"
                "- Do NOT include '💡 **General answer — not from your Study Plan documents:**'.\n"
                "- Do NOT include any locked study plan reminders or '🔒 ...' footers.\n"
                "- Keep the response friendly, welcoming, and natural."
            )
            messages = [{"role": "system", "content": system_instruction}]
            if conversation_history:
                for past in conversation_history[-6:]:
                    role = "user" if past.get("role") == "user" else "assistant"
                    content = past.get("message", "").strip()
                    if content:
                        messages.append({"role": role, "content": content})
            messages.append({"role": "user", "content": user_query})
            return messages

        # 2. Knowledge / Technical / Educational Prompt
        system_instruction = (
            "You are an intelligent, articulate, empathetic, and expert learning & performance assistant for the Talent Management Platform for Employee Performance and Career Growth.\n\n"
            "STRICT KNOWLEDGE SOURCE & CITATION RULES:\n\n"
            "CASE 1 — UNLOCKED STUDY PLAN DOCUMENT (When answer is available in document context):\n"
            "- When the answer is derived from the provided UPLOADED DOCUMENT CONTEXT below (which contains only unlocked Study Plan PDFs):\n"
            "- You MUST begin your response on the very first line with:\n"
            "  **Based on your study material — Week X, Day Y:**\n"
            "  (or '**Based on your study material — [Document Title]:**')\n"
            "- Synthesize a comprehensive, clear, structured, and insightful answer based on the provided PDF content.\n\n"
            "CASE 2 — LOCKED STUDY PLAN TOPICS (When question relates to a locked Study Plan Day):\n"
            "- When the question relates to a topic from the LOCKED Study Plan Days listed below, and the answer is NOT available in unlocked documents:\n"
            "- You MUST begin your response on the very first line with:\n"
            "  **General Answer:**\n\n"
            "- Provide an educational, thorough, and structured general answer using your general knowledge without using the locked PDF text.\n\n"
            "CASE 3 — GENERAL KNOWLEDGE / UNRELATED TECHNICAL QUERIES:\n"
            "- When the question is general knowledge or technical, not found in unlocked documents and not covered in locked study plan topics:\n"
            "- Provide a direct, helpful, and insightful response from general knowledge.\n"
            "- Do NOT invent Week/Day references. Do NOT tell the user to unlock a PDF.\n\n"
            "FORMATTING & TONE:\n"
            "- Use clean Markdown: headings (###, ####), bullet points, bold terms, and code blocks where applicable.\n"
            "- Never claim to have read or accessed the text of locked PDFs.\n"
            "- Maintain multi-turn conversational context seamlessly."
        )

        messages = [{"role": "system", "content": system_instruction}]

        # Inject conversation memory history
        if conversation_history:
            for past in conversation_history[-10:]:
                role = "user" if past.get("role") == "user" else "assistant"
                content = past.get("message", "").strip()
                if content:
                    messages.append({"role": role, "content": content})

        curriculum_info = []
        if unlocked_study_days:
            unlocked_lines = [f"• {d['label']} (Status: UNLOCKED ✅ - Document content available)" for d in unlocked_study_days]
            curriculum_info.append("CURRENT USER'S UNLOCKED STUDY PLAN DOCUMENTS:\n" + "\n".join(unlocked_lines))
        if locked_study_days:
            locked_lines = [f"• {d['label']} (PDF: {d.get('pdf_title', d['title'])}) (Topic: {d.get('topic', d['title'])}) (Status: LOCKED 🔒 - Text is NOT accessible)" for d in locked_study_days]
            curriculum_info.append("LOCKED STUDY PLAN DAYS (Curriculum topics locked for this user):\n" + "\n".join(locked_lines))

        curriculum_block = ("\n\n".join(curriculum_info) + "\n\n") if curriculum_info else ""

        # Identify if query matches any locked days using scored matching
        matched_locked = self.find_matched_locked_days(user_query, locked_study_days)

        # Formulate current prompt based on category & context
        if category == "WebsiteHelp":
            prompt = (
                f"{curriculum_block}"
                f"PLATFORM USER GUIDE REQUEST:\nQuestion: {user_query}\n\n"
                f"LMS SYSTEM KNOWLEDGE BASE:\n{WEBSITE_KNOWLEDGE_BASE}\n\n"
                f"Please explain step-by-step how to perform this action in the Talent Management Platform for Employee Performance and Career Growth platform."
            )
        elif has_doc_context:
            prompt = (
                f"{curriculum_block}"
                f"UPLOADED DOCUMENT CONTEXT (Unlocked documents only):\n{context_str}\n\n"
                f"USER QUESTION:\n{user_query}\n\n"
                f"Synthesize a clear, structured, and insightful answer based on the provided document sources.\n"
                f"Begin your response on the first line with '**Based on your study material — [Week X, Day Y / Document Name]:**'."
            )
        elif matched_locked:
            locked_names = ", ".join([f"{d.get('pdf_title', d['title'])} (Week {d.get('week_number', 1)} – Day {d['day_number']})" for d in matched_locked])
            prompt = (
                f"{curriculum_block}"
                f"USER QUESTION:\n{user_query}\n\n"
                f"INSTRUCTIONS:\n"
                f"1. This question is related to the locked study material: {locked_names}.\n"
                f"2. You MUST begin your response on the very first line with:\n"
                f"   **General Answer:**\n\n"
                f"3. Provide a thorough, structured, educational answer using your general knowledge.\n"
            )
        else:
            prompt = (
                f"{curriculum_block}"
                f"USER QUESTION:\n{user_query}\n\n"
                f"Provide a thorough, structured, educational answer using your general knowledge. Do NOT invent any Study Plan references."
            )

        messages.append({"role": "user", "content": prompt})
        return messages

    def enforce_response_formatting(
        self,
        answer: str,
        category: str,
        has_doc_context: bool,
        retrieved_chunks: Optional[List[Dict[str, Any]]],
        matched_locked: List[Dict[str, Any]]
    ) -> str:
        cleaned = answer.strip()

        # 1. Casual / Conversational messages: NEVER add source headers or general answer prefixes or lock footers!
        if category == "Casual":
            cleaned = re.sub(r'\*\*Based on your study material[^\n]*\*\*\n*', '', cleaned).strip()
            cleaned = re.sub(r'📄\s*\*\*Source:[^\n]*\*\*\n*', '', cleaned).strip()
            cleaned = re.sub(r'\*\*General Answer:\*\*\n*', '', cleaned).strip()
            cleaned = re.sub(r'💡\s*\*\*General answer[^\n]*\*\*\n*', '', cleaned).strip()
            cleaned = re.sub(r'\*\*Study Material Reference:\*\*.*', '', cleaned, flags=re.DOTALL).rstrip()
            cleaned = re.sub(r'\*\*Related Study Materials:\*\*.*', '', cleaned, flags=re.DOTALL).rstrip()
            cleaned = re.sub(r'🔒\s*For detailed information from[^\n]*', '', cleaned, flags=re.DOTALL).rstrip()
            return cleaned

        # 2. CASE 1: Knowledge / Technical questions with Unlocked Study Plan PDF context:
        if has_doc_context:
            cleaned = re.sub(r'\*\*General Answer:\*\*\n*', '', cleaned).strip()
            cleaned = re.sub(r'💡\s*\*\*General answer[^\n]*\*\*\n*', '', cleaned).strip()
            cleaned = re.sub(r'\*\*Study Material Reference:\*\*.*', '', cleaned, flags=re.DOTALL).rstrip()
            cleaned = re.sub(r'\*\*Related Study Materials:\*\*.*', '', cleaned, flags=re.DOTALL).rstrip()
            cleaned = re.sub(r'🔒\s*For detailed information from[^\n]*', '', cleaned, flags=re.DOTALL).rstrip()

            # Ensure proper header format: **Based on your study material — Week X, Day Y:**
            if not cleaned.startswith("**Based on your study material"):
                first_chunk = retrieved_chunks[0] if retrieved_chunks else {}
                doc_title = first_chunk.get("document_title") or "Study Plan Document"
                if "Week " in doc_title and "Day " in doc_title:
                    # Extract Week X, Day Y
                    match = re.search(r'(Week\s+\d+,\s+Day\s+\d+)', doc_title)
                    prefix_label = match.group(1) if match else doc_title
                else:
                    prefix_label = doc_title
                cleaned = f"**Based on your study material — {prefix_label}:**\n\n{cleaned}"
            return cleaned

        # 3. CASE 2: Question relates to a LOCKED PDF
        if matched_locked:
            cleaned = re.sub(r'\*\*Based on your study material[^\n]*\*\*\n*', '', cleaned).strip()
            cleaned = re.sub(r'📄\s*\*\*Source:[^\n]*\*\*\n*', '', cleaned).strip()
            cleaned = re.sub(r'\*\*Study Material Reference:\*\*.*', '', cleaned, flags=re.DOTALL).rstrip()
            cleaned = re.sub(r'\*\*Related Study Materials:\*\*.*', '', cleaned, flags=re.DOTALL).rstrip()
            cleaned = re.sub(r'🔒\s*For detailed information[^\n]*', '', cleaned, flags=re.DOTALL).rstrip()

            if not cleaned.startswith("**General Answer:**"):
                cleaned = f"**General Answer:**\n{cleaned}"

            if len(matched_locked) == 1:
                target = matched_locked[0]
                pdf_name = target.get("pdf_title") or target.get("title") or f"Day {target['day_number']}.pdf"
                if not pdf_name.endswith(".pdf"):
                    pdf_name = f"{pdf_name}.pdf"
                w_num = target.get("week_number", 1)
                d_num = target.get("day_number", 1)

                reference_block = (
                    f"\n\n**Study Material Reference:**\n"
                    f"📄 {pdf_name}\n"
                    f"**Week {w_num} – Day {d_num} — Locked**\n\n"
                    f"⚠️ This answer is **not from your PDF**.\n"
                    f"For a detailed answer based on your study material, please unlock **Week {w_num} – Day {d_num}**."
                )
                cleaned = f"{cleaned}{reference_block}"
            else:
                lines = []
                for target in matched_locked:
                    pdf_name = target.get("pdf_title") or target.get("title") or f"Day {target['day_number']}.pdf"
                    if not pdf_name.endswith(".pdf"):
                        pdf_name = f"{pdf_name}.pdf"
                    w_num = target.get("week_number", 1)
                    d_num = target.get("day_number", 1)
                    lines.append(f"📄 {pdf_name} — **Week {w_num} – Day {d_num} — Locked**")

                materials_list = "\n".join(lines)
                reference_block = (
                    f"\n\n**Related Study Materials:**\n"
                    f"{materials_list}\n\n"
                    f"⚠️ This answer is **not from your PDFs**.\n"
                    f"Please unlock the relevant day(s) for a detailed answer based on your study material."
                )
                cleaned = f"{cleaned}{reference_block}"

            return cleaned

        # 4. CASE 3: General knowledge query (not matching unlocked or locked study material)
        cleaned = re.sub(r'\*\*Based on your study material[^\n]*\*\*\n*', '', cleaned).strip()
        cleaned = re.sub(r'📄\s*\*\*Source:[^\n]*\*\*\n*', '', cleaned).strip()
        cleaned = re.sub(r'\*\*Study Material Reference:\*\*.*', '', cleaned, flags=re.DOTALL).rstrip()
        cleaned = re.sub(r'\*\*Related Study Materials:\*\*.*', '', cleaned, flags=re.DOTALL).rstrip()
        cleaned = re.sub(r'🔒\s*For detailed information[^\n]*', '', cleaned, flags=re.DOTALL).rstrip()

        return cleaned

    def generate_response(
        self,
        user_query: str,
        retrieved_chunks: List[Dict[str, Any]] = None,
        conversation_history: List[Dict[str, str]] = None,
        unlocked_study_days: Optional[List[Dict[str, Any]]] = None,
        locked_study_days: Optional[List[Dict[str, Any]]] = None
    ) -> Tuple[str, List[Dict[str, Any]]]:
        """
        Synchronous full response generation using the centralized Groq AI provider.
        """
        category = self.classify_query(user_query)
        logger.info(f"AIService: Processing Query='{user_query}' | Category='{category}'")

        # RAG Context & Citations
        matched_locked = self.find_matched_locked_days(user_query, locked_study_days)
        citations, context_str, has_doc_context = self.prepare_rag_context(retrieved_chunks, user_query, matched_locked)

        # Build Messages Payload with Memory & Curriculum Metadata
        messages = self.build_prompt_messages(
            user_query=user_query,
            category=category,
            context_str=context_str,
            has_doc_context=has_doc_context,
            conversation_history=conversation_history,
            unlocked_study_days=unlocked_study_days,
            locked_study_days=locked_study_days
        )

        self._ensure_client()
        # 1. Primary path: Call Groq API with candidate model fallback
        if self.client:
            model_candidates = [self.model, "openai/gpt-oss-20b", "llama-3.1-8b-instant"]
            # Deduplicate preserving order
            seen_models = set()
            models_to_try = [m for m in model_candidates if m and not (m in seen_models or seen_models.add(m))]

            for candidate_model in models_to_try:
                try:
                    chat_completion = self.client.chat.completions.create(
                        messages=messages,
                        model=candidate_model,
                        temperature=0.5 if category == "Casual" else 0.4,
                        max_tokens=1500
                    )
                    raw_answer = chat_completion.choices[0].message.content
                    logger.info(f"AIService: Groq LLM ({candidate_model}) successfully generated response ({len(raw_answer)} chars).")
                    final_answer = self.enforce_response_formatting(
                        raw_answer, category, has_doc_context, retrieved_chunks, matched_locked
                    )
                    final_citations = [] if category == "Casual" else citations
                    return final_answer, final_citations
                except Exception as e:
                    logger.warning(f"AIService: Groq model '{candidate_model}' call failed: {e}. Trying next candidate...")

        # 2. Fallback path (only if all Groq models offline or key missing):
        fallback_raw = self._generate_intelligent_fallback_response(
            user_query=user_query,
            category=category,
            citations=citations,
            context_str=context_str,
            has_doc_context=has_doc_context,
            conversation_history=conversation_history,
            unlocked_study_days=unlocked_study_days,
            locked_study_days=locked_study_days
        )
        final_answer = self.enforce_response_formatting(
            fallback_raw, category, has_doc_context, retrieved_chunks, matched_locked
        )
        final_citations = [] if category == "Casual" else citations
        return final_answer, final_citations

    def generate_response_stream(
        self,
        user_query: str,
        retrieved_chunks: List[Dict[str, Any]] = None,
        conversation_history: List[Dict[str, str]] = None,
        unlocked_study_days: Optional[List[Dict[str, Any]]] = None,
        locked_study_days: Optional[List[Dict[str, Any]]] = None
    ) -> Generator[Tuple[str, List[Dict[str, Any]]], None, None]:
        """
        Token-by-token SSE streaming response generator using the centralized Groq AI provider.
        """
        category = self.classify_query(user_query)
        logger.info(f"AIService Stream: Processing Query='{user_query}' | Category='{category}'")

        matched_locked = self.find_matched_locked_days(user_query, locked_study_days)
        citations, context_str, has_doc_context = self.prepare_rag_context(retrieved_chunks, user_query, matched_locked)
        messages = self.build_prompt_messages(
            user_query=user_query,
            category=category,
            context_str=context_str,
            has_doc_context=has_doc_context,
            conversation_history=conversation_history,
            unlocked_study_days=unlocked_study_days,
            locked_study_days=locked_study_days
        )

        stream_citations = [] if category == "Casual" else citations

        self._ensure_client()
        if self.client:
            model_candidates = [self.model, "openai/gpt-oss-20b", "llama-3.1-8b-instant"]
            seen_models = set()
            models_to_try = [m for m in model_candidates if m and not (m in seen_models or seen_models.add(m))]

            for candidate_model in models_to_try:
                try:
                    response_stream = self.client.chat.completions.create(
                        messages=messages,
                        model=candidate_model,
                        temperature=0.5 if category == "Casual" else 0.4,
                        max_tokens=1500,
                        stream=True
                    )
                    for chunk in response_stream:
                        if chunk.choices and chunk.choices[0].delta and chunk.choices[0].delta.content:
                            token = chunk.choices[0].delta.content
                            yield token, stream_citations

                    # Append locked study material reference block if applicable
                    if matched_locked and not has_doc_context and category != "Casual":
                        if len(matched_locked) == 1:
                            target = matched_locked[0]
                            pdf_name = target.get("pdf_title") or target.get("title") or f"Day {target['day_number']}.pdf"
                            if not pdf_name.endswith(".pdf"):
                                pdf_name = f"{pdf_name}.pdf"
                            w_num = target.get("week_number", 1)
                            d_num = target.get("day_number", 1)
                            ref_block = (
                                f"\n\n**Study Material Reference:**\n"
                                f"📄 {pdf_name}\n"
                                f"**Week {w_num} – Day {d_num} — Locked**\n\n"
                                f"⚠️ This answer is **not from your PDF**.\n"
                                f"For a detailed answer based on your study material, please unlock **Week {w_num} – Day {d_num}**."
                            )
                        else:
                            lines = []
                            for target in matched_locked:
                                pdf_name = target.get("pdf_title") or target.get("title") or f"Day {target['day_number']}.pdf"
                                if not pdf_name.endswith(".pdf"):
                                    pdf_name = f"{pdf_name}.pdf"
                                w_num = target.get("week_number", 1)
                                d_num = target.get("day_number", 1)
                                lines.append(f"📄 {pdf_name} — **Week {w_num} – Day {d_num} — Locked**")
                            materials_list = "\n".join(lines)
                            ref_block = (
                                f"\n\n**Related Study Materials:**\n"
                                f"{materials_list}\n\n"
                                f"⚠️ This answer is **not from your PDFs**.\n"
                                f"Please unlock the relevant day(s) for a detailed answer based on your study material."
                            )
                        yield ref_block, stream_citations

                    return
                except Exception as e:
                    logger.warning(f"AIService Stream: Groq model '{candidate_model}' stream failed: {e}")

        # Fallback stream
        fallback_raw = self._generate_intelligent_fallback_response(
            user_query=user_query,
            category=category,
            citations=citations,
            context_str=context_str,
            has_doc_context=has_doc_context,
            conversation_history=conversation_history,
            unlocked_study_days=unlocked_study_days,
            locked_study_days=locked_study_days
        )
        fallback_text = self.enforce_response_formatting(
            fallback_raw, category, has_doc_context, retrieved_chunks, matched_locked
        )
        tokens = re.split(r'(\s+)', fallback_text)
        for t in tokens:
            if t:
                yield t, stream_citations
                time.sleep(0.01)

    def _get_greeting_response(self, query: str) -> str:
        q = query.strip().lower()
        if "morning" in q:
            return "Good morning! How can I help you with your courses, study materials, or questions today?"
        elif "evening" in q:
            return "Good evening! Ready to continue learning? Feel free to ask any question or let me know how I can help."
        elif "afternoon" in q:
            return "Good afternoon! What topic would you like to explore today?"
        else:
            return "Hello! How can I help you today?"

    def _generate_intelligent_fallback_response(
        self,
        user_query: str,
        category: str,
        citations: List[Dict[str, Any]],
        context_str: str,
        has_doc_context: bool,
        conversation_history: List[Dict[str, str]] = None,
        unlocked_study_days: Optional[List[Dict[str, Any]]] = None,
        locked_study_days: Optional[List[Dict[str, Any]]] = None
    ) -> str:
        q_lower = user_query.strip().lower()

        # Handle Casual / Conversational Messages
        if category == "Casual":
            if any(w in q_lower for w in ["morning", "afternoon", "evening", "hi", "hello", "hey", "howdy", "greetings"]):
                return self._get_greeting_response(user_query)
            elif any(w in q_lower for w in ["how are you", "how's it going", "how are u"]):
                return "I'm doing well, thank you! How can I help you with your learning today?"
            elif any(w in q_lower for w in ["thank", "thanks", "thx"]):
                return "You're very welcome! Feel free to ask if there's anything else you need."
            elif any(w in q_lower for w in ["bye", "goodbye", "see you", "cya"]):
                return "Goodbye! Have a great day and happy learning!"
            elif any(w in q_lower for w in ["ok", "okay", "alright", "got it", "cool", "great", "sure"]):
                return "Sounds good! Let me know whenever you'd like to explore any topic or have questions."
            elif any(w in q_lower for w in ["who are you", "what is your name", "what are you"]):
                return "I am your **AI Learning & Performance Companion** for the Talent Management Platform for Employee Performance and Career Growth. I can help answer technical questions, explain study plan topics, and assist you with your coursework."
            elif any(w in q_lower for w in ["can you help", "help me", "i need help"]):
                return "Of course! I'm here to help. What topic, question, or study plan material would you like assistance with?"
            else:
                return "Hello! How can I assist you today?"

        # Handle RAG Document Grounded Fallback (Unlocked PDF)
        if has_doc_context and citations:
            doc_name = citations[0]["document_name"]
            first_chunk = citations[0]["reference"]
            sources_summary = "\n".join([f"- **{c['document_name']}** (Page {c['page_number']})" for c in citations[:3]])

            source_header = f"📄 **Source: {doc_name}**"
            return (
                f"{source_header}\n\n"
                f"{first_chunk}\n\n"
                f"#### Cited Document Sources:\n"
                f"{sources_summary}\n\n"
                f"> **Tip**: Ask a follow-up question for further detail or practical examples."
            )

        # Check if question relates to any locked study plan day
        matched_locked_day = None
        if locked_study_days:
            for l_day in locked_study_days:
                title_words = [w.lower() for w in re.findall(r'\b\w{4,}\b', l_day.get("title", "") + " " + l_day.get("topic", ""))]
                for w in title_words:
                    if w in ["study", "plan", "lesson", "module", "topic"]:
                        continue
                    if w in q_lower:
                        matched_locked_day = l_day
                        break
                if matched_locked_day:
                    break

        # Match Topic Knowledge Base
        base_answer = ""
        for topic_key, topic_content in TOPIC_KNOWLEDGE_MAP.items():
            if topic_key in q_lower:
                base_answer = topic_content
                break

        if not base_answer:
            # Default structured educational answer
            clean_title = user_query.strip().capitalize()
            base_answer = (
                f"### Overview of {clean_title}\n\n"
                f"**{clean_title}** is an essential technical concept involving systematic principles, core architectures, and real-world implementations.\n\n"
                f"#### Core Principles:\n"
                f"1. **Fundamental Definition**: Provides a structured methodology for understanding and solving technical problems.\n"
                f"2. **Key Capabilities**: Scalable, modular, and optimized for performance in modern software and computing environments.\n"
                f"3. **Practical Applications**: Widely utilized across industry to build robust, automated systems."
            )

        return base_answer

ai_service = AIService()
