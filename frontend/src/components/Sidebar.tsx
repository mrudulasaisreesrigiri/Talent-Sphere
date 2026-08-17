import React from 'react';
import { NavLink } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import {
  LayoutDashboard,
  Bot,
  GraduationCap,
  Users,
  Megaphone,
  Search,
  FileText,
  Settings,
  LogOut,
  ShieldCheck,
  Sparkles,
  BookOpen
} from 'lucide-react';

export const Sidebar: React.FC = () => {
  const { user, isAdmin, logout } = useAuth();

  const adminLinks = [
    { name: 'Home', path: '/admin-dashboard', icon: LayoutDashboard },
    { name: 'Study Plans', path: '/study-plans', icon: BookOpen },
    { name: 'Chatbot', path: '/ai-assistant', icon: Bot },
    { name: 'Exams', path: '/exams', icon: GraduationCap },
    { name: 'User Management', path: '/user-management', icon: Users },
    { name: 'Announcements', path: '/announcements', icon: Megaphone },
    { name: 'Knowledge Search', path: '/knowledge-search', icon: Search },
    { name: 'Audit Logs & Settings', path: '/audit-logs', icon: Settings },
  ];

  const studentLinks = [
    { name: 'Home', path: '/user-dashboard', icon: LayoutDashboard },
    { name: 'Study Plans', path: '/study-plans', icon: BookOpen },
    { name: 'AI Assistant', path: '/ai-assistant', icon: Bot },
    { name: 'Exams', path: '/exams', icon: GraduationCap },
    { name: 'Announcements', path: '/announcements', icon: Megaphone },
    { name: 'Profile', path: '/profile', icon: Settings },
  ];

  const links = isAdmin ? adminLinks : studentLinks;

  return (
    <aside className="w-64 glass-panel min-h-screen border-r border-slate-800 flex flex-col justify-between p-4 sticky top-0 z-30">
      <div>
        {/* Brand Header */}
        <div className="flex items-center gap-3 px-2 py-4 mb-6 border-b border-slate-800/60">
          <div className="w-10 h-10 rounded-xl bg-gradient-to-tr from-indigo-600 via-indigo-500 to-cyan-400 flex items-center justify-center shadow-lg shadow-indigo-500/20 shrink-0 font-black text-xs text-white">
            TMP
          </div>
          <div className="overflow-hidden">
            <h1 className="font-bold text-xs text-white leading-tight">Talent Management Platform</h1>
            <span className="text-[9px] font-semibold tracking-wide text-cyan-400 uppercase block">for Employee Performance & Growth</span>
          </div>
        </div>

        {/* User Role Badge */}
        <div className="mx-2 mb-6 px-3 py-2 rounded-lg bg-slate-800/50 border border-slate-700/50 flex items-center justify-between">
          <div className="flex items-center gap-2 overflow-hidden">
            <div className="w-8 h-8 rounded-full bg-indigo-500/20 text-indigo-400 flex items-center justify-center font-bold text-sm">
              {user?.full_name?.charAt(0) || 'U'}
            </div>
            <div className="truncate">
              <p className="text-xs font-semibold text-white truncate">{user?.full_name}</p>
              <p className="text-[10px] text-slate-400 truncate">{user?.email}</p>
            </div>
          </div>
          <span className={`text-[10px] font-bold px-2 py-0.5 rounded uppercase ${isAdmin ? 'bg-amber-500/20 text-amber-300 border border-amber-500/30' : 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/30'}`}>
            {user?.role}
          </span>
        </div>

        {/* Navigation Links */}
        <nav className="space-y-1">
          {links.map((link) => {
            const Icon = link.icon;
            return (
              <NavLink
                key={link.path}
                to={link.path}
                className={({ isActive }) =>
                  `flex items-center gap-3 px-3.5 py-2.5 rounded-xl font-medium text-sm transition-all duration-200 ${
                    isActive
                      ? 'bg-gradient-to-r from-indigo-600 to-indigo-700 text-white shadow-md shadow-indigo-600/30 font-semibold'
                      : 'text-slate-400 hover:text-white hover:bg-slate-800/60'
                  }`
                }
              >
                <Icon className="w-4 h-4" />
                <span>{link.name}</span>
              </NavLink>
            );
          })}
        </nav>
      </div>

      {/* Sign Out Button */}
      <div className="pt-4 border-t border-slate-800/60">
        <button
          onClick={logout}
          className="w-full flex items-center gap-3 px-3.5 py-2.5 rounded-xl font-medium text-sm text-rose-400 hover:bg-rose-500/10 hover:text-rose-300 transition-all duration-200"
        >
          <LogOut className="w-4 h-4" />
          <span>Sign Out</span>
        </button>
      </div>
    </aside>
  );
};
