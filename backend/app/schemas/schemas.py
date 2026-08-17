from pydantic import BaseModel, EmailStr, Field
from typing import Optional, List, Any
from datetime import datetime
from app.models.models import UserRole, ExamStatus, AttemptStatus

# Token Schemas
class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: "UserOut"

class TokenPayload(BaseModel):
    sub: Optional[str] = None
    role: Optional[str] = None

# User Schemas
class UserCreate(BaseModel):
    email: EmailStr
    full_name: str
    password: str
    role: UserRole = UserRole.STUDENT
    is_active: bool = True

class UserUpdate(BaseModel):
    full_name: Optional[str] = None
    email: Optional[EmailStr] = None
    role: Optional[UserRole] = None
    is_active: Optional[bool] = None

class PasswordReset(BaseModel):
    new_password: str

class UserOut(BaseModel):
    id: str
    email: str
    full_name: str
    role: UserRole
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True

# Document Schemas
class DocumentOut(BaseModel):
    id: str
    title: str
    file_path: str
    file_size: int
    mime_type: str
    uploaded_by: Optional[str] = None
    is_study_plan_doc: bool = False
    study_plan_day_id: Optional[str] = None
    created_at: datetime
    chunk_count: Optional[int] = 0

    class Config:
        from_attributes = True

class DocumentRename(BaseModel):
    title: str

# Exam & Question Schemas
class QuestionCreate(BaseModel):
    question_type: str = "MCQ"
    question_text: str
    option_a: Optional[str] = None
    option_b: Optional[str] = None
    option_c: Optional[str] = None
    option_d: Optional[str] = None
    correct_option: str
    explanation: Optional[str] = None
    points: float = 1.0

class QuestionOut(BaseModel):
    id: str
    exam_id: str
    question_type: str
    question_text: str
    option_a: Optional[str] = None
    option_b: Optional[str] = None
    option_c: Optional[str] = None
    option_d: Optional[str] = None
    points: float
    explanation: Optional[str] = None

    class Config:
        from_attributes = True

class ExamCreate(BaseModel):
    title: str
    description: Optional[str] = None
    duration_minutes: int = 30
    passing_score: float = 70.0
    status: ExamStatus = ExamStatus.DRAFT
    questions: Optional[List[QuestionCreate]] = []

class ExamUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    duration_minutes: Optional[int] = None
    passing_score: Optional[float] = None
    status: Optional[ExamStatus] = None

class ExamOut(BaseModel):
    id: str
    title: str
    description: Optional[str] = None
    duration_minutes: int
    passing_score: float
    status: ExamStatus
    source_document_name: Optional[str] = None
    created_at: datetime
    question_count: Optional[int] = 0

    class Config:
        from_attributes = True

class StudentAnswerSubmit(BaseModel):
    question_id: str
    selected_option: str

class ExamSubmission(BaseModel):
    answers: List[StudentAnswerSubmit]

class ExamAttemptOut(BaseModel):
    id: str
    exam_id: str
    user_id: str
    started_at: datetime
    completed_at: Optional[datetime] = None
    score: float
    passed: bool
    status: AttemptStatus

    class Config:
        from_attributes = True

class ExamResultOut(BaseModel):
    id: str
    attempt_id: str
    total_questions: int
    correct_answers: int
    score_percentage: float
    passed: bool
    graded_at: datetime

    class Config:
        from_attributes = True

# Announcement Schemas
class AnnouncementCreate(BaseModel):
    title: str
    content: str
    source_document_name: Optional[str] = None
    is_published: bool = True

class AnnouncementOut(BaseModel):
    id: str
    title: str
    content: str
    source_document_name: Optional[str] = None
    is_published: bool
    created_at: datetime

    class Config:
        from_attributes = True

# Notification Schemas
class NotificationOut(BaseModel):
    id: str
    title: str
    message: str
    type: str
    is_read: bool
    created_at: datetime

    class Config:
        from_attributes = True

# Chat & AI Schemas
class Citation(BaseModel):
    document_name: str
    page_number: int
    reference: str

class ChatMessageRequest(BaseModel):
    message: str
    session_id: str = "default"

class ChatMessageOut(BaseModel):
    id: str
    session_id: str
    role: str
    message: str
    citations: Optional[List[Citation]] = None
    created_at: datetime

    class Config:
        from_attributes = True

class AICommandRequest(BaseModel):
    command: str  # e.g., "Create Exam from <DocName>" or "Create Announcement from <DocName>"
    document_name: Optional[str] = None

# Search & Analytics Schemas
class KnowledgeSearchResult(BaseModel):
    document_id: str
    document_title: str
    page_number: int
    content: str
    score: float

class DashboardAnalyticsOut(BaseModel):
    total_users: int
    total_documents: int
    total_study_plans: Optional[int] = 0
    total_exams: int
    students_attempted: int
    highest_score: float
    lowest_score: float
    average_score: float
    performance_trends: List[dict]
    exam_trends: List[dict]
    document_trends: List[dict]
    monthly_analytics: List[dict]

class AuditLogOut(BaseModel):
    id: str
    user_id: Optional[str] = None
    action: str
    entity_type: str
    entity_id: Optional[str] = None
    details: Optional[str] = None
    timestamp: datetime

    class Config:
        from_attributes = True

# Study Plan Schemas
class StudyPlanCreate(BaseModel):
    title: str
    description: Optional[str] = None
    category: Optional[str] = "General"
    duration_weeks: Optional[int] = 4
    status: Optional[str] = "ACTIVE"

class StudyPlanUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    category: Optional[str] = None
    duration_weeks: Optional[int] = None
    status: Optional[str] = None

class StudyPlanDayUpdate(BaseModel):
    lesson_title: Optional[str] = None
    lesson_content: Optional[str] = None

class StudyPlanDayOut(BaseModel):
    id: str
    week_id: str
    day_number: int
    title: str
    topic: Optional[str] = None
    content_summary: Optional[str] = None
    has_lesson: bool = True
    lesson_title: Optional[str] = None
    lesson_content: Optional[str] = None
    document_id: Optional[str] = None
    pdf_title: Optional[str] = None
    pdf_file_path: Optional[str] = None

    class Config:
        from_attributes = True

class StudyPlanWeekOut(BaseModel):
    id: str
    plan_id: str
    exam_id: Optional[str] = None
    exam_status: str = "PENDING"
    week_number: int
    title: str
    description: Optional[str] = None
    days: List[StudyPlanDayOut] = []

    class Config:
        from_attributes = True

class StudyPlanOut(BaseModel):
    id: str
    title: str
    description: Optional[str] = None
    category: str
    duration_weeks: int
    status: str
    created_by: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    weeks: List[StudyPlanWeekOut] = []

    class Config:
        from_attributes = True

