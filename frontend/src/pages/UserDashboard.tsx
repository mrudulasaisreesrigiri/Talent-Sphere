import React, { useState, useEffect } from 'react';
import { Topbar } from '../components/Topbar';
import { StatsCard } from '../components/StatsCard';
import { EmptyState } from '../components/EmptyState';
import { apiClient } from '../api/client';
import { GraduationCap, CheckCircle2, TrendingUp, Award, Clock, ArrowRight, Megaphone } from 'lucide-react';
import { Link } from 'react-router-dom';
import { ResponsiveContainer, AreaChart, Area, XAxis, YAxis, Tooltip } from 'recharts';

export const UserDashboard: React.FC = () => {
  const [data, setData] = useState<any>(null);
  const [announcements, setAnnouncements] = useState<any[]>([]);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    const fetchData = async () => {
      try {
        const res = await apiClient.get('/analytics/user/me');
        setData(res.data);
        const annRes = await apiClient.get('/announcements');
        setAnnouncements(annRes.data.slice(0, 3));
      } catch (e) {
        console.error(e);
      } finally {
        setIsLoading(false);
      }
    };
    fetchData();
  }, []);

  return (
    <div className="flex-1 min-h-screen bg-dark-900 pb-12">
      <Topbar title="Student Learning Hub" />

      <main className="p-6 max-w-7xl mx-auto space-y-6">
        {/* Stats Row */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          <StatsCard
            title="Upcoming Exams"
            value={data?.upcoming_exams ?? 0}
            subtitle="Published & available"
            icon={Clock}
            color="indigo"
          />
          <StatsCard
            title="Completed Exams"
            value={data?.completed_exams ?? 0}
            subtitle="Submitted evaluations"
            icon={CheckCircle2}
            color="emerald"
          />
          <StatsCard
            title="Average Score"
            value={`${data?.average_score ?? 0}%`}
            subtitle="Overall academic score"
            icon={TrendingUp}
            color="cyan"
          />
          <StatsCard
            title="Highest Score"
            value={`${data?.highest_score ?? 0}%`}
            subtitle="Personal record"
            icon={Award}
            color="amber"
          />
        </div>

        {/* Charts & Quick Actions */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Performance Trend */}
          <div className="lg:col-span-2 glass-panel p-5 rounded-2xl border border-slate-800">
            <h3 className="font-bold text-white text-sm mb-4">My Score Progression</h3>
            {data?.attempt_history && data.attempt_history.length > 0 ? (
              <div className="h-64">
                <ResponsiveContainer width="100%" height="100%">
                  <AreaChart data={data.attempt_history}>
                    <defs>
                      <linearGradient id="scoreGrad" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="5%" stopColor="#6366f1" stopOpacity={0.4}/>
                        <stop offset="95%" stopColor="#6366f1" stopOpacity={0}/>
                      </linearGradient>
                    </defs>
                    <XAxis dataKey="date" stroke="#64748b" fontSize={11} />
                    <YAxis domain={[0, 100]} stroke="#64748b" fontSize={11} />
                    <Tooltip contentStyle={{ backgroundColor: '#0f172a', borderColor: '#334155', borderRadius: '12px' }} />
                    <Area type="monotone" dataKey="score" stroke="#6366f1" strokeWidth={3} fillOpacity={1} fill="url(#scoreGrad)" />
                  </AreaChart>
                </ResponsiveContainer>
              </div>
            ) : (
              <EmptyState
                title="No Exam History Yet"
                description="Take published exams to track your score progression and academic metrics over time."
                actionButton={
                  <Link to="/exams" className="px-4 py-2 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-white font-semibold text-xs inline-flex items-center gap-2">
                    <GraduationCap className="w-4 h-4" /> Go to Exams
                  </Link>
                }
              />
            )}
          </div>

          {/* Announcements Card */}
          <div className="glass-panel p-5 rounded-2xl border border-slate-800 flex flex-col justify-between">
            <div>
              <div className="flex items-center justify-between mb-4">
                <h3 className="font-bold text-white text-sm flex items-center gap-2">
                  <Megaphone className="w-4 h-4 text-amber-400" /> Latest Announcements
                </h3>
                <Link to="/announcements" className="text-xs text-indigo-400 hover:underline">View All</Link>
              </div>

              {announcements.length === 0 ? (
                <p className="text-xs text-slate-500 py-6 text-center">No announcements published</p>
              ) : (
                <div className="space-y-3">
                  {announcements.map((a) => (
                    <div key={a.id} className="p-3 rounded-xl bg-slate-900/60 border border-slate-800">
                      <p className="text-xs font-semibold text-white truncate">{a.title}</p>
                      <p className="text-[11px] text-slate-400 mt-1 line-clamp-2">{a.content}</p>
                      <p className="text-[10px] text-slate-500 mt-1">{new Date(a.created_at).toLocaleDateString()}</p>
                    </div>
                  ))}
                </div>
              )}
            </div>

            <Link
              to="/ai-assistant"
              className="mt-4 py-3 rounded-xl bg-gradient-to-r from-indigo-600 to-cyan-600 text-white text-xs font-bold flex items-center justify-center gap-2 shadow-lg shadow-indigo-600/20"
            >
              <span>Launch AI Learning Assistant</span>
              <ArrowRight className="w-4 h-4" />
            </Link>
          </div>
        </div>
      </main>
    </div>
  );
};
