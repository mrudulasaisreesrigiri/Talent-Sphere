import React, { useState, useEffect, useRef } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { Exam, Question, ExamAttempt, ExamResult } from '../types';
import { apiClient } from '../api/client';
import { Clock, Maximize2, Minimize2, CheckCircle2, XCircle, ArrowLeft, ArrowRight, Send, AlertTriangle, ShieldCheck, Loader2 } from 'lucide-react';

export const TakeExamPage: React.FC = () => {
  const { examId } = useParams<{ examId: string }>();
  const navigate = useNavigate();

  const [exam, setExam] = useState<Exam | null>(null);
  const [questions, setQuestions] = useState<Question[]>([]);
  const [attempt, setAttempt] = useState<ExamAttempt | null>(null);
  const [currentIdx, setCurrentIdx] = useState(0);
  const [answers, setAnswers] = useState<Record<string, string>>({});
  const [timeLeft, setTimeLeft] = useState<number>(0);
  const [hasStartedExam, setHasStartedExam] = useState(false);
  const [isFullscreen, setIsFullscreen] = useState(false);
  const [isPausedForFullscreen, setIsPausedForFullscreen] = useState(false);
  const [fullscreenError, setFullscreenError] = useState<string | null>(null);
  const [result, setResult] = useState<ExamResult | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const timerRef = useRef<any>(null);

  useEffect(() => {
    const initAttempt = async () => {
      try {
        const examRes = await apiClient.get(`/exams/${examId}`);
        setExam(examRes.data);

        const qRes = await apiClient.get(`/exams/${examId}/questions`);
        setQuestions(qRes.data);

        // Start or resume attempt session
        const attRes = await apiClient.post(`/exams/${examId}/start`);
        setAttempt(attRes.data);

        if (attRes.data.status === 'COMPLETED') {
          // Attempt already completed
          setError('You have already completed this exam attempt.');
          setLoading(false);
          return;
        }

        // Calculate timer remaining seconds based on duration
        const totalSecs = examRes.data.duration_minutes * 60;
        const elapsedSecs = Math.floor((new Date().getTime() - new Date(attRes.data.started_at).getTime()) / 1000);
        const remainingSecs = Math.max(0, totalSecs - elapsedSecs);
        setTimeLeft(remainingSecs > 0 ? remainingSecs : totalSecs);
      }
      catch (err: any) {
        setError(err.response?.data?.detail || 'Failed to initialize exam session');
      }
      finally {
        setLoading(false);
      }
    };

    if (examId) {
      initAttempt();
    }
  }, [examId]);

  // Track Fullscreen state transitions safely
  useEffect(() => {
    const handleFullscreenChange = () => {
      const inFullscreen = !!document.fullscreenElement;
      setIsFullscreen(inFullscreen);

      // If exam is active and user exits fullscreen before submission
      if (hasStartedExam && !result && !isSubmitting) {
        if (!inFullscreen) {
          setIsPausedForFullscreen(true);
        } else {
          setIsPausedForFullscreen(false);
        }
      }
    };

    document.addEventListener('fullscreenchange', handleFullscreenChange);
    document.addEventListener('webkitfullscreenchange', handleFullscreenChange);
    document.addEventListener('mozfullscreenchange', handleFullscreenChange);
    document.addEventListener('MSFullscreenChange', handleFullscreenChange);

    return () => {
      document.removeEventListener('fullscreenchange', handleFullscreenChange);
      document.removeEventListener('webkitfullscreenchange', handleFullscreenChange);
      document.removeEventListener('mozfullscreenchange', handleFullscreenChange);
      document.removeEventListener('MSFullscreenChange', handleFullscreenChange);
    };
  }, [hasStartedExam, result, isSubmitting]);

  // Countdown timer effect - ONLY runs after fullscreen is successfully entered
  useEffect(() => {
    if (hasStartedExam && !isPausedForFullscreen && timeLeft > 0 && !result) {
      timerRef.current = setInterval(() => {
        setTimeLeft((prev) => {
          if (prev <= 1) {
            clearInterval(timerRef.current);
            handleSubmitExam(); // Auto submit when time expires
            return 0;
          }
          return prev - 1;
        });
      }, 1000);
    }

    return () => {
      if (timerRef.current) clearInterval(timerRef.current);
    };
  }, [hasStartedExam, isPausedForFullscreen, timeLeft, result]);

  /**
   * Enters browser Fullscreen mode and ONLY starts the exam once active
   */
  const handleEnterFullscreenAndStart = async () => {
    setFullscreenError(null);
    try {
      if (!document.fullscreenElement) {
        if (document.documentElement.requestFullscreen) {
          await document.documentElement.requestFullscreen();
        } else if ((document.documentElement as any).webkitRequestFullscreen) {
          await (document.documentElement as any).webkitRequestFullscreen();
        } else if ((document.documentElement as any).msRequestFullscreen) {
          await (document.documentElement as any).msRequestFullscreen();
        }
      }

      if (document.fullscreenElement || (document as any).webkitFullscreenElement) {
        setIsFullscreen(true);
        setIsPausedForFullscreen(false);
        setHasStartedExam(true);
      } else {
        setFullscreenError('Fullscreen mode could not be activated. Please enable browser fullscreen permissions and try again.');
      }
    } catch (err: any) {
      console.warn('Fullscreen request failed or refused:', err);
      setFullscreenError('Fullscreen permission was refused by the browser. Please allow fullscreen mode to begin the exam.');
    }
  };

  const handleReturnToFullscreen = async () => {
    setFullscreenError(null);
    try {
      if (!document.fullscreenElement) {
        await document.documentElement.requestFullscreen();
      }
      setIsFullscreen(true);
      setIsPausedForFullscreen(false);
    } catch (err) {
      console.warn('Return to fullscreen failed:', err);
    }
  };

  const toggleFullscreen = () => {
    if (!document.fullscreenElement) {
      document.documentElement.requestFullscreen().catch(() => {});
      setIsFullscreen(true);
    } else {
      if (document.exitFullscreen) {
        document.exitFullscreen().catch(() => {});
        setIsFullscreen(false);
      }
    }
  };

  const handleSelectOption = (qId: string, optionKey: string) => {
    setAnswers(prev => ({
      ...prev,
      [qId]: optionKey
    }));
  };

  const handleSubmitExam = async () => {
    if (!attempt || isSubmitting) return;

    setIsSubmitting(true);
    try {
      const payload = {
        answers: Object.entries(answers).map(([qId, val]) => ({
          question_id: qId,
          selected_option: val
        }))
      };

      const res = await apiClient.post(`/exams/attempts/${attempt.id}/submit`, payload);

      // Exit fullscreen mode and return to normal screen
      if (document.fullscreenElement) {
        try {
          await document.exitFullscreen();
        } catch (e) {}
      }
      setIsFullscreen(false);
      setIsPausedForFullscreen(false);

      // ONLY AFTER exiting fullscreen, show the existing exam Results screen
      setResult(res.data);
    } catch (err: any) {
      alert(err.response?.data?.detail || 'Failed to submit exam');
    } finally {
      setIsSubmitting(false);
    }
  };

  const formatTime = (secs: number) => {
    const m = Math.floor(secs / 60);
    const s = secs % 60;
    return `${m.toString().padStart(2, '0')}:${s.toString().padStart(2, '0')}`;
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-dark-900 flex items-center justify-center p-6 text-center">
        <div className="glass-panel p-8 rounded-3xl max-w-md border border-slate-800/70">
          <Loader2 className="w-10 h-10 mx-auto mb-4 animate-spin text-indigo-400" />
          <p className="text-slate-300 text-sm">Loading exam questions...</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="min-h-screen bg-dark-900 flex items-center justify-center p-6 text-center">
        <div className="glass-panel p-8 rounded-3xl max-w-md border border-rose-500/30">
          <AlertTriangle className="w-12 h-12 text-rose-400 mx-auto mb-3" />
          <h2 className="text-lg font-bold text-white mb-2">Access Error</h2>
          <p className="text-xs text-slate-400 mb-6">{error}</p>
          <button
            onClick={() => navigate('/exams')}
            className="px-6 py-2.5 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-white font-bold text-xs"
          >
            Back to Exams
          </button>
        </div>
      </div>
    );
  }

  if (!loading && questions.length === 0) {
    return (
      <div className="min-h-screen bg-dark-900 flex items-center justify-center p-6 text-center">
        <div className="glass-panel p-8 rounded-3xl max-w-md border border-amber-500/30">
          <AlertTriangle className="w-12 h-12 text-amber-400 mx-auto mb-3" />
          <h2 className="text-lg font-bold text-white mb-2">No Questions Available</h2>
          <p className="text-xs text-slate-400 mb-6">
            This exam currently has no questions assigned. Please contact the administrator to add questions or create a new exam with questions.
          </p>
          <button
            onClick={() => navigate('/exams')}
            className="px-6 py-2.5 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-white font-bold text-xs"
          >
            Back to Exams
          </button>
        </div>
      </div>
    );
  }

  // Existing Results Screen
  if (result) {
    return (
      <div className="min-h-screen bg-dark-900 flex items-center justify-center p-6">
        <div className="glass-panel p-8 rounded-3xl max-w-lg w-full border border-indigo-500/30 text-center space-y-6 shadow-2xl">
          <div className={`w-20 h-20 rounded-full mx-auto flex items-center justify-center border-4 ${
            result.passed ? 'bg-emerald-500/20 border-emerald-500 text-emerald-400' : 'bg-rose-500/20 border-rose-500 text-rose-400'
          }`}>
            {result.passed ? <CheckCircle2 className="w-10 h-10" /> : <XCircle className="w-10 h-10" />}
          </div>

          <div>
            <h2 className="text-2xl font-extrabold text-white">
              {result.passed ? 'Exam Passed Successfully!' : 'Evaluation Completed'}
            </h2>
            <p className="text-xs text-slate-400 mt-1">{exam?.title}</p>
          </div>

          <div className="grid grid-cols-2 gap-4 py-4 bg-slate-900/60 rounded-2xl border border-slate-800">
            <div>
              <p className="text-[11px] font-semibold text-slate-400 uppercase">Final Score</p>
              <p className={`text-3xl font-extrabold mt-1 ${result.passed ? 'text-emerald-400' : 'text-rose-400'}`}>
                {result.score_percentage}%
              </p>
            </div>
            <div>
              <p className="text-[11px] font-semibold text-slate-400 uppercase">Correct Answers</p>
              <p className="text-3xl font-extrabold text-white mt-1">
                {result.correct_answers} / {result.total_questions}
              </p>
            </div>
          </div>

          <button
            onClick={() => navigate('/exams')}
            className="w-full py-3 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-white font-bold text-xs shadow-lg shadow-indigo-600/30 cursor-pointer"
          >
            Return to Assessment Center
          </button>
        </div>
      </div>
    );
  }

  const currentQ = questions[currentIdx];

  return (
    <div className="min-h-screen bg-[#090d16] text-slate-100 flex flex-col justify-between relative">
      {/* 1. Fullscreen Required Modal Before Exam Starts */}
      {!hasStartedExam && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-md animate-fade-in">
          <div className="glass-panel w-full max-w-md rounded-3xl border border-indigo-500/30 p-8 shadow-2xl text-center space-y-6">
            <div className="w-16 h-16 rounded-2xl bg-indigo-600/20 text-indigo-400 border border-indigo-500/30 mx-auto flex items-center justify-center shadow-lg">
              <Maximize2 className="w-8 h-8 animate-pulse" />
            </div>

            <div>
              <span className="text-[11px] font-bold text-amber-400 uppercase tracking-wider block mb-1">
                Exam not started
              </span>
              <h2 className="text-xl font-extrabold text-white">
                Fullscreen Mode Required
              </h2>
              <p className="text-xs text-slate-300 mt-2 leading-relaxed">
                Please enter fullscreen mode to start the exam.
              </p>
            </div>

            <div className="p-3.5 rounded-2xl bg-slate-900/80 border border-slate-800 text-[11px] text-slate-400 space-y-1.5 text-left">
              <p className="font-semibold text-indigo-300 flex items-center gap-1.5">
                <ShieldCheck className="w-3.5 h-3.5 text-indigo-400" /> Assessment Rules:
              </p>
              <p>• The exam timer will begin immediately upon entering fullscreen.</p>
              <p>• The assessment must remain in fullscreen mode until submission.</p>
            </div>

            {fullscreenError && (
              <div className="p-3 rounded-xl bg-rose-950/60 border border-rose-500/40 text-rose-300 text-xs flex items-center gap-2 text-left">
                <AlertTriangle className="w-4 h-4 shrink-0 text-rose-400" />
                <span>{fullscreenError}</span>
              </div>
            )}

            <button
              onClick={handleEnterFullscreenAndStart}
              className="w-full py-3.5 rounded-xl bg-gradient-to-r from-indigo-600 to-emerald-600 hover:from-indigo-500 hover:to-emerald-500 text-white font-bold text-xs flex items-center justify-center gap-2 shadow-lg shadow-indigo-600/30 transition-all cursor-pointer hover:scale-[1.02]"
            >
              <Maximize2 className="w-4 h-4" /> Go to Fullscreen Mode
            </button>
          </div>
        </div>
      )}

      {/* 2. Fullscreen Exit Warning Modal (If user exits fullscreen during exam) */}
      {hasStartedExam && isPausedForFullscreen && !result && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/85 backdrop-blur-md animate-fade-in">
          <div className="glass-panel w-full max-w-md rounded-3xl border border-amber-500/40 p-8 shadow-2xl text-center space-y-6">
            <div className="w-16 h-16 rounded-2xl bg-amber-500/20 text-amber-400 border border-amber-500/30 mx-auto flex items-center justify-center shadow-lg">
              <AlertTriangle className="w-8 h-8 animate-bounce" />
            </div>

            <div>
              <span className="text-[11px] font-bold text-amber-400 uppercase tracking-wider block mb-1">
                Exam Paused
              </span>
              <h2 className="text-xl font-extrabold text-white">
                Fullscreen Exited
              </h2>
              <p className="text-xs text-slate-300 mt-2 leading-relaxed">
                This exam requires active fullscreen mode. Please return to fullscreen mode to continue your assessment.
              </p>
            </div>

            <button
              onClick={handleReturnToFullscreen}
              className="w-full py-3.5 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-white font-bold text-xs flex items-center justify-center gap-2 shadow-lg shadow-indigo-600/30 transition-all cursor-pointer"
            >
              <Maximize2 className="w-4 h-4" /> Return to Fullscreen
            </button>
          </div>
        </div>
      )}

      {/* Header Bar */}
      <header className="glass-panel px-6 py-4 border-b border-slate-800 flex items-center justify-between sticky top-0 z-30">
        <div>
          <h2 className="font-bold text-white text-base">{exam?.title}</h2>
          <p className="text-xs text-slate-400">Passing Threshold: {exam?.passing_score}%</p>
        </div>

        <div className="flex items-center gap-4">
          <div className={`flex items-center gap-2 px-4 py-2 rounded-xl font-mono text-sm font-bold border ${
            timeLeft < 300 ? 'bg-rose-950/60 border-rose-500/40 text-rose-400 animate-pulse' : 'bg-slate-900 border-slate-800 text-indigo-400'
          }`}>
            <Clock className="w-4 h-4" />
            <span>{formatTime(timeLeft)}</span>
          </div>

          <button
            onClick={toggleFullscreen}
            className="p-2 rounded-xl bg-slate-900 border border-slate-800 text-slate-300 hover:text-white cursor-pointer"
            title="Toggle Fullscreen"
          >
            {isFullscreen ? <Minimize2 className="w-4 h-4" /> : <Maximize2 className="w-4 h-4" />}
          </button>
        </div>
      </header>

      {/* Question Workspace */}
      <main className="flex-1 max-w-4xl mx-auto w-full p-6 space-y-6">
        {/* Navigation Grid */}
        <div className="flex items-center gap-2 overflow-x-auto pb-2">
          {questions.map((q, idx) => (
            <button
              key={q.id}
              onClick={() => setCurrentIdx(idx)}
              className={`w-9 h-9 rounded-xl font-bold text-xs shrink-0 transition-all cursor-pointer ${
                currentIdx === idx
                  ? 'bg-indigo-600 text-white shadow-lg shadow-indigo-600/30'
                  : answers[q.id]
                  ? 'bg-emerald-600/30 text-emerald-300 border border-emerald-500/40'
                  : 'bg-slate-900 border border-slate-800 text-slate-400 hover:bg-slate-800'
              }`}
            >
              {idx + 1}
            </button>
          ))}
        </div>

        {currentQ && (
          <div className="glass-panel p-8 rounded-3xl border border-slate-800 space-y-6 shadow-xl">
            <div className="flex items-center justify-between border-b border-slate-800/80 pb-4">
              <span className="text-xs font-semibold text-indigo-400 uppercase tracking-wider">
                Question {currentIdx + 1} of {questions.length} • ({currentQ.points} Points)
              </span>
              <span className="text-xs font-medium text-slate-400">{currentQ.question_type}</span>
            </div>

            <h3 className="text-base sm:text-lg font-bold text-white leading-relaxed">
              {currentQ.question_text}
            </h3>

            {/* Options List */}
            <div className="space-y-3 pt-2">
              {currentQ.option_a && (
                <button
                  onClick={() => handleSelectOption(currentQ.id, 'A')}
                  className={`w-full p-4 rounded-2xl text-left text-xs font-medium transition-all flex items-center gap-3 cursor-pointer ${
                    answers[currentQ.id] === 'A'
                      ? 'bg-indigo-600/20 border-2 border-indigo-500 text-white shadow-lg'
                      : 'bg-slate-900/80 border border-slate-800 text-slate-300 hover:bg-slate-800'
                  }`}
                >
                  <span className="w-6 h-6 rounded-lg bg-slate-800 flex items-center justify-center font-bold text-indigo-400 shrink-0">A</span>
                  <span>{currentQ.option_a}</span>
                </button>
              )}

              {currentQ.option_b && (
                <button
                  onClick={() => handleSelectOption(currentQ.id, 'B')}
                  className={`w-full p-4 rounded-2xl text-left text-xs font-medium transition-all flex items-center gap-3 cursor-pointer ${
                    answers[currentQ.id] === 'B'
                      ? 'bg-indigo-600/20 border-2 border-indigo-500 text-white shadow-lg'
                      : 'bg-slate-900/80 border border-slate-800 text-slate-300 hover:bg-slate-800'
                  }`}
                >
                  <span className="w-6 h-6 rounded-lg bg-slate-800 flex items-center justify-center font-bold text-indigo-400 shrink-0">B</span>
                  <span>{currentQ.option_b}</span>
                </button>
              )}

              {currentQ.option_c && (
                <button
                  onClick={() => handleSelectOption(currentQ.id, 'C')}
                  className={`w-full p-4 rounded-2xl text-left text-xs font-medium transition-all flex items-center gap-3 cursor-pointer ${
                    answers[currentQ.id] === 'C'
                      ? 'bg-indigo-600/20 border-2 border-indigo-500 text-white shadow-lg'
                      : 'bg-slate-900/80 border border-slate-800 text-slate-300 hover:bg-slate-800'
                  }`}
                >
                  <span className="w-6 h-6 rounded-lg bg-slate-800 flex items-center justify-center font-bold text-indigo-400 shrink-0">C</span>
                  <span>{currentQ.option_c}</span>
                </button>
              )}

              {currentQ.option_d && (
                <button
                  onClick={() => handleSelectOption(currentQ.id, 'D')}
                  className={`w-full p-4 rounded-2xl text-left text-xs font-medium transition-all flex items-center gap-3 cursor-pointer ${
                    answers[currentQ.id] === 'D'
                      ? 'bg-indigo-600/20 border-2 border-indigo-500 text-white shadow-lg'
                      : 'bg-slate-900/80 border border-slate-800 text-slate-300 hover:bg-slate-800'
                  }`}
                >
                  <span className="w-6 h-6 rounded-lg bg-slate-800 flex items-center justify-center font-bold text-indigo-400 shrink-0">D</span>
                  <span>{currentQ.option_d}</span>
                </button>
              )}
            </div>
          </div>
        )}
      </main>

      {/* Footer Controls */}
      <footer className="glass-panel px-6 py-4 border-t border-slate-800 sticky bottom-0 z-30 flex items-center justify-between max-w-4xl mx-auto w-full">
        <button
          disabled={currentIdx === 0}
          onClick={() => setCurrentIdx(prev => Math.max(0, prev - 1))}
          className="px-4 py-2 rounded-xl bg-slate-900 border border-slate-800 text-slate-300 hover:text-white text-xs font-semibold flex items-center gap-2 disabled:opacity-40 cursor-pointer"
        >
          <ArrowLeft className="w-4 h-4" /> Previous
        </button>

        {currentIdx < questions.length - 1 ? (
          <button
            onClick={() => setCurrentIdx(prev => Math.min(questions.length - 1, prev + 1))}
            className="px-4 py-2 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-semibold flex items-center gap-2 cursor-pointer"
          >
            Next <ArrowRight className="w-4 h-4" />
          </button>
        ) : (
          <button
            onClick={handleSubmitExam}
            disabled={isSubmitting}
            className="px-6 py-2.5 rounded-xl bg-gradient-to-r from-emerald-600 to-cyan-600 hover:from-emerald-500 hover:to-cyan-500 text-white text-xs font-bold flex items-center gap-2 shadow-lg shadow-emerald-600/30 cursor-pointer"
          >
            {isSubmitting ? <Loader2 className="w-4 h-4 animate-spin" /> : <><Send className="w-4 h-4" /> Submit Exam Paper</>}
          </button>
        )}
      </footer>
    </div>
  );
};
