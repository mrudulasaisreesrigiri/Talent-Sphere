import React, { useState, useEffect } from 'react';
import { useAuth } from '../context/AuthContext';
import { NotificationDropdown } from './NotificationDropdown';
import { VoiceAssistantModal } from './VoiceAssistantModal';
import { AICommandModal } from './AICommandModal';
import { Mic, Terminal, User as UserIcon, Sun, Moon } from 'lucide-react';

interface TopbarProps {
  title: string;
}

export const Topbar: React.FC<TopbarProps> = ({ title }) => {
  const { user, isAdmin } = useAuth();
  const [isVoiceOpen, setIsVoiceOpen] = useState(false);
  const [isAICmdOpen, setIsAICmdOpen] = useState(false);
  const [isLight, setIsLight] = useState<boolean>(() => {
    return document.documentElement.classList.contains('light') || localStorage.getItem('app-theme') === 'light';
  });

  useEffect(() => {
    const root = document.documentElement;
    if (isLight) {
      root.classList.remove('dark');
      root.classList.add('light');
      root.setAttribute('data-theme', 'light');
    } else {
      root.classList.remove('light');
      root.classList.add('dark');
      root.setAttribute('data-theme', 'dark');
    }
  }, [isLight]);

  const toggleTheme = () => {
    const nextIsLight = !isLight;
    setIsLight(nextIsLight);
    const nextTheme = nextIsLight ? 'light' : 'dark';
    localStorage.setItem('app-theme', nextTheme);
  };

  return (
    <header className="glass-panel sticky top-0 z-20 px-6 py-4 border-b border-slate-800 flex items-center justify-between">
      <div>
        <h2 className="text-xl font-bold text-white tracking-tight">{title}</h2>
        <p className="text-xs text-slate-400">Talent Management Platform for Employee Performance and Career Growth</p>
      </div>

      <div className="flex items-center gap-3">
        {/* Admin AI Command Center Button */}
        {isAdmin && (
          <button
            onClick={() => setIsAICmdOpen(true)}
            className="flex items-center gap-2 px-3.5 py-2 rounded-xl bg-cyan-600/20 hover:bg-cyan-600/30 text-cyan-300 border border-cyan-500/30 text-xs font-semibold transition-all shadow-sm"
            title="Execute AI Directives"
          >
            <Terminal className="w-4 h-4 text-cyan-400" />
            <span className="hidden sm:inline">AI Commands</span>
          </button>
        )}

        {/* Voice RAG Assistant Button */}
        <button
          onClick={() => setIsVoiceOpen(true)}
          className="flex items-center gap-2 px-3.5 py-2 rounded-xl bg-indigo-600/20 hover:bg-indigo-600/30 text-indigo-300 border border-indigo-500/30 text-xs font-semibold transition-all shadow-sm"
          title="Open Voice Assistant"
        >
          <Mic className="w-4 h-4 text-indigo-400 animate-pulse" />
          <span className="hidden sm:inline">Voice Assistant</span>
        </button>

        {/* Notifications */}
        <NotificationDropdown />

        {/* Theme Toggle Button */}
        <button
          onClick={toggleTheme}
          className="p-2.5 rounded-xl bg-slate-800/80 hover:bg-slate-700/80 text-slate-300 hover:text-white transition-all border border-slate-700/60 flex items-center justify-center cursor-pointer shadow-sm"
          title={isLight ? 'Switch to Dark Mode' : 'Switch to Light Mode'}
          aria-label={isLight ? 'Switch to Dark Mode' : 'Switch to Light Mode'}
        >
          {isLight ? <Moon className="w-4 h-4 text-indigo-600" /> : <Sun className="w-4 h-4 text-amber-400" />}
        </button>

        {/* User Avatar */}
        <div className="flex items-center gap-3 pl-3 border-l border-slate-800">
          <div className="w-9 h-9 rounded-xl bg-gradient-to-tr from-indigo-500 to-purple-600 flex items-center justify-center font-bold text-white shadow-md">
            {user?.full_name?.charAt(0) || <UserIcon className="w-4 h-4" />}
          </div>
          <div className="hidden md:block">
            <p className="text-xs font-semibold text-white leading-tight">{user?.full_name}</p>
            <p className="text-[10px] font-medium text-slate-400 capitalize">{user?.role?.toLowerCase()}</p>
          </div>
        </div>
      </div>

      <VoiceAssistantModal isOpen={isVoiceOpen} onClose={() => setIsVoiceOpen(false)} />
      <AICommandModal isOpen={isAICmdOpen} onClose={() => setIsAICmdOpen(false)} />
    </header>
  );
};
