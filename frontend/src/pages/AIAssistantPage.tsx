import React, { useState, useEffect, useRef } from 'react';
import { Topbar } from '../components/Topbar';
import { ChatMessage, Citation } from '../types';
import { apiClient } from '../api/client';
import ReactMarkdown from 'react-markdown';
import {
  Bot, Send, Sparkles, Copy, RefreshCw, Trash2, Search, Plus, FileText, Check, AlertCircle, Loader2, User as UserIcon
} from 'lucide-react';

export const AIAssistantPage: React.FC = () => {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [inputMessage, setInputMessage] = useState('');
  const [sessionId, setSessionId] = useState('default');
  const [sessions, setSessions] = useState<string[]>(['default']);
  const [searchQuery, setSearchQuery] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [copiedId, setCopiedId] = useState<string | null>(null);

  const messagesEndRef = useRef<HTMLDivElement>(null);

  const suggestedQuestions = [
    "What are the core principles outlined in our study documents?",
    "Summarize the mandatory compliance requirements.",
    "Explain key definitions from page 1 of the reference material."
  ];

  const fetchHistory = async (sessId: string) => {
    try {
      const res = await apiClient.get('/chat/history', { params: { session_id: sessId } });
      setMessages(res.data || []);
    } catch (e) {
      console.error('Failed to fetch chat history:', e);
      setMessages([]);
    }
  };

  const fetchSessions = async () => {
    try {
      const res = await apiClient.get('/chat/sessions');
      if (res.data && Array.isArray(res.data) && res.data.length > 0) {
        setSessions(res.data);
      } else {
        setSessions(['default']);
      }
    } catch (e) {
      console.error('Failed to fetch chat sessions:', e);
      setSessions(['default']);
    }
  };

  useEffect(() => {
    fetchSessions();
    fetchHistory(sessionId);
  }, [sessionId]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, isLoading]);

  const handleSendMessage = async (textToSend?: string) => {
    const text = textToSend || inputMessage;
    if (!text.trim() || isLoading) return;

    const userTempMsg: ChatMessage = {
      id: Date.now().toString(),
      session_id: sessionId,
      role: 'user',
      message: text,
      created_at: new Date().toISOString()
    };

    setMessages(prev => [...prev, userTempMsg]);
    if (!textToSend) setInputMessage('');
    setIsLoading(true);

    try {
      const res = await apiClient.post('/chat', {
        message: text,
        session_id: sessionId
      });
      // Refresh chat history directly from database to ensure exact sync
      await fetchHistory(sessionId);
      await fetchSessions();
    } catch (e) {
      console.error(e);
      const errMsg: ChatMessage = {
        id: (Date.now() + 1).toString(),
        session_id: sessionId,
        role: 'assistant',
        message: 'Sorry, I encountered an error retrieving the document context. Please try again.',
        created_at: new Date().toISOString()
      };
      setMessages(prev => [...prev, errMsg]);
    } finally {
      setIsLoading(false);
    }
  };

  const handleCopy = (text: string, id: string) => {
    navigator.clipboard.writeText(text);
    setCopiedId(id);
    setTimeout(() => setCopiedId(null), 2000);
  };

  const handleRegenerate = () => {
    const lastUserMsg = [...messages].reverse().find(m => m.role === 'user');
    if (lastUserMsg) {
      handleSendMessage(lastUserMsg.message);
    }
  };

  /**
   * Permanently deletes a specific session's messages from the database
   */
  const handleDeleteSession = async (sessToDelete: string) => {
    if (window.confirm(`Permanently delete all messages in session '${sessToDelete}'?`)) {
      try {
        await apiClient.delete(`/chat/sessions/${encodeURIComponent(sessToDelete)}`);
        
        // If deleting active session, reset state
        if (sessionId === sessToDelete) {
          setMessages([]);
          const remainingSessions = sessions.filter(s => s !== sessToDelete);
          const nextSession = remainingSessions[0] || 'default';
          setSessionId(nextSession);
          await fetchHistory(nextSession);
        } else {
          await fetchHistory(sessionId);
        }
        await fetchSessions();
      } catch (e) {
        console.error('Failed to permanently delete chat session:', e);
        alert('Failed to delete chat session from database.');
      }
    }
  };

  /**
   * Permanently clears all chat messages in the currently active session
   */
  const handleClearActiveSession = async () => {
    if (window.confirm(`Permanently clear all messages from current session '${sessionId}'?`)) {
      try {
        await apiClient.delete('/chat/history', { params: { session_id: sessionId } });
        setMessages([]);
        await fetchHistory(sessionId);
        await fetchSessions();
      } catch (e) {
        console.error('Failed to clear active session history:', e);
        alert('Failed to clear chat history from database.');
      }
    }
  };

  /**
   * Permanently clears ALL chat messages across ALL sessions for the logged-in user
   */
  const handleClearAllHistory = async () => {
    if (window.confirm('Permanently delete ALL your chat history and conversations from the database? This cannot be undone.')) {
      try {
        await apiClient.delete('/chat/history');
        setMessages([]);
        setSessions(['default']);
        setSessionId('default');
        await fetchHistory('default');
        await fetchSessions();
      } catch (e) {
        console.error('Failed to clear entire chat history:', e);
        alert('Failed to clear all chat history from database.');
      }
    }
  };

  const createNewSession = () => {
    const newSessName = `chat_${Date.now().toString().slice(-4)}`;
    setSessions(prev => [newSessName, ...prev]);
    setSessionId(newSessName);
    setMessages([]);
  };

  return (
    <div className="flex-1 min-h-screen bg-dark-900 flex flex-col">
      <Topbar title="AI RAG Learning Assistant" />

      <div className="flex-1 flex max-w-7xl mx-auto w-full p-4 gap-4 h-[calc(100vh-80px)] overflow-hidden">
        {/* Chat History Sidebar */}
        <aside className="w-64 glass-panel rounded-2xl border border-slate-800 p-3.5 flex flex-col justify-between hidden md:flex h-full overflow-hidden shrink-0">
          <div className="flex flex-col h-full overflow-hidden">
            <button
              onClick={createNewSession}
              className="w-full py-2.5 px-3 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-bold flex items-center justify-center gap-2 mb-3 shadow-md shadow-indigo-600/20 shrink-0 cursor-pointer"
            >
              <Plus className="w-4 h-4" /> New Chat Session
            </button>

            <div className="relative mb-3 shrink-0">
              <Search className="w-3.5 h-3.5 text-slate-500 absolute left-3 top-2.5" />
              <input
                type="text"
                placeholder="Search history..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="w-full pl-9 pr-3 py-1.5 rounded-lg bg-slate-900 border border-slate-800 text-[11px] text-white placeholder-slate-500 focus:outline-none focus:border-indigo-500"
              />
            </div>

            <div className="flex items-center justify-between px-2 mb-2 shrink-0">
              <p className="text-[10px] font-bold uppercase tracking-wider text-slate-500">History Sessions</p>
              <button
                onClick={handleClearAllHistory}
                className="text-[10px] text-rose-400 hover:text-rose-300 font-semibold hover:underline flex items-center gap-0.5 cursor-pointer"
                title="Permanently clear all chat history"
              >
                <Trash2 className="w-2.5 h-2.5" /> Clear All
              </button>
            </div>

            <div className="space-y-1 overflow-y-auto flex-1 pr-1">
              {sessions
                .filter(s => s.toLowerCase().includes(searchQuery.toLowerCase()))
                .map((s) => (
                  <div
                    key={s}
                    onClick={() => setSessionId(s)}
                    className={`px-3 py-2 rounded-xl text-xs flex items-center justify-between cursor-pointer transition-colors group ${
                      sessionId === s
                        ? 'bg-indigo-600/20 text-indigo-300 font-bold border border-indigo-500/30'
                        : 'text-slate-400 hover:bg-slate-800'
                    }`}
                  >
                    <span className="truncate max-w-[130px]">{s}</span>
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        handleDeleteSession(s);
                      }}
                      className="text-slate-500 hover:text-rose-400 p-1 opacity-60 group-hover:opacity-100 transition-opacity cursor-pointer"
                      title={`Permanently delete session '${s}'`}
                    >
                      <Trash2 className="w-3 h-3" />
                    </button>
                  </div>
                ))}
            </div>
          </div>

          <div className="p-3 rounded-xl bg-slate-900/60 border border-slate-800 text-[10px] text-slate-400 space-y-1 shrink-0 mt-3">
            <span className="font-bold text-indigo-400 flex items-center gap-1">
              <Sparkles className="w-3 h-3" /> RAG Grounded
            </span>
            <p>Answers synthesized directly from uploaded ChromaDB vector chunks with source page citations.</p>
          </div>
        </aside>

        {/* Main Chat Workspace */}
        <main className="flex-1 glass-panel rounded-2xl border border-slate-800 flex flex-col h-full overflow-hidden min-w-0">
          {/* Header Bar */}
          <div className="px-6 py-3 border-b border-slate-800/80 bg-slate-900/40 flex items-center justify-between shrink-0">
            <div className="flex items-center gap-2">
              <div className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse"></div>
              <span className="text-xs font-semibold text-slate-300">Session: <strong className="text-white">{sessionId}</strong></span>
              <span className="text-[11px] text-slate-500">({messages.length} messages)</span>
            </div>
            {messages.length > 0 && (
              <button
                onClick={handleClearActiveSession}
                className="px-3 py-1.5 rounded-lg bg-rose-600/10 hover:bg-rose-600/20 text-rose-400 border border-rose-500/20 text-xs font-medium flex items-center gap-1.5 transition-colors cursor-pointer"
                title="Permanently clear messages in this session"
              >
                <Trash2 className="w-3.5 h-3.5" /> Clear Session History
              </button>
            )}
          </div>

          {/* Message Stream */}
          <div className="flex-1 p-6 overflow-y-auto space-y-6 min-h-0">
            {messages.length === 0 ? (
              <div className="h-full flex flex-col items-center justify-center text-center p-6 space-y-6">
                <div className="w-16 h-16 rounded-2xl bg-indigo-600/20 text-indigo-400 border border-indigo-500/30 flex items-center justify-center shadow-lg">
                  <Bot className="w-8 h-8" />
                </div>
                <div>
                  <h3 className="font-extrabold text-white text-lg">AI Performance & Learning Assistant</h3>
                  <p className="text-xs text-slate-400 max-w-sm mt-1">
                    Ask questions grounded strictly on your enterprise documents without hallucinations.
                  </p>
                </div>

                <div className="w-full max-w-md space-y-2 text-left">
                  <p className="text-[11px] font-bold text-slate-500 uppercase tracking-wider">Suggested Questions:</p>
                  {suggestedQuestions.map((q, idx) => (
                    <button
                      key={idx}
                      onClick={() => handleSendMessage(q)}
                      className="w-full p-3 rounded-xl bg-slate-900/80 hover:bg-slate-800 border border-slate-800 text-xs text-indigo-300 font-medium text-left transition-colors flex items-center justify-between cursor-pointer"
                    >
                      <span>{q}</span>
                      <Sparkles className="w-3.5 h-3.5 text-indigo-400" />
                    </button>
                  ))}
                </div>
              </div>
            ) : (
              messages.map((m) => (
                <div
                  key={m.id}
                  className={`flex gap-3 max-w-3xl ${m.role === 'user' ? 'ml-auto flex-row-reverse' : ''}`}
                >
                  <div className={`w-8 h-8 rounded-xl flex items-center justify-center text-xs font-bold shrink-0 ${
                    m.role === 'user' ? 'bg-cyan-600 text-white' : 'bg-indigo-600 text-white'
                  }`}>
                    {m.role === 'user' ? <UserIcon className="w-4 h-4" /> : <Bot className="w-4 h-4" />}
                  </div>

                  <div className={`p-4 rounded-2xl text-xs leading-relaxed space-y-2 ${
                    m.role === 'user'
                      ? 'bg-gradient-to-r from-indigo-600 to-cyan-600 text-white rounded-tr-none shadow-md'
                      : 'bg-slate-900/90 border border-slate-800 text-slate-200 rounded-tl-none'
                  }`}>
                    <div className="prose prose-invert prose-xs max-w-none">
                      <ReactMarkdown>{m.message}</ReactMarkdown>
                    </div>

                    {/* Source Citations Display */}
                    {m.citations && m.citations.length > 0 && (
                      <div className="mt-3 pt-3 border-t border-slate-800 space-y-1.5">
                        <p className="text-[10px] font-bold text-cyan-400 uppercase tracking-wider flex items-center gap-1">
                          <FileText className="w-3 h-3" /> Grounded References ({m.citations.length}):
                        </p>
                        {m.citations.map((c, idx) => (
                          <div key={idx} className="p-2 rounded-lg bg-slate-950/80 border border-slate-800 text-[10px] text-slate-400">
                            <span className="font-semibold text-indigo-300">{c.document_name}</span> • <span className="text-slate-300">Page {c.page_number}</span>
                            <p className="italic text-slate-500 mt-0.5 line-clamp-1">"{c.reference}"</p>
                          </div>
                        ))}
                      </div>
                    )}

                    {m.role === 'assistant' && (
                      <div className="flex items-center gap-2 pt-2 border-t border-slate-800/60 text-[10px] text-slate-500">
                        <button
                          onClick={() => handleCopy(m.message, m.id)}
                          className="hover:text-slate-300 flex items-center gap-1 cursor-pointer"
                        >
                          {copiedId === m.id ? <Check className="w-3 h-3 text-emerald-400" /> : <Copy className="w-3 h-3" />} Copy
                        </button>
                        <span>•</span>
                        <button onClick={handleRegenerate} className="hover:text-slate-300 flex items-center gap-1 cursor-pointer">
                          <RefreshCw className="w-3 h-3" /> Regenerate
                        </button>
                      </div>
                    )}
                  </div>
                </div>
              ))
            )}

            {isLoading && (
              <div className="flex gap-3 max-w-3xl">
                <div className="w-8 h-8 rounded-xl bg-indigo-600 text-white flex items-center justify-center shrink-0 animate-pulse">
                  <Bot className="w-4 h-4" />
                </div>
                <div className="p-4 rounded-2xl bg-slate-900 border border-slate-800 text-xs text-slate-400 flex items-center gap-2">
                  <Loader2 className="w-4 h-4 animate-spin text-indigo-400" />
                  <span>Searching vector database & synthesizing response...</span>
                </div>
              </div>
            )}
            <div ref={messagesEndRef} />
          </div>

          {/* Input Form Bar */}
          <form onSubmit={(e) => { e.preventDefault(); handleSendMessage(); }} className="p-4 border-t border-slate-800 bg-slate-900/60 flex items-center gap-3">
            <input
              type="text"
              value={inputMessage}
              onChange={(e) => setInputMessage(e.target.value)}
              placeholder="Ask a question about your uploaded documents..."
              className="flex-1 px-4 py-3 bg-slate-900 border border-slate-800 rounded-xl text-white text-xs placeholder-slate-500 focus:outline-none focus:border-indigo-500"
            />
            <button
              type="submit"
              disabled={isLoading || !inputMessage.trim()}
              className="p-3 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-white disabled:opacity-40 shadow-lg shadow-indigo-600/30 cursor-pointer"
            >
              <Send className="w-4 h-4" />
            </button>
          </form>
        </main>
      </div>
    </div>
  );
};
