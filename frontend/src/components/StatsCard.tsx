import React from 'react';
import { LucideIcon } from 'lucide-react';

interface StatsCardProps {
  title: string;
  value: string | number;
  subtitle?: string;
  icon: LucideIcon;
  color?: 'indigo' | 'cyan' | 'emerald' | 'amber' | 'rose';
}

export const StatsCard: React.FC<StatsCardProps> = ({
  title,
  value,
  subtitle,
  icon: Icon,
  color = 'indigo'
}) => {
  const colorMap = {
    indigo: 'from-indigo-500/20 to-indigo-600/10 text-indigo-400 border-indigo-500/30',
    cyan: 'from-cyan-500/20 to-cyan-600/10 text-cyan-400 border-cyan-500/30',
    emerald: 'from-emerald-500/20 to-emerald-600/10 text-emerald-400 border-emerald-500/30',
    amber: 'from-amber-500/20 to-amber-600/10 text-amber-400 border-amber-500/30',
    rose: 'from-rose-500/20 to-rose-600/10 text-rose-400 border-rose-500/30',
  };

  return (
    <div className="glass-card rounded-2xl p-5 border border-slate-800 flex items-center justify-between transition-all duration-300 hover:scale-[1.02]">
      <div>
        <p className="text-xs font-semibold uppercase tracking-wider text-slate-400 mb-1">{title}</p>
        <h3 className="text-2xl font-extrabold text-white tracking-tight">{value}</h3>
        {subtitle && <p className="text-[11px] text-slate-400 mt-1">{subtitle}</p>}
      </div>
      <div className={`p-3.5 rounded-2xl bg-gradient-to-br ${colorMap[color]} border shadow-lg`}>
        <Icon className="w-6 h-6" />
      </div>
    </div>
  );
};
