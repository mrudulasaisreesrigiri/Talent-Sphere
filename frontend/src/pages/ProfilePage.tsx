import React, { useState } from 'react';
import { Topbar } from '../components/Topbar';
import { useAuth } from '../context/AuthContext';
import { apiClient } from '../api/client';
import { User, KeyRound, ShieldCheck, CheckCircle2, Loader2 } from 'lucide-react';

export const ProfilePage: React.FC = () => {
  const { user } = useAuth();
  const [newPassword, setNewPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);

  const handlePasswordChange = async (e: React.FormEvent) => {
    e.preventDefault();
    if (newPassword !== confirmPassword) {
      alert('Passwords do not match');
      return;
    }
    setIsLoading(true);
    setMsg(null);
    try {
      await apiClient.post('/auth/change-password', { new_password: newPassword });
      setMsg('Password updated successfully!');
      setNewPassword('');
      setConfirmPassword('');
    } catch (err: any) {
      alert(err.response?.data?.detail || 'Failed to update password');
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="flex-1 min-h-screen bg-dark-900 pb-12">
      <Topbar title="User Profile & Security" />

      <main className="p-6 max-w-3xl mx-auto space-y-6">
        {/* User Card */}
        <div className="glass-panel p-6 rounded-3xl border border-slate-800 flex items-center gap-4">
          <div className="w-16 h-16 rounded-2xl bg-gradient-to-tr from-indigo-500 to-cyan-500 flex items-center justify-center text-white font-extrabold text-2xl shadow-xl">
            {user?.full_name?.charAt(0) || 'U'}
          </div>
          <div>
            <h3 className="font-bold text-white text-lg">{user?.full_name}</h3>
            <p className="text-xs text-slate-400">{user?.email}</p>
            <span className="inline-block mt-2 px-2.5 py-0.5 rounded text-[10px] font-bold uppercase bg-indigo-500/20 text-indigo-300 border border-indigo-500/30">
              Role: {user?.role}
            </span>
          </div>
        </div>

        {/* Change Password */}
        <div className="glass-panel p-6 rounded-3xl border border-slate-800 space-y-4">
          <div className="flex items-center gap-2 border-b border-slate-800 pb-3">
            <KeyRound className="w-5 h-5 text-indigo-400" />
            <h4 className="font-bold text-white text-sm">Security & Password Renewal</h4>
          </div>

          {msg && (
            <div className="p-3 rounded-xl bg-emerald-950/40 border border-emerald-500/30 text-emerald-300 text-xs flex items-center gap-2">
              <CheckCircle2 className="w-4 h-4 text-emerald-400" />
              <span>{msg}</span>
            </div>
          )}

          <form onSubmit={handlePasswordChange} className="space-y-4 text-xs">
            <div>
              <label className="block text-slate-300 font-semibold mb-1">New Password</label>
              <input
                type="password"
                required
                value={newPassword}
                onChange={(e) => setNewPassword(e.target.value)}
                className="w-full px-4 py-2.5 rounded-xl bg-slate-900 border border-slate-700 text-white"
              />
            </div>
            <div>
              <label className="block text-slate-300 font-semibold mb-1">Confirm New Password</label>
              <input
                type="password"
                required
                value={confirmPassword}
                onChange={(e) => setConfirmPassword(e.target.value)}
                className="w-full px-4 py-2.5 rounded-xl bg-slate-900 border border-slate-700 text-white"
              />
            </div>
            <button
              type="submit"
              disabled={isLoading}
              className="py-3 px-6 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-white font-bold flex items-center justify-center gap-2"
            >
              {isLoading ? <Loader2 className="w-4 h-4 animate-spin" /> : 'Update Password'}
            </button>
          </form>
        </div>
      </main>
    </div>
  );
};
