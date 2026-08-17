import React, { useState } from 'react';
import { Topbar } from '../components/Topbar';
import { KnowledgeSearchResult } from '../types';
import { apiClient } from '../api/client';
import { Search, FileText, Database, Sparkles, Loader2, ArrowRight } from 'lucide-react';

export const KnowledgeSearchPage: React.FC = () => {
  const [query, setQuery] = useState('');
  const [results, setResults] = useState<KnowledgeSearchResult[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [hasSearched, setHasSearched] = useState(false);

  const handleSearch = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!query.trim()) return;

    setIsLoading(true);
    setHasSearched(true);

    try {
      const res = await apiClient.get('/search', { params: { q: query } });
      setResults(res.data);
    } catch (e) {
      console.error(e);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="flex-1 min-h-screen bg-dark-900 pb-12">
      <Topbar title="Semantic Knowledge Search" />

      <main className="p-6 max-w-5xl mx-auto space-y-6">
        <div className="text-center py-6">
          <div className="w-12 h-12 rounded-2xl bg-indigo-600/20 text-indigo-400 border border-indigo-500/30 mx-auto flex items-center justify-center mb-3">
            <Database className="w-6 h-6" />
          </div>
          <h2 className="text-xl font-bold text-white tracking-tight">ChromaDB Vector Repository Search</h2>
          <p className="text-xs text-slate-400 max-w-md mx-auto mt-1">
            Perform natural language similarity queries across all ingested enterprise PDF study documents.
          </p>
        </div>

        {/* Search Bar Form */}
        <form onSubmit={handleSearch} className="glass-panel p-3 rounded-2xl border border-slate-800 flex items-center gap-3">
          <div className="relative flex-1">
            <Search className="w-5 h-5 text-slate-400 absolute left-4 top-3.5" />
            <input
              type="text"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="e.g. What are the mandatory security protocols for user authentication?"
              className="w-full pl-12 pr-4 py-3 bg-slate-900/80 border border-slate-800 rounded-xl text-white text-sm placeholder-slate-500 focus:outline-none focus:border-indigo-500"
            />
          </div>
          <button
            type="submit"
            disabled={isLoading}
            className="px-6 py-3 rounded-xl bg-gradient-to-r from-indigo-600 to-cyan-600 hover:from-indigo-500 hover:to-cyan-500 text-white font-bold text-xs flex items-center gap-2 shadow-lg shadow-indigo-600/30"
          >
            {isLoading ? <Loader2 className="w-4 h-4 animate-spin" /> : <><Sparkles className="w-4 h-4" /> Search Vector Store</>}
          </button>
        </form>

        {/* Results Container */}
        {isLoading ? (
          <div className="p-12 text-center text-slate-400 text-xs flex flex-col items-center gap-2">
            <Loader2 className="w-6 h-6 animate-spin text-indigo-500" />
            <span>Calculating vector embeddings & performing similarity search...</span>
          </div>
        ) : hasSearched && results.length === 0 ? (
          <div className="glass-panel p-8 rounded-2xl text-center border border-slate-800">
            <FileText className="w-8 h-8 text-slate-500 mx-auto mb-2" />
            <p className="font-bold text-white text-sm">No matching document chunks found</p>
            <p className="text-xs text-slate-400 mt-1">Try refining your search keywords or upload additional reference documents.</p>
          </div>
        ) : (
          <div className="space-y-4">
            {results.map((r, idx) => (
              <div key={idx} className="glass-card p-5 rounded-2xl border border-slate-800 hover:border-indigo-500/30 transition-all">
                <div className="flex items-center justify-between gap-3 mb-2">
                  <div className="flex items-center gap-2">
                    <FileText className="w-4 h-4 text-indigo-400" />
                    <span className="font-bold text-white text-sm">{r.document_title}</span>
                    <span className="text-[11px] px-2 py-0.5 rounded bg-slate-800 text-slate-300 border border-slate-700">
                      Page {r.page_number}
                    </span>
                  </div>
                  <span className="text-[10px] font-bold px-2 py-0.5 rounded bg-emerald-500/20 text-emerald-300 border border-emerald-500/30">
                    {(r.score * 100).toFixed(1)}% Match
                  </span>
                </div>
                <p className="text-xs text-slate-300 leading-relaxed bg-slate-950/60 p-3 rounded-xl border border-slate-900 font-mono">
                  "{r.content}"
                </p>
              </div>
            ))}
          </div>
        )}
      </main>
    </div>
  );
};
