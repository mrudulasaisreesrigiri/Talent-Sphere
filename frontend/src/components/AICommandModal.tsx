import React, { useState } from 'react';
import { Terminal, Sparkles, X, Loader2, CheckCircle2, AlertCircle } from 'lucide-react';
import { apiClient } from '../api/client';

interface AICommandModalProps {
  isOpen: boolean;
  onClose: () => void;
}

export const AICommandModal: React.FC<AICommandModalProps> = ({ isOpen, onClose }) => {
  const [command, setCommand] = useState('');
  const [docName, setDocName] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [result, setResult] = useState<{ status: string; message: string } | null>(null);
  const [error, setError] = useState<string | null>(null);

  if (!isOpen) return null;

  const handleExecute = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!command.trim()) return;

    setIsLoading(true);
    setResult(null);
    setError(null);

    try {
      const res = await apiClient.post('/ai-commands/execute', {
        command: command.trim(),
        document_name: docName?.trim() || undefined
      });
      setResult({ status: res.data.status, message: res.data.message });
      window.dispatchEvent(new CustomEvent('aiCommandExecuted', {
        detail: {
          entityType: res.data.entity_type,
          entityId: res.data.entity_id,
          message: res.data.message
        }
      }));
      setCommand('');
      setDocName('');
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to execute AI command');
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/70 backdrop-blur-md">
      <div className="glass-panel w-full max-w-xl rounded-3xl border border-indigo-500/30 p-6 shadow-2xl relative">
        <div className="flex items-center justify-between border-b border-slate-800 pb-4 mb-6">
          <div className="flex items-center gap-3">
            <div className="p-2.5 rounded-xl bg-cyan-600/20 text-cyan-400 border border-cyan-500/30">
              <Terminal className="w-5 h-5" />
            </div>
            <div>
              <h3 className="font-bold text-white text-base">Admin AI Command Center</h3>
              <p className="text-xs text-slate-400">Automated PDF-to-Exam & Announcement Generation</p>
            </div>
          </div>
          <button onClick={onClose} className="p-2 rounded-xl text-slate-400 hover:text-white hover:bg-slate-800">
            <X className="w-5 h-5" />
          </button>
        </div>

        <form onSubmit={handleExecute} className="space-y-4">
          <div>
            <label className="block text-xs font-semibold text-slate-300 uppercase tracking-wider mb-2">
              Command Directive
            </label>
            <input
              type="text"
              value={command}
              onChange={(e) => setCommand(e.target.value)}
              placeholder="e.g. Create Exam from CyberSecurity_Policy.pdf"
              className="w-full px-4 py-3 rounded-xl bg-slate-900 border border-slate-700 text-white placeholder-slate-500 text-sm focus:outline-none focus:border-cyan-500"
              required
            />
          </div>

          <div>
            <label className="block text-xs font-semibold text-slate-300 uppercase tracking-wider mb-2">
              PDF Document Name / Query (Optional)
            </label>
            <input
              type="text"
              value={docName}
              onChange={(e) => setDocName(e.target.value)}
              placeholder="e.g. CyberSecurity_Policy.pdf"
              className="w-full px-4 py-3 rounded-xl bg-slate-900 border border-slate-700 text-white placeholder-slate-500 text-sm focus:outline-none focus:border-cyan-500"
            />
          </div>

          <div className="bg-slate-900/60 p-3 rounded-xl border border-slate-800 text-[11px] text-slate-400 space-y-1">
            <p className="font-semibold text-cyan-400">Supported Commands:</p>
            <p>• <code className="text-slate-200">Create Exam from &lt;PDF Name&gt;</code> (Generates MCQs, True/False, Fill Blanks, Short Answers)</p>
            <p>• <code className="text-slate-200">Create Announcement from &lt;PDF Name&gt;</code> (Generates announcement & broadcasts notification)</p>
          </div>

          <button
            type="submit"
            disabled={isLoading}
            className="w-full py-3 rounded-xl bg-gradient-to-r from-cyan-600 to-indigo-600 hover:from-cyan-500 hover:to-indigo-500 text-white font-semibold text-sm flex items-center justify-center gap-2 shadow-lg shadow-cyan-500/20"
          >
            {isLoading ? <Loader2 className="w-5 h-5 animate-spin" /> : <><Sparkles className="w-4 h-4" /> Execute AI Command</>}
          </button>
        </form>

        {result && (
          <div className="mt-4 p-4 rounded-xl bg-emerald-950/40 border border-emerald-500/30 text-emerald-300 text-xs flex items-start gap-3">
            <CheckCircle2 className="w-5 h-5 shrink-0 text-emerald-400" />
            <div>
              <p className="font-bold">Success!</p>
              <p>{result.message}</p>
            </div>
          </div>
        )}

        {error && (
          <div className="mt-4 p-4 rounded-xl bg-rose-950/40 border border-rose-500/30 text-rose-300 text-xs flex items-start gap-3">
            <AlertCircle className="w-5 h-5 shrink-0 text-rose-400" />
            <div>
              <p className="font-bold">Error Execution</p>
              <p>{error}</p>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};
