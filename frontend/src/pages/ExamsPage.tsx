import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { Topbar } from '../components/Topbar';
import { Modal } from '../components/Modal';
import { EmptyState } from '../components/EmptyState';
import { useAuth } from '../context/AuthContext';
import { Exam, ExamStatus, QuestionCreate } from '../types';
import { apiClient } from '../api/client';
import { GraduationCap, Plus, Play, Edit3, Trash2, CheckCircle2, Clock, Award, ShieldAlert, Loader2 } from 'lucide-react';

export const ExamsPage: React.FC = () => {
  const { isAdmin } = useAuth();
  const navigate = useNavigate();
  const [exams, setExams] = useState<Exam[]>([]);
  const [myAttempts, setMyAttempts] = useState<any[]>([]);
  const [isLoading, setIsLoading] = useState(true);

  // Modal State
  const [isCreateOpen, setIsCreateOpen] = useState(false);
  const [formData, setFormData] = useState({
    title: '',
    description: '',
    duration_minutes: 30,
    passing_score: 70,
    status: 'DRAFT' as ExamStatus
  });
  const [questions, setQuestions] = useState<QuestionCreate[]>([
    {
      question_type: 'MCQ',
      question_text: '',
      option_a: '',
      option_b: '',
      option_c: '',
      option_d: '',
      correct_option: '',
      explanation: '',
      points: 1.0
    }
  ]);

  const fetchExams = async () => {
    try {
      const res = await apiClient.get('/exams');
      setExams(res.data);
      if (!isAdmin) {
        const attRes = await apiClient.get('/exams/attempts/user/me');
        setMyAttempts(attRes.data);
      }
    } catch (e) {
      console.error(e);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchExams();

    const onAICommandExecuted = () => {
      fetchExams();
    };

    window.addEventListener('aiCommandExecuted', onAICommandExecuted);
    return () => {
      window.removeEventListener('aiCommandExecuted', onAICommandExecuted);
    };
  }, []);

  const handleCreateExam = async (e: React.FormEvent) => {
    e.preventDefault();

    const hasValidQuestion = questions.some((q) => q.question_text.trim().length > 0);
    if (!hasValidQuestion) {
      alert('Please add at least one question before creating the exam.');
      return;
    }

    try {
      await apiClient.post('/exams', {
        ...formData,
        questions: questions.filter((q) => q.question_text.trim().length > 0)
      });
      setIsCreateOpen(false);
      setFormData({ title: '', description: '', duration_minutes: 30, passing_score: 70, status: 'DRAFT' });
      setQuestions([
        {
          question_type: 'MCQ',
          question_text: '',
          option_a: '',
          option_b: '',
          option_c: '',
          option_d: '',
          correct_option: '',
          explanation: '',
          points: 1.0
        }
      ]);
      fetchExams();
    } catch (err: any) {
      alert(err.response?.data?.detail || 'Failed to create exam');
    }
  };

  const handleStatusChange = async (exam: Exam, newStatus: ExamStatus) => {
    try {
      await apiClient.put(`/exams/${exam.id}`, { status: newStatus });
      fetchExams();
    } catch (err: any) {
      alert(err.response?.data?.detail || 'Failed to update status');
    }
  };

  const handleDeleteExam = async (exam: Exam) => {
    if (window.confirm(`Are you sure you want to delete exam '${exam.title}'?`)) {
      try {
        await apiClient.delete(`/exams/${exam.id}`);
        fetchExams();
      } catch (err: any) {
        alert(err.response?.data?.detail || 'Failed to delete exam');
      }
    }
  };

  const getAttemptForExam = (examId: string) => {
    return myAttempts.find(a => a.exam_id === examId);
  };

  return (
    <div className="flex-1 min-h-screen bg-dark-900 pb-12">
      <Topbar title="Assessment & Exam Center" />

      <main className="p-6 max-w-7xl mx-auto space-y-6">
        <div className="flex items-center justify-between">
          <div>
            <h3 className="font-bold text-white text-base">Course Evaluations & Quizzes</h3>
            <p className="text-xs text-slate-400">
              {isAdmin ? 'Manage exam papers, publish tests, and review question banks' : 'Attempt published exams and view evaluation scores'}
            </p>
          </div>

          {isAdmin && (
            <button
              onClick={() => setIsCreateOpen(true)}
              className="px-4 py-2.5 rounded-xl bg-gradient-to-r from-indigo-600 to-cyan-600 hover:from-indigo-500 hover:to-cyan-500 text-white font-semibold text-xs flex items-center gap-2 shadow-lg shadow-indigo-600/20"
            >
              <Plus className="w-4 h-4" />
              <span>Create Manual Exam</span>
            </button>
          )}
        </div>

        <div className="glass-panel rounded-2xl border border-slate-800 p-5">
          {isLoading ? (
            <div className="p-12 text-center text-slate-400 text-xs flex flex-col items-center gap-2">
              <Loader2 className="w-6 h-6 animate-spin text-indigo-500" />
              <span>Loading exams...</span>
            </div>
          ) : exams.length === 0 ? (
            <EmptyState
              title="No Exams Available"
              description="There are currently no exams created or published in the system."
              icon={GraduationCap}
            />
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              {exams.map((ex) => {
                const userAttempt = getAttemptForExam(ex.id);
                const isCompleted = userAttempt?.status === 'COMPLETED';

                return (
                  <div key={ex.id} className="glass-card p-5 rounded-2xl border border-slate-800 flex flex-col justify-between hover:border-indigo-500/30 transition-all">
                    <div>
                      <div className="flex items-start justify-between gap-3 mb-3">
                        <div className="p-3 rounded-xl bg-emerald-600/20 text-emerald-400 border border-emerald-500/30">
                          <GraduationCap className="w-6 h-6" />
                        </div>

                        {isAdmin ? (
                          <select
                            value={ex.status}
                            onChange={(e) => handleStatusChange(ex, e.target.value as ExamStatus)}
                            className={`text-[10px] font-bold px-2 py-1 rounded uppercase bg-slate-900 border ${
                              ex.status === 'PUBLISHED' ? 'border-emerald-500/40 text-emerald-300' : 'border-amber-500/40 text-amber-300'
                            }`}
                          >
                            <option value="DRAFT">DRAFT</option>
                            <option value="PUBLISHED">PUBLISHED</option>
                            <option value="ARCHIVED">ARCHIVED</option>
                          </select>
                        ) : (
                          isCompleted && (
                            <span className="px-2.5 py-1 rounded text-[10px] font-bold uppercase bg-emerald-500/20 text-emerald-300 border border-emerald-500/30 flex items-center gap-1">
                              <CheckCircle2 className="w-3 h-3" /> Score: {userAttempt.score}%
                            </span>
                          )
                        )}
                      </div>

                      <h4 className="font-bold text-white text-base mb-1">{ex.title}</h4>
                      <p className="text-xs text-slate-400 line-clamp-2 mb-3">{ex.description || 'No description provided.'}</p>

                      <div className="flex items-center gap-4 text-[11px] text-slate-400 font-medium border-t border-slate-800/80 pt-3">
                        <span className="flex items-center gap-1">
                          <Clock className="w-3.5 h-3.5 text-indigo-400" /> {ex.duration_minutes} Mins
                        </span>
                        <span className="flex items-center gap-1">
                          <Award className="w-3.5 h-3.5 text-amber-400" /> Pass: {ex.passing_score}%
                        </span>
                        <span>{ex.question_count ?? 0} Qs</span>
                      </div>
                    </div>

                    <div className="mt-5 pt-3 border-t border-slate-800 flex items-center justify-between">
                      {!isAdmin ? (
                        isCompleted ? (
                          <span className="text-xs font-semibold text-emerald-400">Attempt Completed</span>
                        ) : (
                          <button
                            onClick={() => navigate(`/exams/${ex.id}/take`)}
                            className="w-full py-2.5 rounded-xl bg-gradient-to-r from-indigo-600 to-emerald-600 hover:from-indigo-500 hover:to-emerald-500 text-white font-bold text-xs flex items-center justify-center gap-2 shadow-md shadow-indigo-600/20"
                          >
                            <Play className="w-3.5 h-3.5 fill-current" /> Take Exam Now
                          </button>
                        )
                      ) : (
                        <div className="flex items-center justify-between w-full">
                          <span className="text-[10px] text-slate-500">Source: {ex.source_document_name || 'Manual'}</span>
                          <button
                            onClick={() => handleDeleteExam(ex)}
                            className="p-1.5 rounded-lg text-rose-400 hover:text-rose-300 hover:bg-rose-950/40"
                            title="Delete Exam"
                          >
                            <Trash2 className="w-3.5 h-3.5" />
                          </button>
                        </div>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      </main>

      {/* Create Manual Exam Modal */}
      <Modal isOpen={isCreateOpen} onClose={() => setIsCreateOpen(false)} title="Create New Exam Paper">
        <form onSubmit={handleCreateExam} className="space-y-4 text-xs">
          <div>
            <label className="block text-slate-300 font-semibold mb-1">Exam Title</label>
            <input
              type="text"
              required
              value={formData.title}
              onChange={(e) => setFormData({ ...formData, title: e.target.value })}
              placeholder="e.g. Midterm Evaluation: Fundamentals of AI"
              className="w-full px-3 py-2 rounded-xl bg-slate-900 border border-slate-700 text-white"
            />
          </div>
          <div>
            <label className="block text-slate-300 font-semibold mb-1">Description</label>
            <textarea
              value={formData.description}
              onChange={(e) => setFormData({ ...formData, description: e.target.value })}
              className="w-full px-3 py-2 rounded-xl bg-slate-900 border border-slate-700 text-white h-20"
            />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-slate-300 font-semibold mb-1">Duration (Minutes)</label>
              <input
                type="number"
                required
                value={formData.duration_minutes}
                onChange={(e) => setFormData({ ...formData, duration_minutes: parseInt(e.target.value) || 30 })}
                className="w-full px-3 py-2 rounded-xl bg-slate-900 border border-slate-700 text-white"
              />
            </div>
            <div>
              <label className="block text-slate-300 font-semibold mb-1">Passing Score (%)</label>
              <input
                type="number"
                required
                value={formData.passing_score}
                onChange={(e) => setFormData({ ...formData, passing_score: parseFloat(e.target.value) || 70 })}
                className="w-full px-3 py-2 rounded-xl bg-slate-900 border border-slate-700 text-white"
              />
            </div>
          </div>

          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <p className="text-slate-300 font-semibold text-sm">Exam Questions</p>
              <button
                type="button"
                onClick={() => setQuestions((prev) => [
                  ...prev,
                  {
                    question_type: 'MCQ',
                    question_text: '',
                    option_a: '',
                    option_b: '',
                    option_c: '',
                    option_d: '',
                    correct_option: '',
                    explanation: '',
                    points: 1.0
                  }
                ])}
                className="text-xs font-semibold text-cyan-400 hover:text-cyan-200"
              >
                + Add Question
              </button>
            </div>
            {questions.map((question, idx) => (
              <div key={idx} className="p-4 rounded-2xl bg-slate-950 border border-slate-800">
                <div className="flex items-center justify-between gap-3 mb-3">
                  <span className="text-[11px] font-semibold uppercase tracking-wider text-slate-400">Question {idx + 1}</span>
                  <button
                    type="button"
                    onClick={() => setQuestions((prev) => prev.filter((_, index) => index !== idx))}
                    className="text-[11px] font-semibold text-rose-400 hover:text-rose-200"
                  >
                    Remove
                  </button>
                </div>
                <div className="grid grid-cols-2 gap-3 mb-3">
                  <div>
                    <label className="block text-slate-300 font-semibold mb-1">Type</label>
                    <select
                      value={question.question_type}
                      onChange={(e) => {
                        const value = e.target.value as QuestionCreate['question_type'];
                        setQuestions((prev) => prev.map((q, index) => index === idx ? { ...q, question_type: value } : q));
                      }}
                      className="w-full px-3 py-2 rounded-xl bg-slate-900 border border-slate-700 text-white"
                    >
                      <option value="MCQ">MCQ</option>
                      <option value="TrueFalse">True/False</option>
                      <option value="FillBlank">Fill in the Blank</option>
                      <option value="ShortAnswer">Short Answer</option>
                    </select>
                  </div>
                  <div>
                    <label className="block text-slate-300 font-semibold mb-1">Points</label>
                    <input
                      type="number"
                      min={1}
                      step={0.5}
                      value={question.points}
                      onChange={(e) => setQuestions((prev) => prev.map((q, index) => index === idx ? { ...q, points: parseFloat(e.target.value) || 1.0 } : q))}
                      className="w-full px-3 py-2 rounded-xl bg-slate-900 border border-slate-700 text-white"
                    />
                  </div>
                </div>
                <div className="mb-3">
                  <label className="block text-slate-300 font-semibold mb-1">Question Text</label>
                  <textarea
                    value={question.question_text}
                    onChange={(e) => setQuestions((prev) => prev.map((q, index) => index === idx ? { ...q, question_text: e.target.value } : q))}
                    className="w-full px-3 py-2 rounded-xl bg-slate-900 border border-slate-700 text-white h-20"
                  />
                </div>
                {(question.question_type === 'MCQ' || question.question_type === 'FillBlank' || question.question_type === 'TrueFalse') && (
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-3 mb-3">
                    <div>
                      <label className="block text-slate-300 font-semibold mb-1">Option A</label>
                      <input
                        type="text"
                        value={question.option_a}
                        onChange={(e) => setQuestions((prev) => prev.map((q, index) => index === idx ? { ...q, option_a: e.target.value } : q))}
                        className="w-full px-3 py-2 rounded-xl bg-slate-900 border border-slate-700 text-white"
                      />
                    </div>
                    <div>
                      <label className="block text-slate-300 font-semibold mb-1">Option B</label>
                      <input
                        type="text"
                        value={question.option_b}
                        onChange={(e) => setQuestions((prev) => prev.map((q, index) => index === idx ? { ...q, option_b: e.target.value } : q))}
                        className="w-full px-3 py-2 rounded-xl bg-slate-900 border border-slate-700 text-white"
                      />
                    </div>
                    {question.question_type === 'MCQ' && (
                      <>
                        <div>
                          <label className="block text-slate-300 font-semibold mb-1">Option C</label>
                          <input
                            type="text"
                            value={question.option_c}
                            onChange={(e) => setQuestions((prev) => prev.map((q, index) => index === idx ? { ...q, option_c: e.target.value } : q))}
                            className="w-full px-3 py-2 rounded-xl bg-slate-900 border border-slate-700 text-white"
                          />
                        </div>
                        <div>
                          <label className="block text-slate-300 font-semibold mb-1">Option D</label>
                          <input
                            type="text"
                            value={question.option_d}
                            onChange={(e) => setQuestions((prev) => prev.map((q, index) => index === idx ? { ...q, option_d: e.target.value } : q))}
                            className="w-full px-3 py-2 rounded-xl bg-slate-900 border border-slate-700 text-white"
                          />
                        </div>
                      </>
                    )}
                  </div>
                )}
                <div className="grid grid-cols-1 md:grid-cols-2 gap-3 mb-3">
                  <div>
                    <label className="block text-slate-300 font-semibold mb-1">Correct Answer</label>
                    <input
                      type="text"
                      value={question.correct_option}
                      onChange={(e) => setQuestions((prev) => prev.map((q, index) => index === idx ? { ...q, correct_option: e.target.value } : q))}
                      className="w-full px-3 py-2 rounded-xl bg-slate-900 border border-slate-700 text-white"
                      placeholder={question.question_type === 'TrueFalse' ? 'True or False' : 'A / B / C / D / answer text'}
                    />
                  </div>
                  <div>
                    <label className="block text-slate-300 font-semibold mb-1">Explanation</label>
                    <input
                      type="text"
                      value={question.explanation}
                      onChange={(e) => setQuestions((prev) => prev.map((q, index) => index === idx ? { ...q, explanation: e.target.value } : q))}
                      className="w-full px-3 py-2 rounded-xl bg-slate-900 border border-slate-700 text-white"
                    />
                  </div>
                </div>
              </div>
            ))}
          </div>
          <button type="submit" className="w-full py-3 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-white font-bold">
            Save & Draft Exam
          </button>
        </form>
      </Modal>
    </div>
  );
};
