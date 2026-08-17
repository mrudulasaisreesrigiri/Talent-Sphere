import React, { useState, useEffect } from 'react';
import { Topbar } from '../components/Topbar';
import { AuditLogItem } from '../types';
import { apiClient } from '../api/client';
import { ShieldCheck, History, Loader2 } from 'lucide-react';

export const AuditLogsPage: React.FC = () => {
  const [logs, setLogs] = useState<AuditLogItem[]>([]);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    const fetchLogs = async () => {
      try {
        const res = await apiClient.get('/audit-logs');
        setLogs(res.data);
      } catch (e) {
        console.error(e);
      } finally {
        setIsLoading(false);
      }
    };
    fetchLogs();
  }, []);

  return (
    <div className="flex-1 min-h-screen bg-dark-900 pb-12">
      <Topbar title="Security & System Audit Trail" />

      <main className="p-6 max-w-7xl mx-auto space-y-6">
        <div className="flex items-center gap-3">
          <div className="p-2.5 rounded-xl bg-amber-600/20 text-amber-400 border border-amber-500/30">
            <ShieldCheck className="w-5 h-5" />
          </div>
          <div>
            <h3 className="font-bold text-white text-base">Immutable Audit Records</h3>
            <p className="text-xs text-slate-400">Recorded action trail stored in normalized MySQL audit log table</p>
          </div>
        </div>

        <div className="glass-panel rounded-2xl border border-slate-800 overflow-hidden">
          {isLoading ? (
            <div className="p-12 text-center text-slate-400 text-xs flex flex-col items-center gap-2">
              <Loader2 className="w-6 h-6 animate-spin text-indigo-500" />
              <span>Fetching system audit trail...</span>
            </div>
          ) : logs.length === 0 ? (
            <div className="p-12 text-center text-slate-400 text-xs">
              No audit log entries recorded yet.
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs">
                <thead className="bg-slate-900/80 border-b border-slate-800 text-slate-400 uppercase tracking-wider font-semibold">
                  <tr>
                    <th className="px-6 py-4">Timestamp</th>
                    <th className="px-6 py-4">Action Event</th>
                    <th className="px-6 py-4">Entity Type</th>
                    <th className="px-6 py-4">Details</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-800/60 font-mono">
                  {logs.map((log) => (
                    <tr key={log.id} className="hover:bg-slate-800/40">
                      <td className="px-6 py-3.5 text-slate-400">
                        {new Date(log.timestamp).toLocaleString()}
                      </td>
                      <td className="px-6 py-3.5">
                        <span className="font-bold text-indigo-400">{log.action}</span>
                      </td>
                      <td className="px-6 py-3.5 text-slate-300">
                        {log.entity_type}
                      </td>
                      <td className="px-6 py-3.5 text-slate-400">
                        {log.details || 'N/A'}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </main>
    </div>
  );
};
