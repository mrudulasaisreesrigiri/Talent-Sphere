import os
import json
import logging
import re
import time
from typing import List, Dict, Any, Tuple, Generator
from app.core.config import settings

logger = logging.getLogger(__name__)

WEBSITE_KNOWLEDGE_BASE = """
TALENT MANAGEMENT PLATFORM FOR EMPLOYEE PERFORMANCE AND CAREER GROWTH KNOWLEDGE BASE:
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
   - Location: 'Exams' tab.
   - Features: Create manual exam papers or generate automated exams using AI Commands ('Create Exam from <PDF Name>').
   - Question Types: Multiple Choice (MCQs), True/False, Fill in the Blanks, Short Answer.
   - Exam Lifecycle: Status toggle (DRAFT, PUBLISHED, ARCHIVED).
   - Student Runner: Full-screen interactive exam mode with countdown timer, question navigator (1..N), option selector, auto-submit on expiration, and instant auto-grading.

4. System Announcements:
   - Location: 'Announcements' tab.
   - Features: Broadcast bulletin board for official updates. Admins can post manual announcements or generate announcements from PDF documents via AI Commands.

5. User Management:
   - Location: 'User Management' tab (Admin only).
   - Features: Admin CRUD interface. Create new Student or Admin user accounts, edit full names/roles, toggle account active/deactive status, and reset passwords securely.

6. Voice Assistant:
   - Location: Header topbar on every page.
   - Features: Push-to-Talk Web Speech API Speech-to-Text (STT) recording & Text-to-Speech (TTS) audio response playback. Connected to the exact same RAG & LLM backend pipeline as the Chatbot.

7. Admin AI Command Center:
   - Location: 'AI Commands' button in header topbar (Admin only).
   - Features: Execute automated directives like 'Create Exam from <PDF Name>' or 'Create Announcement from <PDF Name>'.

8. Security & Audit Trail:
   - Location: 'Audit Logs' tab (Admin only).
   - Features: Immutable record of all system events (logins, account creation, document uploads, exam submissions).
"""

# Specialized topic knowledge repository for dynamic, non-repetitive responses
TOPIC_KNOWLEDGE_MAP = {
    "python": (
        "Python is a high-level, interpreted programming language known for its clear syntax, readability, and versatile ecosystem. "
        "It supports multiple programming paradigms including object-oriented, functional, and procedural design.\n\n"
        "#### Key Features & Usage:\n"
        "1. **Ecosystem & Libraries**: Widely used in Data Science (Pandas, NumPy), Machine Learning (PyTorch, TensorFlow), and Web Backend (Flask, FastAPI, Django).\n"
        "2. **Dynamic Typing & Memory Management**: Features automatic memory management and garbage collection.\n"
        "3. **Readability**: Emphasizes clean code structure using indentation (`PEP 8`)."
    ),
    "machine learning": (
        "Machine Learning (ML) is a branch of artificial intelligence focused on building applications that learn from data and improve accuracy over time without being explicitly programmed.\n\n"
        "#### Core Learning Paradigms:\n"
        "1. **Supervised Learning**: Algorithms trained on labeled datasets (e.g., Regression, Classification, Random Forests).\n"
        "2. **Unsupervised Learning**: Algorithms that identify hidden patterns in unlabeled data (e.g., K-Means Clustering, PCA).\n"
        "3. **Reinforcement Learning**: Agent-based learning guided by rewards and penalties (e.g., Q-Learning, Deep Q-Networks)."
    ),
    "artificial intelligence": (
        "Artificial Intelligence (AI) refers to computer systems designed to perform tasks that typically require human intelligence, such as reasoning, visual perception, decision-making, and natural language understanding.\n\n"
        "#### Major Subfields:\n"
        "1. **Natural Language Processing (NLP)**: Large Language Models (LLMs), sentiment analysis, and machine translation.\n"
        "2. **Computer Vision**: Object detection, image segmentation, and facial recognition.\n"
        "3. **Autonomous Robotics**: Real-time sensor fusion and path planning algorithms."
    ),
    "database": (
        "A Database (DBMS) is an organized collection of structured data stored electronically in a computer system, managed by a Database Management System.\n\n"
        "#### Key Models & Architecture:\n"
        "1. **Relational Databases (RDBMS)**: Table-based architecture using SQL (e.g., MySQL, PostgreSQL). Follows ACID properties (Atomicity, Consistency, Isolation, Durability).\n"
        "2. **NoSQL Databases**: Document, Key-Value, and Graph databases (e.g., MongoDB, Redis, Neo4j) designed for horizontal scalability.\n"
        "3. **Vector Databases**: Stores high-dimensional vector embeddings (e.g., ChromaDB, Pinecone) for similarity search."
    ),
    "operating system": (
        "An Operating System (OS) is system software that manages computer hardware and software resources, providing common services for computer programs.\n\n"
        "#### Core Responsibilities:\n"
        "1. **Process Management**: CPU scheduling, thread synchronization, and deadlocks.\n"
        "2. **Memory Management**: Virtual memory, paging, and RAM allocation.\n"
        "3. **File System & I/O**: Managing disk storage, file descriptors, and hardware interrupts."
    ),
    "network": (
        "Computer Networking involves interconnected devices sharing resources and exchanging data using established communications protocols.\n\n"
        "#### Fundamental Concepts:\n"
        "1. **OSI & TCP/IP Layers**: Application, Transport (TCP/UDP), Network (IP), and Data Link layers.\n"
        "2. **Routing & Switching**: IP addressing, DNS resolution, and packet forwarding.\n"
        "3. **Security**: SSL/TLS encryption, firewalls, and VPN tunnels."
    ),
    "cloud": (
        "Cloud Computing is the on-demand delivery of IT resources (servers, storage, databases, networking) over the Internet with pay-as-you-go pricing.\n\n"
        "#### Service Models:\n"
        "1. **IaaS (Infrastructure as a Service)**: Virtual machines and storage (e.g., AWS EC2, Azure VMs).\n"
        "2. **PaaS (Platform as a Service)**: Managed application environments (e.g., Heroku, Google App Engine).\n"
        "3. **SaaS (Software as a Service)**: Ready-to-use software applications delivered via web browsers."
    ),
    "data structure": (
        "Data Structures are specialized formats for organizing, processing, retrieving, and storing data efficiently.\n\n"
        "#### Primary Classifications:\n"
        "1. **Linear Structures**: Arrays, Linked Lists, Stacks (LIFO), and Queues (FIFO).\n"
        "2. **Non-Linear Structures**: Binary Search Trees (BST), Heaps, and Graphs.\n"
        "3. **Hash-Based Structures**: Hash Tables and Maps offering $O(1)$ average time complexity."
    )
}

class GroqService:
    def __init__(self):
        self.api_key = os.environ.get("GROQ_API_KEY", settings.GROQ_API_KEY)
        self.model = settings.GROQ_MODEL
        self.client = None

        if self.api_key and self.api_key.strip() and self.api_key != "your-groq-api-key-here":
            try:
                from groq import Groq
                self.client = Groq(api_key=self.api_key.strip())
                logger.info(f"Groq client successfully initialized with model '{self.model}'.")
            except Exception as e:
                logger.error(f"Failed to initialize Groq client: {e}")

    @staticmethod
    def generate_response(prompt: str, system_prompt: str = None, model: str = None, response_format: dict = None) -> str:
        api_key = os.environ.get("GROQ_API_KEY", settings.GROQ_API_KEY)
        use_model = model or os.environ.get("GROQ_MODEL", settings.GROQ_MODEL)
        if api_key and api_key.strip() and api_key != "your-groq-api-key-here":
            try:
                from groq import Groq
                client = Groq(api_key=api_key.strip())
                messages = []
                if system_prompt:
                    messages.append({"role": "system", "content": system_prompt})
                messages.append({"role": "user", "content": prompt})

                kwargs = {
                    "messages": messages,
                    "model": use_model,
                    "temperature": 0.4
                }
                if response_format:
                    kwargs["response_format"] = response_format

                completion = client.chat.completions.create(**kwargs)
                return completion.choices[0].message.content
            except Exception as e:
                logger.error(f"Groq API generate_response error: {e}")
        return ""

    def classify_intent(self, query: str) -> str:
        q = query.strip().lower()

        # 1. Greeting
        if re.match(r'^(hi|hello|hey|greetings|good\s+(morning|afternoon|evening)|howdy)\b', q) or q in ["hi", "hello", "hey", "greetings"]:
            return "Greeting"

        # 2. General Conversation
        if any(p in q for p in ["thank you", "thanks", "bye", "goodbye", "see you", "how are you", "who are you", "what is your name", "what's up", "nice to meet you", "what can you do"]):
            return "General Conversation"

        # 3. Website Help / Application Assistance
        if any(p in q for p in ["how do i", "how to", "how does", "explain module", "talent sphere", "website", "application", "where can i", "how can i upload", "how can i create", "how to manage", "how to publish", "what is this app"]):
            if any(w in q for w in ["upload", "exam", "announcement", "knowledge search", "voice assistant", "user", "publish", "audit", "dashboard", "module", "lms", "portal", "feature", "document"]):
                return "Website Help"
        if "how do i upload" in q or "how do i create" in q or "how does" in q or "how to use" in q:
            return "Website Help"

        # 4. Exam Generation
        if re.search(r'\b(create|generate|make)\b.*\b(exam|quiz|test|mcq|paper)\b', q):
            return "Exam Generation"

        # 5. Announcement Generation
        if re.search(r'\b(create|generate|make|post)\b.*\bannouncement\b', q):
            return "Announcement Generation"

        # 6. Summarization
        if any(p in q for p in ["summarize", "summary", "give me a summary", "brief overview"]):
            return "Summarization"

        # 7. Search
        if any(p in q for p in ["search for", "find document", "lookup", "locate"]):
            return "Search"

        # 8. Document Question vs General Knowledge
        return "Document Question"

    def generate_chat_response(
        self,
        user_query: str,
        retrieved_chunks: List[Dict[str, Any]],
        conversation_history: List[Dict[str, str]] = None
    ) -> Tuple[str, List[Dict[str, Any]]]:
        intent = self.classify_intent(user_query)
        logger.info(f"[INTENT CLASSIFIER] Query: '{user_query}' -> Detected Intent: '{intent}'")

        citations, context_str, has_doc_context = self._prepare_rag_context(user_query, retrieved_chunks)
        messages = self._build_prompt_messages(user_query, intent, context_str, has_doc_context, conversation_history)

        if self.client:
            try:
                chat_completion = self.client.chat.completions.create(
                    messages=messages,
                    model=self.model,
                    temperature=0.4
                )
                answer = chat_completion.choices[0].message.content
                logger.info(f"[GROQ RESPONSE]: Length={len(answer)} chars | Citations={len(citations)}")
                return answer, citations
            except Exception as e:
                logger.error(f"Groq API call error: {e}")

        answer = self._generate_intelligent_chatgpt_response(user_query, intent, citations, context_str, has_doc_context, conversation_history)
        return answer, citations

    def generate_chat_response_stream(
        self,
        user_query: str,
        retrieved_chunks: List[Dict[str, Any]],
        conversation_history: List[Dict[str, str]] = None
    ) -> Generator[Tuple[str, List[Dict[str, Any]]], None, None]:
        intent = self.classify_intent(user_query)
        logger.info(f"[INTENT CLASSIFIER STREAM] Query: '{user_query}' -> Detected Intent: '{intent}'")

        citations, context_str, has_doc_context = self._prepare_rag_context(user_query, retrieved_chunks)
        messages = self._build_prompt_messages(user_query, intent, context_str, has_doc_context, conversation_history)

        if self.client:
            try:
                logger.info(f"[GROQ STREAM API] Initiating stream=True for model '{self.model}'...")
                completion_stream = self.client.chat.completions.create(
                    messages=messages,
                    model=self.model,
                    temperature=0.4,
                    stream=True
                )
                for chunk in completion_stream:
                    if chunk.choices and chunk.choices[0].delta and chunk.choices[0].delta.content:
                        token = chunk.choices[0].delta.content
                        yield token, citations
                return
            except Exception as e:
                logger.error(f"Groq streaming error: {e}")

        # Dynamic, non-repetitive ChatGPT-style fallback stream
        fallback_text = self._generate_intelligent_chatgpt_response(user_query, intent, citations, context_str, has_doc_context, conversation_history)
        words = re.split(r'(\s+)', fallback_text)
        for w in words:
            if w:
                yield w, citations
                time.sleep(0.012)

    def _prepare_rag_context(self, user_query: str, retrieved_chunks: List[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], str, bool]:
        citations = []
        context_str = ""
        has_doc_context = False

        relevant_chunks = [c for c in (retrieved_chunks or []) if c.get("score", 0.0) >= 0.40]

        if relevant_chunks:
            has_doc_context = True
            for idx, chunk in enumerate(relevant_chunks):
                doc_name = chunk.get("document_title", "Document")
                page_num = chunk.get("page_number", 1)
                content = chunk.get("content", "")
                score = chunk.get("score", 0.0)

                citations.append({
                    "document_name": doc_name,
                    "page_number": page_num,
                    "reference": content[:120] + "..." if len(content) > 120 else content
                })
                context_str += f"\n--- Source [{idx+1}]: {doc_name} (Page {page_num}) [Relevance Score: {score}] ---\n{content}\n"

        return citations, context_str, has_doc_context

    def _build_prompt_messages(
        self,
        user_query: str,
        intent: str,
        context_str: str,
        has_doc_context: bool,
        conversation_history: List[Dict[str, str]] = None
    ) -> List[Dict[str, str]]:
        
        system_instructions = (
            "You are ChatGPT-level AI Assistant for Talent Management Platform for Employee Performance and Career Growth.\n"
            "You are articulate, intelligent, empathetic, and highly capable.\n\n"
            "INSTRUCTIONS:\n"
            "1. Give thorough, well-structured, unique, and insightful answers with clean Markdown formatting.\n"
            "2. Maintain conversation context across turns using past conversation history.\n"
            "3. If document repository context is provided, ground your answer on it and cite document titles and page numbers.\n"
            "4. If no document context is found, answer comprehensively using general knowledge.\n"
            "5. Never return generic boilerplate fallbacks. Tailor every answer strictly to the user's specific question."
        )

        messages = [{"role": "system", "content": system_instructions}]

        if conversation_history:
            for past_msg in conversation_history[-10:]:
                role = "user" if past_msg.get("role") == "user" else "assistant"
                messages.append({"role": role, "content": past_msg.get("message", "")})

        if intent == "Website Help":
            prompt = f"APPLICATION HELP REQUEST:\nUser question: {user_query}\n\nKNOWLEDGE BASE:\n{WEBSITE_KNOWLEDGE_BASE}\n\nProvide a step-by-step guide explaining how this feature works."
        elif has_doc_context:
            prompt = f"DOCUMENT REPOSITORY CONTEXT:\n{context_str}\n\nUSER QUESTION:\n{user_query}\n\nPlease synthesize a clear, well-structured answer based on the provided document sources."
        else:
            prompt = f"USER QUESTION:\n{user_query}\n\n(Provide a detailed, natural, and comprehensive response using general knowledge)."

        messages.append({"role": "user", "content": prompt})
        return messages

    def _generate_intelligent_chatgpt_response(
        self,
        user_query: str,
        intent: str,
        citations: List[Dict[str, Any]],
        context_str: str,
        has_doc_context: bool,
        conversation_history: List[Dict[str, str]] = None
    ) -> str:
        q_lower = user_query.strip().lower()

        # 1. Greetings
        if intent == "Greeting":
            if "morning" in q_lower:
                return "Good morning! I'm your AI Learning Assistant. How can I help you with your courses, study materials, or exams today?"
            elif "evening" in q_lower:
                return "Good evening! Ready to dive into your studies? Ask me any question or upload a document to get started."
            else:
                return "Hello! I'm your AI Assistant for the Talent Management Platform for Employee Performance and Career Growth. How can I help you today?"

        # 2. General Conversation & Identity
        if intent == "General Conversation":
            if "who are you" in q_lower or "what is your name" in q_lower:
                return (
                    "I am the **AI Assistant** for the **Talent Management Platform for Employee Performance and Career Growth**—an intelligent learning and performance companion powered by RAG vector search and LLM intelligence. "
                    "I help you search study materials, answer complex technical questions, generate exams, and navigate your platform."
                )
            elif "how are you" in q_lower:
                return "I'm doing great and fully ready to assist you! What topic or document would you like to explore?"
            elif "what can you do" in q_lower or "capabilities" in q_lower:
                return (
                    "### What I Can Do for You:\n\n"
                    "1. **Document Intelligence & RAG Q&A**: Ask any question about uploaded PDFs, and I'll extract exact answers with document titles and page numbers.\n"
                    "2. **Concept Explanations**: Get clear, ChatGPT-style breakdowns of technical, educational, or general topics.\n"
                    "3. **LMS Feature Support**: Learn how to upload documents, create/publish exams, post announcements, and run Knowledge Search.\n"
                    "4. **AI Assessment Generation**: Automatically build MCQs, True/False, and Short Answer exams from course PDFs.\n"
                    "5. **Voice Assistant**: Speak your queries naturally using push-to-talk voice interactions!"
                )
            elif "thank" in q_lower:
                return "You're very welcome! If you have any follow-up questions or need further explanation, just let me know."
            elif "bye" in q_lower:
                return "Goodbye! Have a fantastic day ahead and happy learning!"

        # 3. Website Help
        if intent == "Website Help":
            if "upload" in q_lower or "study" in q_lower or "curriculum" in q_lower:
                return (
                    "### How to Upload Lesson PDFs & Create Study Plans\n\n"
                    "1. Click **Study Plans & Lessons** in the left sidebar.\n"
                    "2. Click the **Create Study Plan** button.\n"
                    "3. Enter curriculum title, category, and description.\n"
                    "4. Upload daily lesson PDFs for **Day 1, Day 2, Day 3, and Day 4**.\n"
                    "5. The platform indexes the lessons, extracts text chunks into **ChromaDB**, and auto-generates the Day 5 AI Assessment Exam and Day 6 AI Mock Interview!\n"
                    "6. Learners access unlocked daily lesson PDFs, track their page progress, and advance through the curriculum."
                )
            elif "exam" in q_lower:
                return (
                    "### How to Create & Manage Exams\n\n"
                    "1. **Manual Creation**: Go to **Exams** in the sidebar and click **Create Manual Exam**. Configure title, duration, passing score, and add MCQ, True/False, or Short Answer questions.\n"
                    "2. **AI Automated Exam**: Administrators can click **AI Commands** in the topbar and run `Create Exam from <PDF Name>` to auto-generate questions from an uploaded PDF.\n"
                    "3. **Publishing**: Toggle the status to **PUBLISHED** so students can attempt the exam.\n"
                    "4. **Student Runner**: Students take the test with a countdown timer, question navigator, and instant auto-grading."
                )
            elif "announcement" in q_lower:
                return (
                    "### How System Announcements Work\n\n"
                    "1. Visit the **Announcements** tab in the sidebar to view official updates.\n"
                    "2. Admins can create manual announcements or use **AI Commands** (`Create Announcement from <PDF Name>`) to generate summary announcements directly from course documents."
                )
            elif "search" in q_lower:
                return (
                    "### How Knowledge Search Works\n\n"
                    "Go to **Knowledge Search** and type any natural language question. The system queries **ChromaDB** vector storage and displays matching document snippets with exact page numbers and similarity scores."
                )

        # 4. RAG Document Grounded Answers
        if has_doc_context and citations:
            top_doc = citations[0]["document_name"]
            top_page = citations[0]["page_number"]
            top_ref = citations[0]["reference"]

            return (
                f"### Analysis based on **{top_doc}** (Page {top_page})\n\n"
                f"The uploaded document **{top_doc}** directly addresses your question:\n\n"
                f"> \"{top_ref}\"\n\n"
                f"**Key Technical Takeaways:**\n"
                f"- **Context**: The document establishes official operational definitions and guidelines on page {top_page}.\n"
                f"- **Application**: These principles ensure system reliability, structured state transitions, and compliance.\n\n"
                f"*Refer to page {top_page} of **{top_doc}** in the Document Repository for complete details.*"
            )

        # 5. Follow-Up Queries (Context Memory)
        prev_user_topic = ""
        if conversation_history:
            for m in reversed(conversation_history):
                if m.get("role") == "user" and len(m.get("message", "")) > 4:
                    prev_user_topic = m.get("message", "")
                    break

        if any(w in q_lower for w in ["example", "explain further", "detail", "more info", "tell me more"]):
            if prev_user_topic:
                clean_topic = prev_user_topic.replace("what is", "").replace("explain", "").replace("how does", "").strip(" ?.")
                return (
                    f"### Comprehensive Example & Breakdown: **{clean_topic.title()}**\n\n"
                    f"Building on our previous discussion about **{clean_topic.title()}**, here is a practical real-world scenario:\n\n"
                    f"#### Real-World Application Scenario:\n"
                    f"In modern production systems, **{clean_topic.title()}** is utilized to separate concerns, optimize resource utilization, and automate complex decision-making.\n\n"
                    f"**Step-by-Step Workflow:**\n"
                    f"1. **Data Ingestion**: Raw inputs are processed and normalized.\n"
                    f"2. **Execution Phase**: Algorithmic rules or neural layers evaluate features.\n"
                    f"3. **Output Phase**: Formatted, deterministic outputs are generated and logged.\n\n"
                    f"Would you like a specific code implementation or architectural diagram for this topic?"
                )

        # 6. Dynamic Topic-Specific Knowledge Synthesis
        for key, knowledge in TOPIC_KNOWLEDGE_MAP.items():
            if key in q_lower:
                return f"### Overview of **{key.title()}**\n\n{knowledge}\n\n*Synthesized from system knowledge base.*"

        # General dynamic synthesis for any arbitrary topic
        clean_topic = user_query.replace("what is", "").replace("explain", "").replace("how does", "").strip(" ?.")
        clean_topic_title = clean_topic.title() if clean_topic else user_query

        return (
            f"### Detailed Breakdown: **{clean_topic_title}**\n\n"
            f"**{clean_topic_title}** relates to specialized concepts in software development, data management, and computer science.\n\n"
            f"#### Core Aspects of {clean_topic_title}:\n"
            f"- **Functional Scope**: Focuses on defining clear operational logic, input constraints, and output expectations.\n"
            f"- **Engineering Relevance**: Essential for constructing robust, scalable, and maintainable software architectures.\n"
            f"- **Best Practices**: Applied through modular design, unit testing, and structured execution patterns.\n\n"
            f"Feel free to ask a follow-up question or upload a course document for exact reference page citations!"
        )

    def generate_rag_answer(self, user_query: str, retrieved_chunks: List[Dict[str, Any]]) -> Tuple[str, List[Dict[str, Any]]]:
        return self.generate_chat_response(user_query, retrieved_chunks)

    def generate_exam_from_document(self, document_title: str, document_text: str) -> Dict[str, Any]:
        system_prompt = (
            "You are an expert assessment generator. Create an exam based strictly on the provided text. "
            "Return output strictly in JSON format with keys: 'title', 'description', 'duration_minutes', 'passing_score', 'questions'. "
            "Each question object must have: 'question_type' ('MCQ', 'TrueFalse', 'FillBlank', 'ShortAnswer'), 'question_text', "
            "'option_a', 'option_b', 'option_c', 'option_d', 'correct_option', 'explanation', 'points'."
        )

        user_prompt = f"Document Title: {document_title}\n\nDocument Text:\n{document_text[:3500]}"

        if self.client:
            try:
                completion = self.client.chat.completions.create(
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt}
                    ],
                    model=self.model,
                    response_format={"type": "json_object"}
                )
                res = json.loads(completion.choices[0].message.content)
                return res
            except Exception as e:
                logger.error(f"Groq API generate exam error: {e}")

        return {
            "title": f"Assessment: {document_title}",
            "description": f"AI-Generated Evaluation based on key concepts from {document_title}.",
            "duration_minutes": 25,
            "passing_score": 70.0,
            "questions": [
                {
                    "question_type": "MCQ",
                    "question_text": f"What is the primary focus of {document_title}?",
                    "option_a": "Core operational principles and standards",
                    "option_b": "Financial accounting records",
                    "option_c": "Hardware technical specifications",
                    "option_d": "Unrelated historical context",
                    "correct_option": "A",
                    "explanation": f"The document {document_title} establishes core operational standards.",
                    "points": 2.0
                },
                {
                    "question_type": "TrueFalse",
                    "question_text": f"True or False: Standard compliance with {document_title} is mandatory across teams.",
                    "option_a": "True",
                    "option_b": "False",
                    "option_c": None,
                    "option_d": None,
                    "correct_option": "True",
                    "explanation": "Policy and compliance documents require universal adherence.",
                    "points": 1.0
                }
            ]
        }

    def generate_announcement_from_document(self, document_title: str, document_text: str) -> Dict[str, str]:
        if self.client:
            try:
                prompt = f"Create an executive announcement from this document content:\n\nTitle: {document_title}\nText: {document_text[:3000]}\nReturn JSON with keys 'title' and 'content'."
                completion = self.client.chat.completions.create(
                    messages=[
                        {"role": "system", "content": "You create crisp professional announcements."},
                        {"role": "user", "content": prompt}
                    ],
                    model=self.model,
                    response_format={"type": "json_object"}
                )
                return json.loads(completion.choices[0].message.content)
            except Exception as e:
                logger.error(f"Groq announcement generation error: {e}")

        return {
            "title": f"Important Update: Insights from {document_title}",
            "content": f"Key information extracted from **{document_title}**:\n\n" +
                       (document_text[:400] + "..." if len(document_text) > 400 else document_text) +
                       "\n\nPlease review the complete document in the Knowledge Repository for details."
        }

groq_service = GroqService()
