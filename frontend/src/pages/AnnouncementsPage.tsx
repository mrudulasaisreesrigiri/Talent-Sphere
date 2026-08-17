import React, { useState, useEffect } from 'react';
import { Topbar } from '../components/Topbar';
import { Modal } from '../components/Modal';
import { EmptyState } from '../components/EmptyState';
import { useAuth } from '../context/AuthContext';
import { Announcement } from '../types';
import { apiClient } from '../api/client';
import { Megaphone, Plus, Edit3, Trash2, CheckCircle, XCircle, Sparkles, Loader2 } from 'lucide-react';

export const AnnouncementsPage: React.FC = () => {
  const { isAdmin } = useAuth();
  const [announcements, setAnnouncements] = useState<Announcement[]>([]);
  const [isLoading, setIsLoading] = useState(true);

  // Modal
  const [isCreateOpen, setIsCreateOpen] = useState(false);
  const [isEditOpen, setIsEditOpen] = useState(false);
  const [selectedAnn, setSelectedAnn] = useState<Announcement | null>(null);

  const [formData, setFormData] = useState({
    title: '',
    content: '',
    is_published: true
  });

  const fetchAnnouncements = async () => {
    try {
      const res = await apiClient.get('/announcements');
      setAnnouncements(res.data);
    } catch (e) {
      console.error(e);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchAnnouncements();
  }, []);

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      await apiClient.post('/announcements', formData);
      setIsCreateOpen(false);
      setFormData({ title: '', content: '', is_published: true });
      fetchAnnouncements();
    } catch (err: any) {
      alert(err.response?.data?.detail || 'Failed to create announcement');
    }
  };

  const handleUpdate = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedAnn) return;
    try {
      await apiClient.put(`/announcements/${selectedAnn.id}`, formData);
      setIsEditOpen(false);
      fetchAnnouncements();
    } catch (err: any) {
      alert(err.response?.data?.detail || 'Failed to update announcement');
    }
  };

  const handleDelete = async (ann: Announcement) => {
    if (window.confirm(`Delete announcement '${ann.title}'?`)) {
      try {
        await apiClient.delete(`/announcements/${ann.id}`);
        fetchAnnouncements();
      } catch (err: any) {
        alert(err.response?.data?.detail || 'Failed to delete announcement');
      }
    }
  };

  return (
    <div className="flex-1 min-h-screen bg-dark-900 pb-12">
      <Topbar title="System Announcements" />

      <main className="p-6 max-w-5xl mx-auto space-y-6">
        <div className="flex items-center justify-between">
          <div>
            <h3 className="font-bold text-white text-base">Broadcast Bulletins</h3>
            <p className="text-xs text-slate-400">Official updates, course announcements, and system alerts</p>
          </div>

          {isAdmin && (
            <button
              onClick={() => {
                setFormData({ title: '', content: '', is_published: true });
                setIsCreateOpen(true);
              }}
              className="px-4 py-2.5 rounded-xl bg-gradient-to-r from-indigo-600 to-cyan-600 hover:from-indigo-500 hover:to-cyan-500 text-white font-semibold text-xs flex items-center gap-2 shadow-lg shadow-indigo-600/20"
            >
              <Plus className="w-4 h-4" />
              <span>Create Announcement</span>
            </button>
          )}
        </div>

        <div className="glass-panel rounded-2xl border border-slate-800 p-5">
          {isLoading ? (
            <div className="p-12 text-center text-slate-400 text-xs flex flex-col items-center gap-2">
              <Loader2 className="w-6 h-6 animate-spin text-indigo-500" />
              <span>Loading announcements...</span>
            </div>
          ) : announcements.length === 0 ? (
            <EmptyState
              title="No Announcements Posted"
              description="There are currently no public announcements available."
              icon={Megaphone}
            />
          ) : (
            <div className="space-y-4">
              {announcements.map((ann) => (
                <div key={ann.id} className="glass-card p-5 rounded-2xl border border-slate-800 hover:border-indigo-500/30 transition-all">
                  <div className="flex items-start justify-between gap-4 mb-2">
                    <div className="flex items-center gap-3">
                      <div className="p-2.5 rounded-xl bg-amber-600/20 text-amber-400 border border-amber-500/30">
                        <Megaphone className="w-5 h-5" />
                      </div>
                      <div>
                        <h4 className="font-bold text-white text-base">{ann.title}</h4>
                        <p className="text-[10px] text-slate-500">
                          Posted on {new Date(ann.created_at).toLocaleString()} • {ann.source_document_name ? `Source: ${ann.source_document_name}` : 'Manual Entry'}
                        </p>
                      </div>
                    </div>

                    {isAdmin && (
                      <div className="flex items-center gap-2">
                        <span className={`px-2 py-0.5 rounded text-[10px] font-bold uppercase ${
                          ann.is_published ? 'bg-emerald-500/20 text-emerald-300' : 'bg-slate-800 text-slate-400'
                        }`}>
                          {ann.is_published ? 'Published' : 'Draft'}
                        </span>
                        <button
                          onClick={() => {
                            setSelectedAnn(ann);
                            setFormData({ title: ann.title, content: ann.content, is_published: ann.is_published });
                            setIsEditOpen(true);
                          }}
                          className="p-1.5 rounded-lg text-slate-400 hover:text-white hover:bg-slate-800"
                        >
                          <Edit3 className="w-3.5 h-3.5" />
                        </button>
                        <button
                          onClick={() => handleDelete(ann)}
                          className="p-1.5 rounded-lg text-rose-400 hover:text-rose-300 hover:bg-rose-950/40"
                        >
                          <Trash2 className="w-3.5 h-3.5" />
                        </button>
                      </div>
                    )}
                  </div>

                  <p className="text-xs text-slate-300 whitespace-pre-line leading-relaxed pl-12 mt-2">
                    {ann.content}
                  </p>
                </div>
              ))}
            </div>
          )}
        </div>
      </main>

      {/* Create Modal */}
      <Modal isOpen={isCreateOpen} onClose={() => setIsCreateOpen(false)} title="Create System Announcement">
        <form onSubmit={handleCreate} className="space-y-4 text-xs">
          <div>
            <label className="block text-slate-300 font-semibold mb-1">Announcement Title</label>
            <input
              type="text"
              required
              value={formData.title}
              onChange={(e) => setFormData({ ...formData, title: e.target.value })}
              placeholder="e.g. Schedule Update for End-of-Term Examinations"
              className="w-full px-3 py-2 rounded-xl bg-slate-900 border border-slate-700 text-white"
            />
          </div>
          <div>
            <label className="block text-slate-300 font-semibold mb-1">Content Body</label>
            <textarea
              required
              value={formData.content}
              onChange={(e) => setFormData({ ...formData, content: e.target.value })}
              className="w-full px-3 py-2 rounded-xl bg-slate-900 border border-slate-700 text-white h-28"
            />
          </div>
          <div>
            <label className="flex items-center gap-2 text-slate-300 font-semibold cursor-pointer">
              <input
                type="checkbox"
                checked={formData.is_published}
                onChange={(e) => setFormData({ ...formData, is_published: e.target.checked })}
                className="w-4 h-4 rounded border-slate-700 bg-slate-900 text-indigo-600"
              />
              <span>Publish Immediately & Broadcast Notification</span>
            </label>
          </div>
          <button type="submit" className="w-full py-3 rounded-xl bg-indigo-600 text-white font-bold">
            Post Announcement
          </button>
        </form>
      </Modal>

      {/* Edit Modal */}
      <Modal isOpen={isEditOpen} onClose={() => setIsEditOpen(false)} title="Edit Announcement">
        <form onSubmit={handleUpdate} className="space-y-4 text-xs">
          <div>
            <label className="block text-slate-300 font-semibold mb-1">Title</label>
            <input
              type="text"
              required
              value={formData.title}
              onChange={(e) => setFormData({ ...formData, title: e.target.value })}
              className="w-full px-3 py-2 rounded-xl bg-slate-900 border border-slate-700 text-white"
            />
          </div>
          <div>
            <label className="block text-slate-300 font-semibold mb-1">Content Body</label>
            <textarea
              required
              value={formData.content}
              onChange={(e) => setFormData({ ...formData, content: e.target.value })}
              className="w-full px-3 py-2 rounded-xl bg-slate-900 border border-slate-700 text-white h-28"
            />
          </div>
          <div>
            <label className="flex items-center gap-2 text-slate-300 font-semibold cursor-pointer">
              <input
                type="checkbox"
                checked={formData.is_published}
                onChange={(e) => setFormData({ ...formData, is_published: e.target.checked })}
                className="w-4 h-4 rounded border-slate-700 bg-slate-900 text-indigo-600"
              />
              <span>Published Status</span>
            </label>
          </div>
          <button type="submit" className="w-full py-3 rounded-xl bg-indigo-600 text-white font-bold">
            Save Announcement
          </button>
        </form>
      </Modal>
    </div>
  );
};
