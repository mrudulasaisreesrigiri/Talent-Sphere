import React, { useState, useEffect } from 'react';
import { Topbar } from '../components/Topbar';
import { Modal } from '../components/Modal';
import { EmptyState } from '../components/EmptyState';
import { User, UserRole } from '../types';
import { apiClient } from '../api/client';
import { Users, UserPlus, Edit3, Trash2, KeyRound, ShieldAlert, CheckCircle, XCircle, Search, Loader2, Mail } from 'lucide-react';

export const UserManagementPage: React.FC = () => {
  const [users, setUsers] = useState<User[]>([]);
  const [search, setSearch] = useState('');
  const [isLoading, setIsLoading] = useState(true);

  // Modal States
  const [isCreateOpen, setIsCreateOpen] = useState(false);
  const [isEditOpen, setIsEditOpen] = useState(false);
  const [isResetOpen, setIsResetOpen] = useState(false);
  const [selectedUser, setSelectedUser] = useState<User | null>(null);

  // Newly created user credentials state for Send Mail flow
  const [createdUserCredential, setCreatedUserCredential] = useState<{
    id: string;
    email: string;
    full_name: string;
    role: string;
    password: string;
  } | null>(null);
  const [isSendingMail, setIsSendingMail] = useState(false);
  const [emailStatusMsg, setEmailStatusMsg] = useState<{ type: 'success' | 'error'; text: string } | null>(null);

  // Form States
  const [formData, setFormData] = useState({
    email: '',
    full_name: '',
    password: '',
    role: 'STUDENT' as UserRole,
    is_active: true
  });
  const [resetPasswordText, setResetPasswordText] = useState('');

  const fetchUsers = async () => {
    try {
      const res = await apiClient.get('/users', { params: { search: search || undefined } });
      setUsers(res.data);
    } catch (e) {
      console.error(e);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchUsers();
  }, [search]);

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      const res = await apiClient.post('/users', formData);
      const createdUser = res.data;
      const initialPassword = formData.password;

      // Close create modal and open Send Mail modal with the newly created user's credentials
      setIsCreateOpen(false);
      setFormData({ email: '', full_name: '', password: '', role: 'STUDENT', is_active: true });
      setEmailStatusMsg(null);
      setCreatedUserCredential({
        id: createdUser.id,
        email: createdUser.email,
        full_name: createdUser.full_name,
        role: createdUser.role,
        password: initialPassword
      });

      fetchUsers();
    } catch (err: any) {
      alert(err.response?.data?.detail || 'Failed to create user');
    }
  };

  const handleSendMail = async () => {
    if (!createdUserCredential || isSendingMail) return;

    setIsSendingMail(true);
    setEmailStatusMsg(null);

    try {
      const res = await apiClient.post(`/users/${createdUserCredential.id}/send-credentials`, {
        initial_password: createdUserCredential.password
      });

      setEmailStatusMsg({
        type: 'success',
        text: res.data.message || `Login credentials sent successfully to ${createdUserCredential.email}.`
      });
    } catch (err: any) {
      const errorDetail = err.response?.data?.detail || err.message || 'SMTP server or network connection error.';
      setEmailStatusMsg({
        type: 'error',
        text: `Failed to send email: ${errorDetail}`
      });
    } finally {
      setIsSendingMail(false);
    }
  };

  const handleUpdate = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedUser) return;
    try {
      await apiClient.put(`/users/${selectedUser.id}`, {
        full_name: formData.full_name,
        role: formData.role,
        is_active: formData.is_active
      });
      setIsEditOpen(false);
      fetchUsers();
    } catch (err: any) {
      alert(err.response?.data?.detail || 'Failed to update user');
    }
  };

  const handleDelete = async (user: User) => {
    if (window.confirm(`Are you sure you want to delete user ${user.email}?`)) {
      try {
        await apiClient.delete(`/users/${user.id}`);
        fetchUsers();
      } catch (err: any) {
        alert(err.response?.data?.detail || 'Failed to delete user');
      }
    }
  };

  const handleResetPassword = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedUser || !resetPasswordText) return;
    try {
      await apiClient.post(`/users/${selectedUser.id}/reset-password`, {
        new_password: resetPasswordText
      });
      alert('Password reset successfully!');
      setIsResetOpen(false);
      setResetPasswordText('');
    } catch (err: any) {
      alert(err.response?.data?.detail || 'Failed to reset password');
    }
  };

  return (
    <div className="flex-1 min-h-screen bg-dark-900 pb-12">
      <Topbar title="Enterprise User Management" />

      <main className="p-6 max-w-7xl mx-auto space-y-6">
        {/* Controls Header */}
        <div className="flex flex-col sm:flex-row items-center justify-between gap-4">
          <div className="relative w-full sm:w-80">
            <Search className="w-4 h-4 text-slate-500 absolute left-3.5 top-3.5" />
            <input
              type="text"
              placeholder="Search users by name or email..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="w-full pl-10 pr-4 py-2.5 rounded-xl bg-slate-900 border border-slate-800 text-white text-xs placeholder-slate-500 focus:outline-none focus:border-indigo-500"
            />
          </div>

          <button
            onClick={() => {
              setFormData({ email: '', full_name: '', password: '', role: 'STUDENT', is_active: true });
              setIsCreateOpen(true);
            }}
            className="w-full sm:w-auto px-4 py-2.5 rounded-xl bg-gradient-to-r from-indigo-600 to-cyan-600 hover:from-indigo-500 hover:to-cyan-500 text-white font-semibold text-xs flex items-center justify-center gap-2 shadow-lg shadow-indigo-600/20 cursor-pointer"
          >
            <UserPlus className="w-4 h-4" />
            <span>Create New User</span>
          </button>
        </div>

        {/* User Table */}
        <div className="glass-panel rounded-2xl border border-slate-800 overflow-hidden">
          {isLoading ? (
            <div className="p-12 text-center text-slate-400 text-xs flex flex-col items-center gap-2">
              <Loader2 className="w-6 h-6 animate-spin text-indigo-500" />
              <span>Fetching user records...</span>
            </div>
          ) : users.length === 0 ? (
            <EmptyState
              title="No Users Found"
              description="No registered user accounts found matching your query."
              icon={Users}
            />
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs">
                <thead className="bg-slate-900/80 border-b border-slate-800 text-slate-400 uppercase tracking-wider font-semibold">
                  <tr>
                    <th className="px-6 py-4">User Details</th>
                    <th className="px-6 py-4">Role</th>
                    <th className="px-6 py-4">Account Status</th>
                    <th className="px-6 py-4">Created Date</th>
                    <th className="px-6 py-4 text-right">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-800/60">
                  {users.map((u) => (
                    <tr key={u.id} className="hover:bg-slate-800/40 transition-colors">
                      <td className="px-6 py-4">
                        <div>
                          <p className="font-bold text-white">{u.full_name}</p>
                          <p className="text-slate-400 text-[11px]">{u.email}</p>
                        </div>
                      </td>
                      <td className="px-6 py-4">
                        <span className={`px-2.5 py-1 rounded-md text-[10px] font-bold uppercase ${
                          u.role === 'ADMIN' ? 'bg-amber-500/20 text-amber-300 border border-amber-500/30' : 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/30'
                        }`}>
                          {u.role}
                        </span>
                      </td>
                      <td className="px-6 py-4">
                        <span className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md text-[10px] font-bold ${
                          u.is_active ? 'bg-emerald-500/20 text-emerald-300' : 'bg-rose-500/20 text-rose-300'
                        }`}>
                          {u.is_active ? <CheckCircle className="w-3 h-3" /> : <XCircle className="w-3 h-3" />}
                          {u.is_active ? 'Active' : 'Deactivated'}
                        </span>
                      </td>
                      <td className="px-6 py-4 text-slate-400">
                        {new Date(u.created_at).toLocaleDateString()}
                      </td>
                      <td className="px-6 py-4 text-right">
                        <div className="flex items-center justify-end gap-2">
                          <button
                            onClick={() => {
                              setSelectedUser(u);
                              setFormData({
                                email: u.email,
                                full_name: u.full_name,
                                password: '',
                                role: u.role,
                                is_active: u.is_active
                              });
                              setIsEditOpen(true);
                            }}
                            className="p-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 hover:text-white cursor-pointer"
                            title="Edit User"
                          >
                            <Edit3 className="w-3.5 h-3.5" />
                          </button>
                          <button
                            onClick={() => {
                              setSelectedUser(u);
                              setResetPasswordText('');
                              setIsResetOpen(true);
                            }}
                            className="p-1.5 rounded-lg bg-indigo-950 hover:bg-indigo-900 text-indigo-300 cursor-pointer"
                            title="Reset Password"
                          >
                            <KeyRound className="w-3.5 h-3.5" />
                          </button>
                          <button
                            onClick={() => handleDelete(u)}
                            className="p-1.5 rounded-lg bg-rose-950 hover:bg-rose-900 text-rose-300 cursor-pointer"
                            title="Delete User"
                          >
                            <Trash2 className="w-3.5 h-3.5" />
                          </button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </main>

      {/* Create User Modal */}
      <Modal isOpen={isCreateOpen} onClose={() => setIsCreateOpen(false)} title="Create New Enterprise User">
        <form onSubmit={handleCreate} className="space-y-4 text-xs">
          <div>
            <label className="block text-slate-300 font-semibold mb-1">Full Name</label>
            <input
              type="text"
              required
              value={formData.full_name}
              onChange={(e) => setFormData({ ...formData, full_name: e.target.value })}
              placeholder="e.g. John Doe"
              className="w-full px-3 py-2 rounded-xl bg-slate-900 border border-slate-700 text-white focus:outline-none focus:border-indigo-500"
            />
          </div>
          <div>
            <label className="block text-slate-300 font-semibold mb-1">Email Address</label>
            <input
              type="email"
              required
              value={formData.email}
              onChange={(e) => setFormData({ ...formData, email: e.target.value })}
              placeholder="e.g. user@talentsphere.com"
              className="w-full px-3 py-2 rounded-xl bg-slate-900 border border-slate-700 text-white focus:outline-none focus:border-indigo-500"
            />
          </div>
          <div>
            <label className="block text-slate-300 font-semibold mb-1">Initial Password</label>
            <input
              type="password"
              required
              value={formData.password}
              onChange={(e) => setFormData({ ...formData, password: e.target.value })}
              className="w-full px-3 py-2 rounded-xl bg-slate-900 border border-slate-700 text-white focus:outline-none focus:border-indigo-500"
            />
          </div>
          <div>
            <label className="block text-slate-300 font-semibold mb-1">Assigned Role</label>
            <select
              value={formData.role}
              onChange={(e) => setFormData({ ...formData, role: e.target.value as UserRole })}
              className="w-full px-3 py-2 rounded-xl bg-slate-900 border border-slate-700 text-white focus:outline-none focus:border-indigo-500"
            >
              <option value="STUDENT">Student Learner</option>
              <option value="ADMIN">System Administrator</option>
            </select>
          </div>
          <button
            type="submit"
            className="w-full py-3 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-white font-bold cursor-pointer"
          >
            Create User Account
          </button>
        </form>
      </Modal>

      {/* Post-Creation "Send Mail" Modal */}
      <Modal
        isOpen={!!createdUserCredential}
        onClose={() => {
          setCreatedUserCredential(null);
          setEmailStatusMsg(null);
        }}
        title="User Created Successfully"
      >
        <div className="space-y-5 text-xs">
          <div className="p-4 rounded-2xl bg-emerald-500/10 border border-emerald-500/30 flex items-start gap-3">
            <CheckCircle className="w-5 h-5 text-emerald-400 shrink-0 mt-0.5" />
            <div>
              <h4 className="font-bold text-white text-sm">Account Created</h4>
              <p className="text-slate-300 mt-1">
                User <strong className="text-white">{createdUserCredential?.full_name}</strong> (<span className="text-indigo-300">{createdUserCredential?.email}</span>) was registered successfully.
              </p>
            </div>
          </div>

          <div className="p-4 rounded-2xl bg-slate-900 border border-slate-800 space-y-2">
            <p className="text-[11px] font-bold text-slate-400 uppercase tracking-wider">Account Credentials Summary</p>
            <div className="flex justify-between items-center py-1 border-b border-slate-800">
              <span className="text-slate-400">Email:</span>
              <span className="text-white font-mono font-bold">{createdUserCredential?.email}</span>
            </div>
            <div className="flex justify-between items-center py-1 border-b border-slate-800">
              <span className="text-slate-400">Initial Password:</span>
              <span className="text-indigo-300 font-mono font-bold">••••••••</span>
            </div>
            <div className="flex justify-between items-center py-1">
              <span className="text-slate-400">Assigned Role:</span>
              <span className="text-emerald-400 font-bold uppercase">{createdUserCredential?.role}</span>
            </div>
          </div>

          {emailStatusMsg && (
            <div className={`p-3.5 rounded-xl border text-xs flex items-center gap-2 ${
              emailStatusMsg.type === 'success'
                ? 'bg-emerald-950/60 border-emerald-500/40 text-emerald-300'
                : 'bg-rose-950/60 border-rose-500/40 text-rose-300'
            }`}>
              {emailStatusMsg.type === 'success' ? (
                <CheckCircle className="w-4 h-4 text-emerald-400 shrink-0" />
              ) : (
                <ShieldAlert className="w-4 h-4 text-rose-400 shrink-0" />
              )}
              <span>{emailStatusMsg.text}</span>
            </div>
          )}

          <div className="flex flex-col sm:flex-row items-center gap-3 pt-2">
            <button
              type="button"
              onClick={handleSendMail}
              disabled={isSendingMail}
              className="w-full py-3 rounded-xl bg-gradient-to-r from-indigo-600 to-cyan-600 hover:from-indigo-500 hover:to-cyan-500 text-white font-bold text-xs flex items-center justify-center gap-2 shadow-lg shadow-indigo-600/30 transition-all cursor-pointer disabled:opacity-50"
            >
              {isSendingMail ? (
                <>
                  <Loader2 className="w-4 h-4 animate-spin" />
                  <span>Sending Credentials Mail...</span>
                </>
              ) : (
                <>
                  <Mail className="w-4 h-4" />
                  <span>{emailStatusMsg?.type === 'success' ? 'Send Mail Again' : 'Send Mail'}</span>
                </>
              )}
            </button>

            <button
              type="button"
              onClick={() => {
                setCreatedUserCredential(null);
                setEmailStatusMsg(null);
              }}
              className="w-full sm:w-auto px-5 py-3 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-300 hover:text-white font-semibold text-xs transition-colors cursor-pointer"
            >
              Done
            </button>
          </div>
        </div>
      </Modal>

      {/* Edit User Modal */}
      <Modal isOpen={isEditOpen} onClose={() => setIsEditOpen(false)} title="Edit User Details">
        <form onSubmit={handleUpdate} className="space-y-4 text-xs">
          <div>
            <label className="block text-slate-300 font-semibold mb-1">Full Name</label>
            <input
              type="text"
              required
              value={formData.full_name}
              onChange={(e) => setFormData({ ...formData, full_name: e.target.value })}
              className="w-full px-3 py-2 rounded-xl bg-slate-900 border border-slate-700 text-white"
            />
          </div>
          <div>
            <label className="block text-slate-300 font-semibold mb-1">Role</label>
            <select
              value={formData.role}
              onChange={(e) => setFormData({ ...formData, role: e.target.value as UserRole })}
              className="w-full px-3 py-2 rounded-xl bg-slate-900 border border-slate-700 text-white"
            >
              <option value="STUDENT">Student Learner</option>
              <option value="ADMIN">System Administrator</option>
            </select>
          </div>
          <div>
            <label className="flex items-center gap-2 text-slate-300 font-semibold cursor-pointer">
              <input
                type="checkbox"
                checked={formData.is_active}
                onChange={(e) => setFormData({ ...formData, is_active: e.target.checked })}
                className="w-4 h-4 rounded border-slate-700 bg-slate-900 text-indigo-600"
              />
              <span>Account Active Status</span>
            </label>
          </div>
          <button type="submit" className="w-full py-3 rounded-xl bg-indigo-600 text-white font-bold cursor-pointer">
            Save User Changes
          </button>
        </form>
      </Modal>

      {/* Reset Password Modal */}
      <Modal isOpen={isResetOpen} onClose={() => setIsResetOpen(false)} title={`Reset Password for ${selectedUser?.email}`}>
        <form onSubmit={handleResetPassword} className="space-y-4 text-xs">
          <div>
            <label className="block text-slate-300 font-semibold mb-1">New Password</label>
            <input
              type="password"
              required
              value={resetPasswordText}
              onChange={(e) => setResetPasswordText(e.target.value)}
              placeholder="Enter new password"
              className="w-full px-3 py-2 rounded-xl bg-slate-900 border border-slate-700 text-white"
            />
          </div>
          <button type="submit" className="w-full py-3 rounded-xl bg-indigo-600 text-white font-bold cursor-pointer">
            Reset Password
          </button>
        </form>
      </Modal>
    </div>
  );
};
