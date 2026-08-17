export type UserRole = 'ADMIN' | 'STUDENT';
export type ExamStatus = 'DRAFT' | 'PUBLISHED' | 'ARCHIVED';
export type AttemptStatus = 'IN_PROGRESS' | 'COMPLETED';

export interface User {
  id: string;
  email: string;
  full_name: string;
  role: UserRole;
  is_active: boolean;
  created_at: string;
}

export interface DocumentItem {
  id: string;
  title: string;
  file_path: string;
  file_size: number;
  mime_type: string;
  uploaded_by: string;
  is_study_plan_doc?: boolean;
  study_plan_day_id?: string;
  created_at: string;
  chunk_count?: number;
}

export interface Question {
  id: string;
  exam_id: string;
  question_type: string;
  question_text: string;
  option_a?: string;
  option_b?: string;
  option_c?: string;
  option_d?: string;
  points: number;
  explanation?: string;
}

export interface QuestionCreate {
  question_type: 'MCQ' | 'TrueFalse' | 'FillBlank' | 'ShortAnswer';
  question_text: string;
  option_a?: string;
  option_b?: string;
  option_c?: string;
  option_d?: string;
  correct_option: string;
  explanation?: string;
  points: number;
}

export interface Exam {
  id: string;
  title: string;
  description?: string;
  duration_minutes: number;
  passing_score: number;
  status: ExamStatus;
  source_document_name?: string;
  created_at: string;
  question_count?: number;
}

export interface ExamAttempt {
  id: string;
  exam_id: string;
  user_id: string;
  started_at: string;
  completed_at?: string;
  score: number;
  passed: boolean;
  status: AttemptStatus;
}

export interface ExamResult {
  id: string;
  attempt_id: string;
  total_questions: number;
  correct_answers: number;
  score_percentage: number;
  passed: boolean;
  graded_at: string;
}

export interface Announcement {
  id: string;
  title: string;
  content: string;
  source_document_name?: string;
  is_published: boolean;
  created_at: string;
}

export interface NotificationItem {
  id: string;
  title: string;
  message: string;
  type: string;
  is_read: boolean;
  created_at: string;
}

export interface Citation {
  document_name: string;
  page_number: number;
  reference: string;
}

export interface ChatMessage {
  id: string;
  session_id: string;
  role: 'user' | 'assistant';
  message: string;
  citations?: Citation[];
  created_at: string;
}

export interface KnowledgeSearchResult {
  document_id: string;
  document_title: string;
  page_number: number;
  content: string;
  score: number;
}

export interface DashboardAnalytics {
  total_users: number;
  total_documents: number;
  total_study_plans?: number;
  total_exams: number;
  students_attempted: number;
  highest_score: number;
  lowest_score: number;
  average_score: number;
  performance_trends: { name: string; value: number }[];
  exam_trends: { exam_name: string; attempts: number; avg_score: number }[];
  document_trends: { name: string; size_mb: number }[];
  monthly_analytics: { month: string; attempts: number; avg_score: number }[];
}

export interface AuditLogItem {
  id: string;
  user_id?: string;
  action: string;
  entity_type: string;
  entity_id?: string;
  details?: string;
  timestamp: string;
}
