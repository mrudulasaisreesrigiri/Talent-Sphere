import React, { useState, useEffect } from 'react';
import { Topbar } from '../components/Topbar';
import { StatsCard } from '../components/StatsCard';
import { EmptyState } from '../components/EmptyState';
import { DashboardAnalytics } from '../types';
import { apiClient } from '../api/client';
import { Users, BookOpen, GraduationCap, Award, TrendingUp, BarChart3, AlertCircle } from 'lucide-react';
import {
  ResponsiveContainer, BarChart, Bar, XAxis, YAxis, Tooltip, PieChart, Pie, Cell, AreaChart, Area
} from 'recharts';

export const AdminDashboard: React.FC = () => {
  const [data, setData] = useState<DashboardAnalytics | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    const fetchAnalytics = async () => {
      try {
        const res = await apiClient.get('/analytics/admin');
        setData(res.data);
      } catch (e) {
        console.error(e);
      } finally {
        setIsLoading(false);
      }
    };
    fetchAnalytics();
  }, []);

  const COLORS = ['#10b981', '#f43f5e', '#6366f1', '#06b6d4'];

  return (
    <div className="flex-1 min-h-screen bg-dark-900 pb-12">
      <Topbar title="Admin Analytics Overview" />

      <main className="p-6 max-w-7xl mx-auto space-y-6">
        {/* Metric Cards Row */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          <StatsCard
            title="Total Users"
            value={data?.total_users ?? 0}
            subtitle="Active learners & admins"
            icon={Users}
            color="indigo"
          />
          <StatsCard
            title="Study Plans"
            value={data?.total_study_plans ?? data?.total_documents ?? 0}
            subtitle="Curriculum tracks"
            icon={BookOpen}
            color="cyan"
          />
          <StatsCard
            title="Total Exams"
            value={data?.total_exams ?? 0}
            subtitle="Created & published"
            icon={GraduationCap}
            color="emerald"
          />
          <StatsCard
            title="Students Attempted"
            value={data?.students_attempted ?? 0}
            subtitle="Learners submitted exams"
            icon={Award}
            color="amber"
          />
        </div>

        {/* Score Statistics */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div className="glass-card p-5 rounded-2xl border border-slate-800 flex items-center justify-between">
            <div>
              <p className="text-xs font-semibold uppercase text-slate-400">Average Score</p>
              <h4 className="text-3xl font-extrabold text-indigo-400 mt-1">{data?.average_score ?? 0}%</h4>
            </div>
            <TrendingUp className="w-8 h-8 text-indigo-400/50" />
          </div>

          <div className="glass-card p-5 rounded-2xl border border-slate-800 flex items-center justify-between">
            <div>
              <p className="text-xs font-semibold uppercase text-slate-400">Highest Score</p>
              <h4 className="text-3xl font-extrabold text-emerald-400 mt-1">{data?.highest_score ?? 0}%</h4>
            </div>
            <Award className="w-8 h-8 text-emerald-400/50" />
          </div>

          <div className="glass-card p-5 rounded-2xl border border-slate-800 flex items-center justify-between">
            <div>
              <p className="text-xs font-semibold uppercase text-slate-400">Lowest Score</p>
              <h4 className="text-3xl font-extrabold text-amber-400 mt-1">{data?.lowest_score ?? 0}%</h4>
            </div>
            <BarChart3 className="w-8 h-8 text-amber-400/50" />
          </div>
        </div>

        {/* Charts Section */}
        {data && data.students_attempted === 0 ? (
          <EmptyState
            title="No Analytics Data Available"
            description="The database currently contains no student exam attempts. Create study plans and publish exams to generate analytics."
            icon={AlertCircle}
          />
        ) : (
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {/* Exam Performance Distribution */}
            <div className="glass-panel p-5 rounded-2xl border border-slate-800">
              <h3 className="font-bold text-white text-sm mb-4">Exam Performance Breakdown</h3>
              <div className="h-64">
                <ResponsiveContainer width="100%" height="100%">
                  <PieChart>
                    <Pie
                      data={data?.performance_trends}
                      cx="50%"
                      cy="50%"
                      innerRadius={60}
                      outerRadius={90}
                      paddingAngle={5}
                      dataKey="value"
                    >
                      {data?.performance_trends.map((entry, index) => (
                        <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                      ))}
                    </Pie>
                    <Tooltip contentStyle={{ backgroundColor: '#0f172a', borderColor: '#334155', borderRadius: '12px' }} />
                  </PieChart>
                </ResponsiveContainer>
              </div>
            </div>

            {/* Exam Trends */}
            <div className="glass-panel p-5 rounded-2xl border border-slate-800">
              <h3 className="font-bold text-white text-sm mb-4">Exam Attempts & Average Score</h3>
              <div className="h-64">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={data?.exam_trends}>
                    <XAxis dataKey="exam_name" stroke="#64748b" fontSize={11} />
                    <YAxis stroke="#64748b" fontSize={11} />
                    <Tooltip contentStyle={{ backgroundColor: '#0f172a', borderColor: '#334155', borderRadius: '12px' }} />
                    <Bar dataKey="attempts" fill="#6366f1" radius={[6, 6, 0, 0]} name="Attempts" />
                    <Bar dataKey="avg_score" fill="#06b6d4" radius={[6, 6, 0, 0]} name="Avg Score (%)" />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </div>
          </div>
        )}
      </main>
    </div>
  );
};
