import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Plus, Trash2, AlertTriangle, Clock, Filter, Search } from 'lucide-react';
import Header from '../components/layout/Header';
import {
  getMissedKeywords,
  deleteMissedKeyword,
  getMissedKeywordFilters,
  createMissedKeywordFilter,
  deleteMissedKeywordFilter,
} from '../services/faqApi';
type FilterMatchMode = 'exact' | 'prefix' | 'contains' | 'regex';

function formatDate(dateStr: string): string {
  const d = new Date(dateStr);
  return d.toLocaleDateString('en-US', {
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });
}

function timeAgo(dateStr: string): string {
  const d = new Date(dateStr);
  const now = new Date();
  const diffMs = now.getTime() - d.getTime();
  const diffMins = Math.floor(diffMs / 60000);
  if (diffMins < 60) return `${diffMins}m ago`;
  const diffHours = Math.floor(diffMins / 60);
  if (diffHours < 24) return `${diffHours}h ago`;
  const diffDays = Math.floor(diffHours / 24);
  return `${diffDays}d ago`;
}

const MATCH_MODE_COLORS: Record<string, string> = {
  exact: '#059669',
  prefix: '#8B5CF6',
  contains: '#00D9FF',
  regex: '#FF8800',
};

const TABS = [
  { key: 'keywords', label: 'Missed Keywords', icon: Search },
  { key: 'filters', label: 'Keyword Filters', icon: Filter },
] as const;

type TabKey = typeof TABS[number]['key'];

export default function MissedKnowledge() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();

  const [activeTab, setActiveTab] = useState<TabKey>('keywords');
  const [newPattern, setNewPattern] = useState('');
  const [newMatchMode, setNewMatchMode] = useState<FilterMatchMode>('exact');
  const [newDescription, setNewDescription] = useState('');

  const { data: keywords = [], isLoading, dataUpdatedAt } = useQuery({
    queryKey: ['missed-keywords'],
    queryFn: getMissedKeywords,
  });

  const { data: filters = [], isLoading: filtersLoading } = useQuery({
    queryKey: ['missed-keyword-filters'],
    queryFn: getMissedKeywordFilters,
  });

  const resolveMutation = useMutation({
    mutationFn: (id: number) => deleteMissedKeyword(id),
    onSuccess: () =>
      queryClient.invalidateQueries({ queryKey: ['missed-keywords'] }),
  });

  const createFilterMutation = useMutation({
    mutationFn: createMissedKeywordFilter,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['missed-keyword-filters'] });
      queryClient.invalidateQueries({ queryKey: ['missed-keywords'] });
      setNewPattern('');
      setNewMatchMode('exact');
      setNewDescription('');
    },
  });

  const deleteFilterMutation = useMutation({
    mutationFn: deleteMissedKeywordFilter,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['missed-keyword-filters'] });
      queryClient.invalidateQueries({ queryKey: ['missed-keywords'] });
    },
  });

  const handleCreateFAQ = (keyword: string) => {
    navigate(`/faq/new?keyword=${encodeURIComponent(keyword)}`);
  };

  const handleDelete = (id: number, keyword: string) => {
    if (window.confirm(`Mark "${keyword}" as resolved?`)) {
      resolveMutation.mutate(id);
    }
  };

  const handleAddFilter = () => {
    if (!newPattern.trim()) return;
    createFilterMutation.mutate({
      pattern: newPattern.trim(),
      match_mode: newMatchMode,
      description: newDescription.trim() || undefined,
    });
  };

  const handleDeleteFilter = (id: number, pattern: string) => {
    if (window.confirm(`Delete filter "${pattern}"?`)) {
      deleteFilterMutation.mutate(id);
    }
  };

  return (
    <div className="flex flex-col h-full">
      <Header title="Missed Knowledge" />
      <div className="flex-1 p-8 overflow-auto">
        {/* Tabs */}
        <div className="flex items-center gap-1 mb-6 border-b border-border-subtle">
          {TABS.map((tab) => {
            const Icon = tab.icon;
            const isActive = activeTab === tab.key;
            const count = tab.key === 'filters' ? filters.length : keywords.length;
            return (
              <button
                key={tab.key}
                onClick={() => setActiveTab(tab.key)}
                className={`flex items-center gap-2 px-4 py-3 text-sm font-medium border-b-2 transition-colors ${
                  isActive
                    ? 'border-accent text-accent'
                    : 'border-transparent text-text-muted hover:text-text-secondary'
                }`}
              >
                <Icon size={14} />
                {tab.label}
                {count > 0 && (
                  <span className={`px-1.5 py-0.5 rounded text-[10px] font-mono ${
                    isActive ? 'bg-accent/10 text-accent' : 'bg-bg-elevated text-text-muted'
                  }`}>
                    {count}
                  </span>
                )}
              </button>
            );
          })}

          {activeTab === 'keywords' && dataUpdatedAt > 0 && (
            <div className="ml-auto flex items-center gap-1 text-text-muted text-xs">
              <Clock size={12} />
              <span>Updated {timeAgo(new Date(dataUpdatedAt).toISOString())}</span>
            </div>
          )}
        </div>

        {/* ---- Tab: Missed Keywords ---- */}
        {activeTab === 'keywords' && (
          <>
            <div className="flex items-center gap-2 mb-4">
              <AlertTriangle size={16} className="text-orange" />
              <p className="text-text-secondary text-xs">
                Keywords from unmatched user messages. Create FAQ rules to cover these topics.
              </p>
            </div>

            <div className="bg-bg-card border border-border-subtle rounded-xl overflow-hidden">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-border-subtle">
                    <th className="text-left px-6 py-4 text-xs font-semibold text-text-muted uppercase tracking-wider font-['JetBrains_Mono']">Keyword</th>
                    <th className="text-center px-6 py-4 text-xs font-semibold text-text-muted uppercase tracking-wider font-['JetBrains_Mono']">Occurrences</th>
                    <th className="text-left px-6 py-4 text-xs font-semibold text-text-muted uppercase tracking-wider font-['JetBrains_Mono']">Sample Messages</th>
                    <th className="text-center px-6 py-4 text-xs font-semibold text-text-muted uppercase tracking-wider font-['JetBrains_Mono']">Last Seen</th>
                    <th className="text-right px-6 py-4 text-xs font-semibold text-text-muted uppercase tracking-wider font-['JetBrains_Mono']">Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {isLoading ? (
                    <tr><td colSpan={5} className="px-4 py-8 text-center text-text-muted">Loading...</td></tr>
                  ) : keywords.length === 0 ? (
                    <tr><td colSpan={5} className="px-4 py-8 text-center text-text-muted">No missed keywords found. Your FAQ coverage looks good!</td></tr>
                  ) : (
                    keywords.map((kw) => (
                      <tr key={kw.id} className="border-b border-border-subtle/50 last:border-0 hover:bg-bg-elevated/50 transition-colors">
                        <td className="px-6 py-4.5">
                          <span className="inline-block px-2 py-1 rounded-md bg-orange/10 text-orange text-sm font-medium">{kw.keyword}</span>
                        </td>
                        <td className="px-6 py-4.5 text-center">
                          <span className="font-mono text-accent font-medium">{kw.occurrence_count}</span>
                        </td>
                        <td className="px-6 py-4.5 text-text-secondary text-xs max-w-[300px]">
                          {kw.sample_messages && kw.sample_messages.length > 0 ? (
                            <div className="space-y-1">
                              {kw.sample_messages.slice(0, 3).map((msg, idx) => (
                                <div key={idx} className="truncate text-text-muted" title={msg}>"{msg}"</div>
                              ))}
                              {kw.sample_messages.length > 3 && (
                                <span className="text-text-placeholder">+{kw.sample_messages.length - 3} more</span>
                              )}
                            </div>
                          ) : (
                            <span className="text-text-placeholder">-</span>
                          )}
                        </td>
                        <td className="px-6 py-4.5 text-center text-text-secondary text-xs">{formatDate(kw.last_seen_at)}</td>
                        <td className="px-6 py-4.5 text-right">
                          <div className="flex items-center justify-end gap-1">
                            <button
                              onClick={() => handleCreateFAQ(kw.keyword)}
                              className="flex items-center gap-1 px-2.5 py-1.5 rounded-md text-xs font-medium bg-accent/10 text-accent hover:bg-accent/20 transition-colors"
                            >
                              <Plus size={12} />
                              Create FAQ
                            </button>
                            <button
                              onClick={() => handleDelete(kw.id, kw.keyword)}
                              className="p-1.5 rounded hover:bg-bg-elevated text-text-secondary hover:text-red transition-colors"
                              title="Mark as resolved"
                            >
                              <Trash2 size={14} />
                            </button>
                          </div>
                        </td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>
          </>
        )}

        {/* ---- Tab: Keyword Filters ---- */}
        {activeTab === 'filters' && (
          <>
            <div className="flex items-center gap-2 mb-4">
              <Filter size={16} className="text-purple" />
              <p className="text-text-secondary text-xs">
                Filter patterns to automatically skip irrelevant keywords (e.g. bot commands like /start, /help).
              </p>
            </div>

            {/* Add filter form */}
            <div className="bg-bg-card border border-border-subtle rounded-xl p-5 mb-6">
              <h3 className="text-xs font-semibold text-text-muted uppercase tracking-wider mb-3">Add New Filter</h3>
              <div className="flex items-center gap-2">
                <input
                  type="text"
                  placeholder="Pattern (e.g. /start)"
                  value={newPattern}
                  onChange={(e) => setNewPattern(e.target.value)}
                  onKeyDown={(e) => e.key === 'Enter' && handleAddFilter()}
                  className="flex-1 min-w-0 px-3 py-2 rounded-md bg-bg-elevated border border-border text-sm text-text-primary placeholder-text-placeholder focus:outline-none focus:border-accent font-['JetBrains_Mono']"
                />
                <select
                  value={newMatchMode}
                  onChange={(e) => setNewMatchMode(e.target.value as FilterMatchMode)}
                  className="px-3 py-2 rounded-md bg-bg-elevated border border-border text-sm text-text-primary focus:outline-none focus:border-accent"
                >
                  <option value="exact">Exact</option>
                  <option value="prefix">Prefix</option>
                  <option value="contains">Contains</option>
                  <option value="regex">Regex</option>
                </select>
                <input
                  type="text"
                  placeholder="Description (optional)"
                  value={newDescription}
                  onChange={(e) => setNewDescription(e.target.value)}
                  onKeyDown={(e) => e.key === 'Enter' && handleAddFilter()}
                  className="w-56 px-3 py-2 rounded-md bg-bg-elevated border border-border text-sm text-text-primary placeholder-text-placeholder focus:outline-none focus:border-accent"
                />
                <button
                  onClick={handleAddFilter}
                  disabled={!newPattern.trim() || createFilterMutation.isPending}
                  className="flex items-center gap-1 px-4 py-2 rounded-md text-xs font-medium bg-accent/10 text-accent hover:bg-accent/20 transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
                >
                  <Plus size={14} />
                  Add Filter
                </button>
              </div>
              {createFilterMutation.isError && (
                <p className="text-xs text-red mt-2">
                  {(createFilterMutation.error as Error)?.message || 'Failed to create filter'}
                </p>
              )}
            </div>

            {/* Filter list */}
            <div className="bg-bg-card border border-border-subtle rounded-xl overflow-hidden">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-border-subtle">
                    <th className="text-left px-6 py-4 text-xs font-semibold text-text-muted uppercase tracking-wider font-['JetBrains_Mono']">Pattern</th>
                    <th className="text-left px-6 py-4 text-xs font-semibold text-text-muted uppercase tracking-wider font-['JetBrains_Mono']">Match Mode</th>
                    <th className="text-left px-6 py-4 text-xs font-semibold text-text-muted uppercase tracking-wider font-['JetBrains_Mono']">Description</th>
                    <th className="text-center px-6 py-4 text-xs font-semibold text-text-muted uppercase tracking-wider font-['JetBrains_Mono']">Created</th>
                    <th className="text-right px-6 py-4 text-xs font-semibold text-text-muted uppercase tracking-wider font-['JetBrains_Mono']">Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {filtersLoading ? (
                    <tr><td colSpan={5} className="px-4 py-8 text-center text-text-muted">Loading...</td></tr>
                  ) : filters.length === 0 ? (
                    <tr>
                      <td colSpan={5} className="px-4 py-12 text-center">
                        <Filter size={24} className="text-text-placeholder mx-auto mb-2" />
                        <p className="text-text-muted text-sm">No filters configured.</p>
                        <p className="text-text-placeholder text-xs mt-1">Add patterns above to auto-skip irrelevant keywords like /start, /help.</p>
                      </td>
                    </tr>
                  ) : (
                    filters.map((f) => (
                      <tr key={f.id} className="border-b border-border-subtle/50 last:border-0 hover:bg-bg-elevated/50 transition-colors">
                        <td className="px-6 py-4.5">
                          <span className="font-['JetBrains_Mono'] text-sm text-text-primary bg-bg-elevated px-2 py-1 rounded-md">
                            {f.pattern}
                          </span>
                        </td>
                        <td className="px-6 py-4.5">
                          <span
                            className="px-2 py-0.5 rounded-md text-[10px] font-semibold uppercase tracking-wide"
                            style={{
                              color: MATCH_MODE_COLORS[f.match_mode] || '#8a8a8a',
                              backgroundColor: `${MATCH_MODE_COLORS[f.match_mode] || '#8a8a8a'}1a`,
                            }}
                          >
                            {f.match_mode}
                          </span>
                        </td>
                        <td className="px-6 py-4.5 text-text-muted text-xs">{f.description || '—'}</td>
                        <td className="px-6 py-4.5 text-center text-text-secondary text-xs">{formatDate(f.created_at)}</td>
                        <td className="px-6 py-4.5 text-right">
                          <button
                            onClick={() => handleDeleteFilter(f.id, f.pattern)}
                            className="p-1.5 rounded hover:bg-bg-elevated text-text-secondary hover:text-red transition-colors"
                            title="Delete filter"
                          >
                            <Trash2 size={14} />
                          </button>
                        </td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
