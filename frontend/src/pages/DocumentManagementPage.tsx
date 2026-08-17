import React, { useState, useEffect } from 'react';
import { Topbar } from '../components/Topbar';
import { Modal } from '../components/Modal';
import { EmptyState } from '../components/EmptyState';
import { useAuth } from '../context/AuthContext';
import { DocumentItem } from '../types';
import { apiClient } from '../api/client';
import { FileText, Upload, Download, Edit3, Trash2, Database, Loader2, FileUp, Eye } from 'lucide-react';

export const DocumentManagementPage: React.FC = () => {
  const { token, isAdmin } = useAuth();
  const [documents, setDocuments] = useState<DocumentItem[]>([]);
  const [isLoading, setIsLoading] = useState(true);

  // Modals
  const [isUploadOpen, setIsUploadOpen] = useState(false);
  const [isRenameOpen, setIsRenameOpen] = useState(false);
  const [selectedDoc, setSelectedDoc] = useState<DocumentItem | null>(null);

  // Form states
  const [uploadTitle, setUploadTitle] = useState('');
  const [uploadFile, setUploadFile] = useState<File | null>(null);
  const [renameTitle, setRenameTitle] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);

  const fetchDocuments = async () => {
    try {
      const res = await apiClient.get('/documents');
      setDocuments(res.data);
    } catch (e) {
      console.error(e);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchDocuments();
  }, []);

  const handleUpload = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!uploadFile || !uploadTitle.trim()) return;

    setIsSubmitting(true);
    const formData = new FormData();
    formData.append('title', uploadTitle);
    formData.append('file', uploadFile);

    try {
      await apiClient.post('/documents/upload', formData, {
        headers: { 'Content-Type': 'multipart/form-data' }
      });
      setIsUploadOpen(false);
      setUploadTitle('');
      setUploadFile(null);
      fetchDocuments();
    } catch (err: any) {
      alert(err.response?.data?.detail || 'Failed to upload document');
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleRename = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedDoc || !renameTitle.trim()) return;
    try {
      await apiClient.put(`/documents/${selectedDoc.id}/rename`, { title: renameTitle });
      setIsRenameOpen(false);
      fetchDocuments();
    } catch (err: any) {
      alert(err.response?.data?.detail || 'Failed to rename document');
    }
  };

  const handleDelete = async (doc: DocumentItem) => {
    if (window.confirm(`Are you sure you want to delete document '${doc.title}'?`)) {
      try {
        await apiClient.delete(`/documents/${doc.id}`);
        fetchDocuments();
      } catch (err: any) {
        alert(err.response?.data?.detail || 'Failed to delete document');
      }
    }
  };

  const handleDownload = (doc: DocumentItem) => {
    window.open(`/api/documents/${doc.id}/download`, '_blank');
  };

  return (
    <div className="flex-1 min-h-screen bg-dark-900 pb-12">
      <Topbar title="Knowledge Document Repository" />

      <main className="p-6 max-w-7xl mx-auto space-y-6">
        <div className="flex items-center justify-between">
          <div>
            <h3 className="font-bold text-white text-base">Uploaded Study Materials</h3>
            <p className="text-xs text-slate-400">PDF documents indexed into ChromaDB vector store</p>
          </div>

          {isAdmin && (
            <button
              onClick={() => setIsUploadOpen(true)}
              className="px-4 py-2.5 rounded-xl bg-gradient-to-r from-indigo-600 to-cyan-600 hover:from-indigo-500 hover:to-cyan-500 text-white font-semibold text-xs flex items-center gap-2 shadow-lg shadow-indigo-600/20"
            >
              <Upload className="w-4 h-4" />
              <span>Upload PDF Document</span>
            </button>
          )}
        </div>

        <div className="glass-panel rounded-2xl border border-slate-800 overflow-hidden">
          {isLoading ? (
            <div className="p-12 text-center text-slate-400 text-xs flex flex-col items-center gap-2">
              <Loader2 className="w-6 h-6 animate-spin text-indigo-500" />
              <span>Loading documents...</span>
            </div>
          ) : documents.length === 0 ? (
            <EmptyState
              title="No Documents Uploaded"
              description="The knowledge base is currently empty. Administrators can upload PDF files to populate the vector search index."
              icon={FileText}
              actionButton={
                isAdmin ? (
                  <button
                    onClick={() => setIsUploadOpen(true)}
                    className="px-4 py-2 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-white font-semibold text-xs flex items-center gap-2"
                  >
                    <Upload className="w-4 h-4" /> Upload First PDF
                  </button>
                ) : undefined
              }
            />
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4 p-5">
              {documents.map((doc) => (
                <div key={doc.id} className="glass-card p-4 rounded-xl border border-slate-800 flex flex-col justify-between hover:border-indigo-500/30 transition-all">
                  <div>
                    <div className="flex items-start justify-between gap-3 mb-3">
                      <div className="p-3 rounded-xl bg-indigo-600/20 text-indigo-400 border border-indigo-500/30">
                        <FileText className="w-6 h-6" />
                      </div>
                      <span className="inline-flex items-center gap-1 text-[10px] font-bold px-2 py-0.5 rounded bg-cyan-500/20 text-cyan-300 border border-cyan-500/30">
                        <Database className="w-3 h-3" />
                        {doc.chunk_count ?? 0} Chunks
                      </span>
                    </div>

                    <div className="flex items-center gap-2 mb-1">
                      <h4 className="font-bold text-white text-sm truncate flex-1" title={doc.title}>{doc.title}</h4>
                      {doc.is_study_plan_doc && (
                        <span className="px-2 py-0.5 rounded text-[9px] font-bold bg-emerald-500/20 text-emerald-300 border border-emerald-500/30 shrink-0">
                          Study Plan ✅
                        </span>
                      )}
                    </div>
                    <p className="text-[11px] text-slate-400 mt-1">
                      Size: {(doc.file_size / (1024 * 1024)).toFixed(2)} MB • {new Date(doc.created_at).toLocaleDateString()}
                    </p>
                  </div>

                  <div className="mt-4 pt-3 border-t border-slate-800/80 flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <button
                        onClick={() => window.open(`/api/documents/${doc.id}/view?token=${encodeURIComponent(token || '')}`, '_blank')}
                        className="px-3 py-1.5 rounded-lg bg-indigo-600/20 hover:bg-indigo-600/40 text-indigo-300 border border-indigo-500/30 text-xs font-semibold flex items-center gap-1.5 transition-colors"
                        title="View original PDF in browser"
                      >
                        <Eye className="w-3.5 h-3.5" /> View
                      </button>
                      <button
                        onClick={() => handleDownload(doc)}
                        className="px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs font-semibold flex items-center gap-1.5"
                      >
                        <Download className="w-3.5 h-3.5" /> Download
                      </button>
                    </div>

                    {isAdmin && (
                      <div className="flex items-center gap-1">
                        <button
                          onClick={() => {
                            setSelectedDoc(doc);
                            setRenameTitle(doc.title);
                            setIsRenameOpen(true);
                          }}
                          className="p-1.5 rounded-lg text-slate-400 hover:text-white hover:bg-slate-800"
                          title="Rename PDF"
                        >
                          <Edit3 className="w-3.5 h-3.5" />
                        </button>
                        <button
                          onClick={() => handleDelete(doc)}
                          className="p-1.5 rounded-lg text-rose-400 hover:text-rose-300 hover:bg-rose-950/40"
                          title="Delete PDF"
                        >
                          <Trash2 className="w-3.5 h-3.5" />
                        </button>
                      </div>
                    )}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </main>

      {/* Upload Modal */}
      <Modal isOpen={isUploadOpen} onClose={() => setIsUploadOpen(false)} title="Upload PDF Study Document">
        <form onSubmit={handleUpload} className="space-y-4 text-xs">
          <div>
            <label className="block text-slate-300 font-semibold mb-1">Document Display Title</label>
            <input
              type="text"
              required
              value={uploadTitle}
              onChange={(e) => setUploadTitle(e.target.value)}
              placeholder="e.g. Advanced Cybersecurity Framework 2026"
              className="w-full px-3 py-2.5 rounded-xl bg-slate-900 border border-slate-700 text-white focus:outline-none focus:border-indigo-500"
            />
          </div>

          <div>
            <label className="block text-slate-300 font-semibold mb-1">Select PDF File</label>
            <div className="border-2 border-dashed border-slate-700 rounded-xl p-6 text-center hover:border-indigo-500 transition-colors">
              <input
                type="file"
                accept=".pdf"
                required
                onChange={(e) => setUploadFile(e.target.files?.[0] || null)}
                className="hidden"
                id="pdf-file-input"
              />
              <label htmlFor="pdf-file-input" className="cursor-pointer flex flex-col items-center gap-2">
                <FileUp className="w-8 h-8 text-indigo-400" />
                <span className="text-slate-300 font-medium">
                  {uploadFile ? uploadFile.name : 'Click to browse PDF file'}
                </span>
                <span className="text-[10px] text-slate-500">Only PDF formats supported up to 50MB</span>
              </label>
            </div>
          </div>

          <button
            type="submit"
            disabled={isSubmitting}
            className="w-full py-3 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-white font-bold flex items-center justify-center gap-2"
          >
            {isSubmitting ? <Loader2 className="w-4 h-4 animate-spin" /> : 'Upload & Index into ChromaDB'}
          </button>
        </form>
      </Modal>

      {/* Rename Modal */}
      <Modal isOpen={isRenameOpen} onClose={() => setIsRenameOpen(false)} title={`Rename Document`}>
        <form onSubmit={handleRename} className="space-y-4 text-xs">
          <div>
            <label className="block text-slate-300 font-semibold mb-1">New Document Title</label>
            <input
              type="text"
              required
              value={renameTitle}
              onChange={(e) => setRenameTitle(e.target.value)}
              className="w-full px-3 py-2.5 rounded-xl bg-slate-900 border border-slate-700 text-white"
            />
          </div>
          <button type="submit" className="w-full py-3 rounded-xl bg-indigo-600 text-white font-bold">
            Save Title
          </button>
        </form>
      </Modal>
    </div>
  );
};
