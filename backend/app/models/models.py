import uuid
from datetime import datetime
from sqlalchemy import (
    Column, String, Integer, Float, Boolean, DateTime, Text, ForeignKey, Enum as SQLEnum, Index
)
from sqlalchemy.orm import relationship
import enum
from app.core.database import Base

def generate_uuid():
    return str(uuid.uuid4())

class UserRole(str, enum.Enum):
    ADMIN = "ADMIN"
    STUDENT = "STUDENT"

class ExamStatus(str, enum.Enum):
    DRAFT = "DRAFT"
    PUBLISHED = "PUBLISHED"
    ARCHIVED = "ARCHIVED"

class AttemptStatus(str, enum.Enum):
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"

class User(Base):
    __tablename__ = "users"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    email = Column(String(255), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    full_name = Column(String(255), nullable=False)
    role = Column(SQLEnum(UserRole), default=UserRole.STUDENT, nullable=False, index=True)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    documents = relationship("Document", back_populates="uploader", cascade="all, delete-orphan")
    exams_created = relationship("Exam", back_populates="creator")
    attempts = relationship("ExamAttempt", back_populates="user", cascade="all, delete-orphan")
    announcements = relationship("Announcement", back_populates="author")
    notifications = relationship("Notification", back_populates="user", cascade="all, delete-orphan")
    chat_messages = relationship("ChatHistory", back_populates="user", cascade="all, delete-orphan")
    audit_logs = relationship("AuditLog", back_populates="user")

class Document(Base):
    __tablename__ = "documents"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    title = Column(String(255), nullable=False, index=True)
    file_path = Column(String(500), nullable=False)
    file_size = Column(Integer, nullable=False) # bytes
    mime_type = Column(String(100), default="application/pdf", nullable=False)
    uploaded_by = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    is_study_plan_doc = Column(Boolean, default=False, nullable=False)
    study_plan_day_id = Column(String(36), ForeignKey("study_plan_days.id", ondelete="SET NULL"), nullable=True, index=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    uploader = relationship("User", back_populates="documents")
    chunks = relationship("DocumentChunk", back_populates="document", cascade="all, delete-orphan")

class DocumentChunk(Base):
    __tablename__ = "document_chunks"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    document_id = Column(String(36), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True)
    chunk_index = Column(Integer, nullable=False)
    page_number = Column(Integer, default=1, nullable=False)
    content = Column(Text, nullable=False)
    vector_id = Column(String(255), nullable=True, index=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    document = relationship("Document", back_populates="chunks")

class Exam(Base):
    __tablename__ = "exams"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    title = Column(String(255), nullable=False, index=True)
    description = Column(Text, nullable=True)
    duration_minutes = Column(Integer, default=30, nullable=False)
    passing_score = Column(Float, default=70.0, nullable=False)
    status = Column(SQLEnum(ExamStatus), default=ExamStatus.DRAFT, nullable=False, index=True)
    source_document_name = Column(String(255), nullable=True)
    created_by = Column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    creator = relationship("User", back_populates="exams_created")
    questions = relationship("Question", back_populates="exam", cascade="all, delete-orphan")
    attempts = relationship("ExamAttempt", back_populates="exam", cascade="all, delete-orphan")

class Question(Base):
    __tablename__ = "questions"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    exam_id = Column(String(36), ForeignKey("exams.id", ondelete="CASCADE"), nullable=False, index=True)
    question_type = Column(String(50), default="MCQ", nullable=False) # MCQ, TrueFalse, FillBlank, ShortAnswer
    question_text = Column(Text, nullable=False)
    option_a = Column(Text, nullable=True)
    option_b = Column(Text, nullable=True)
    option_c = Column(Text, nullable=True)
    option_d = Column(Text, nullable=True)
    correct_option = Column(String(255), nullable=False) # 'A', 'B', 'C', 'D', 'True', 'False', or short answer text
    explanation = Column(Text, nullable=True)
    points = Column(Float, default=1.0, nullable=False)

    exam = relationship("Exam", back_populates="questions")
    answers = relationship("StudentAnswer", back_populates="question", cascade="all, delete-orphan")

class ExamAttempt(Base):
    __tablename__ = "exam_attempts"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    exam_id = Column(String(36), ForeignKey("exams.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    started_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    completed_at = Column(DateTime, nullable=True)
    score = Column(Float, default=0.0, nullable=False)
    passed = Column(Boolean, default=False, nullable=False)
    status = Column(SQLEnum(AttemptStatus), default=AttemptStatus.IN_PROGRESS, nullable=False)

    exam = relationship("Exam", back_populates="attempts")
    user = relationship("User", back_populates="attempts")
    answers = relationship("StudentAnswer", back_populates="attempt", cascade="all, delete-orphan")
    result = relationship("ExamResult", back_populates="attempt", uselist=False, cascade="all, delete-orphan")

class StudentAnswer(Base):
    __tablename__ = "student_answers"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    attempt_id = Column(String(36), ForeignKey("exam_attempts.id", ondelete="CASCADE"), nullable=False, index=True)
    question_id = Column(String(36), ForeignKey("questions.id", ondelete="CASCADE"), nullable=False, index=True)
    selected_option = Column(Text, nullable=True)
    is_correct = Column(Boolean, default=False, nullable=False)
    points_earned = Column(Float, default=0.0, nullable=False)

    attempt = relationship("ExamAttempt", back_populates="answers")
    question = relationship("Question", back_populates="answers")

class ExamResult(Base):
    __tablename__ = "exam_results"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    attempt_id = Column(String(36), ForeignKey("exam_attempts.id", ondelete="CASCADE"), unique=True, nullable=False, index=True)
    total_questions = Column(Integer, nullable=False)
    correct_answers = Column(Integer, nullable=False)
    score_percentage = Column(Float, nullable=False)
    passed = Column(Boolean, nullable=False)
    graded_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    attempt = relationship("ExamAttempt", back_populates="result")

class Announcement(Base):
    __tablename__ = "announcements"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    title = Column(String(255), nullable=False)
    content = Column(Text, nullable=False)
    source_document_name = Column(String(255), nullable=True)
    is_published = Column(Boolean, default=True, nullable=False)
    created_by = Column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    author = relationship("User", back_populates="announcements")

class Notification(Base):
    __tablename__ = "notifications"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    title = Column(String(255), nullable=False)
    message = Column(Text, nullable=False)
    type = Column(String(50), default="INFO", nullable=False) # DOC_UPLOAD, EXAM_PUBLISHED, ANNOUNCEMENT
    is_read = Column(Boolean, default=False, nullable=False, index=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    user = relationship("User", back_populates="notifications")

class ChatHistory(Base):
    __tablename__ = "chat_history"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    session_id = Column(String(255), default="default", nullable=False, index=True)
    role = Column(String(20), nullable=False) # 'user' or 'assistant'
    message = Column(Text, nullable=False)
    citations = Column(Text, nullable=True) # JSON string storing [{document_name, page_number, reference}]
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    user = relationship("User", back_populates="chat_messages")

class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    user_id = Column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    action = Column(String(100), nullable=False, index=True)
    entity_type = Column(String(50), nullable=False)
    entity_id = Column(String(36), nullable=True)
    details = Column(Text, nullable=True)
    ip_address = Column(String(50), nullable=True)
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False)

    user = relationship("User", back_populates="audit_logs")

class StudyPlan(Base):
    __tablename__ = "study_plans"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    title = Column(String(255), nullable=False, index=True)
    description = Column(Text, nullable=True)
    category = Column(String(100), default="General", nullable=False)
    duration_weeks = Column(Integer, default=6, nullable=False)
    status = Column(String(50), default="ACTIVE", nullable=False) # ACTIVE, DRAFT, ARCHIVED
    created_by = Column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    creator = relationship("User")
    weeks = relationship("StudyPlanWeek", back_populates="plan", cascade="all, delete-orphan", order_by="StudyPlanWeek.week_number")

class StudyPlanWeek(Base):
    __tablename__ = "study_plan_weeks"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    plan_id = Column(String(36), ForeignKey("study_plans.id", ondelete="CASCADE"), nullable=False, index=True)
    exam_id = Column(String(36), ForeignKey("exams.id", ondelete="SET NULL"), nullable=True, index=True)
    week_number = Column(Integer, nullable=False)
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    exam_status = Column(String(50), default="PENDING", nullable=False) # PENDING, READY, FAILED
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    plan = relationship("StudyPlan", back_populates="weeks")
    exam = relationship("Exam")
    days = relationship("StudyPlanDay", back_populates="week", cascade="all, delete-orphan", order_by="StudyPlanDay.day_number")

class StudyPlanDay(Base):
    __tablename__ = "study_plan_days"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    week_id = Column(String(36), ForeignKey("study_plan_weeks.id", ondelete="CASCADE"), nullable=False, index=True)
    day_number = Column(Integer, nullable=False)
    title = Column(String(255), nullable=False)
    topic = Column(String(255), nullable=True)
    content_summary = Column(Text, nullable=True)
    has_lesson = Column(Boolean, default=True, nullable=False)
    lesson_title = Column(String(255), nullable=True)
    lesson_content = Column(Text, nullable=True)
    document_id = Column(String(36), ForeignKey("documents.id", ondelete="SET NULL"), nullable=True, index=True)
    pdf_title = Column(String(255), nullable=True)
    pdf_file_path = Column(String(500), nullable=True)
    pdf_extracted_text = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    week = relationship("StudyPlanWeek", back_populates="days")
    document = relationship("Document", foreign_keys=[document_id])

class UserStudyPlanProgress(Base):
    __tablename__ = "user_study_plan_progress"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    plan_id = Column(String(36), ForeignKey("study_plans.id", ondelete="CASCADE"), nullable=False, index=True)
    current_week_number = Column(Integer, default=1, nullable=False)
    current_day_number = Column(Integer, default=1, nullable=False)
    completed_days_json = Column(Text, default="[]", nullable=False)
    completed_weeks_json = Column(Text, default="[]", nullable=False)
    day_page_progress_json = Column(Text, default="{}", nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    user = relationship("User")
    plan = relationship("StudyPlan")



