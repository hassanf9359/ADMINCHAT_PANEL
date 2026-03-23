import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  Film,
  Loader2,
  Check,
  X,
  ExternalLink,
  Clock,
  CheckCircle,
  XCircle,
  BarChart3,
} from 'lucide-react';
import Header from '../components/layout/Header';
import {
  getMovieRequests,
  getMovieRequestStats,
  updateMovieRequest,
} from '../services/movieRequestApi';
import type { MovieRequest } from '../types';

const STATUS_TABS = ['all', 'pending', 'fulfilled', 'rejected'] as const;
type StatusTab = typeof STATUS_TABS[number];

function StatCard({
  label,
  value,
  icon,
  iconBg,
}: {
  label: string;
  value: number;
  icon: React.ReactNode;
  iconBg: string;
}) {
  return (
    <div className="bg-[#0A0A0A] border border-[#2f2f2f] rounded-[10px] p-5">
      <div className="flex items-center justify-between mb-3">
        <span className="text-[11px] font-semibold text-[#6a6a6a] uppercase tracking-[0.5px] font-['JetBrains_Mono']">
          {label}
        </span>
        <div className={`p-1.5 rounded-md ${iconBg}`}>{icon}</div>
      </div>
      <p className="text-2xl font-bold text-white font-['Space_Grotesk']">{value}</p>
    </div>
  );
}

function StatusBadge({ status }: { status: string }) {
  const config: Record<string, { bg: string; text: string; label: string }> = {
    pending: { bg: 'bg-[#FF8800]/10', text: 'text-[#FF8800]', label: 'PENDING' },
    fulfilled: { bg: 'bg-[#059669]/10', text: 'text-[#059669]', label: 'FULFILLED' },
    rejected: { bg: 'bg-[#FF4444]/10', text: 'text-[#FF4444]', label: 'REJECTED' },
  };
  const c = config[status] || config.pending;
  return (
    <span
      className={`text-[10px] font-semibold font-['JetBrains_Mono'] px-2 py-0.5 rounded ${c.bg} ${c.text}`}
    >
      {c.label}
    </span>
  );
}

function MediaTypeBadge({ type }: { type: string }) {
  return (
    <span className="text-[10px] font-semibold font-['JetBrains_Mono'] px-2 py-0.5 rounded bg-[#8B5CF6]/10 text-[#8B5CF6]">
      {type.toUpperCase()}
    </span>
  );
}

export default function MovieRequests() {
  const queryClient = useQueryClient();
  const [activeTab, setActiveTab] = useState<StatusTab>('all');
  const [page, setPage] = useState(1);

  const { data: stats } = useQuery({
    queryKey: ['movie-request-stats'],
    queryFn: getMovieRequestStats,
    staleTime: 30_000,
  });

  const { data, isLoading } = useQuery({
    queryKey: ['movie-requests', activeTab, page],
    queryFn: () =>
      getMovieRequests({
        page,
        page_size: 20,
        status: activeTab === 'all' ? undefined : activeTab,
      }),
    staleTime: 15_000,
  });

  const mutation = useMutation({
    mutationFn: ({ id, status }: { id: number; status: string }) =>
      updateMovieRequest(id, { status }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['movie-requests'] });
      queryClient.invalidateQueries({ queryKey: ['movie-request-stats'] });
    },
  });

  const items = data?.items || [];
  const total = data?.total || 0;
  const totalPages = data?.total_pages || 0;

  return (
    <div className="flex flex-col h-full">
      <Header title="Movie Requests" />
      <div className="flex-1 px-8 py-6 overflow-auto">
        {/* Stats cards */}
        <div className="grid grid-cols-4 gap-4 mb-8">
          <StatCard
            label="Total"
            value={stats?.total ?? 0}
            icon={<BarChart3 size={16} className="text-[#00D9FF]" />}
            iconBg="bg-[#00D9FF]/10"
          />
          <StatCard
            label="Pending"
            value={stats?.pending ?? 0}
            icon={<Clock size={16} className="text-[#FF8800]" />}
            iconBg="bg-[#FF8800]/10"
          />
          <StatCard
            label="Fulfilled"
            value={stats?.fulfilled ?? 0}
            icon={<CheckCircle size={16} className="text-[#059669]" />}
            iconBg="bg-[#059669]/10"
          />
          <StatCard
            label="Rejected"
            value={stats?.rejected ?? 0}
            icon={<XCircle size={16} className="text-[#FF4444]" />}
            iconBg="bg-[#FF4444]/10"
          />
        </div>

        {/* Status filter tabs */}
        <div className="flex items-center gap-6 mb-6 border-b border-[#1A1A1A]">
          {STATUS_TABS.map((tab) => (
            <button
              key={tab}
              onClick={() => {
                setActiveTab(tab);
                setPage(1);
              }}
              className={`pb-3 text-sm font-medium transition-colors relative capitalize ${
                activeTab === tab
                  ? 'text-[#00D9FF]'
                  : 'text-[#6a6a6a] hover:text-white'
              }`}
            >
              {tab}
              {activeTab === tab && (
                <div className="absolute bottom-0 left-0 right-0 h-0.5 bg-[#00D9FF]" />
              )}
            </button>
          ))}
        </div>

        {/* Table */}
        <div className="bg-[#0A0A0A] border border-[#2f2f2f] rounded-[10px] overflow-hidden">
          <table className="w-full">
            <thead>
              <tr className="border-b border-[#2f2f2f]">
                <th className="text-left text-[11px] font-semibold text-[#6a6a6a] uppercase tracking-[0.5px] font-['JetBrains_Mono'] px-5 py-3 w-16">
                  Poster
                </th>
                <th className="text-left text-[11px] font-semibold text-[#6a6a6a] uppercase tracking-[0.5px] font-['JetBrains_Mono'] px-5 py-3">
                  Title
                </th>
                <th className="text-left text-[11px] font-semibold text-[#6a6a6a] uppercase tracking-[0.5px] font-['JetBrains_Mono'] px-5 py-3">
                  TMDB
                </th>
                <th className="text-center text-[11px] font-semibold text-[#6a6a6a] uppercase tracking-[0.5px] font-['JetBrains_Mono'] px-5 py-3">
                  Rating
                </th>
                <th className="text-center text-[11px] font-semibold text-[#6a6a6a] uppercase tracking-[0.5px] font-['JetBrains_Mono'] px-5 py-3">
                  Requests
                </th>
                <th className="text-center text-[11px] font-semibold text-[#6a6a6a] uppercase tracking-[0.5px] font-['JetBrains_Mono'] px-5 py-3">
                  Library
                </th>
                <th className="text-center text-[11px] font-semibold text-[#6a6a6a] uppercase tracking-[0.5px] font-['JetBrains_Mono'] px-5 py-3">
                  Status
                </th>
                <th className="text-right text-[11px] font-semibold text-[#6a6a6a] uppercase tracking-[0.5px] font-['JetBrains_Mono'] px-5 py-3">
                  Actions
                </th>
              </tr>
            </thead>
            <tbody>
              {isLoading ? (
                <tr>
                  <td colSpan={8} className="text-center py-12">
                    <Loader2 className="w-6 h-6 text-[#6a6a6a] animate-spin mx-auto" />
                  </td>
                </tr>
              ) : items.length === 0 ? (
                <tr>
                  <td colSpan={8} className="text-center py-12 text-[#6a6a6a] text-sm">
                    No requests found
                  </td>
                </tr>
              ) : (
                items.map((req: MovieRequest) => {
                  const year = req.release_date?.slice(0, 4) || 'N/A';
                  const tmdbUrl =
                    req.media_type === 'movie'
                      ? `https://www.themoviedb.org/movie/${req.tmdb_id}`
                      : `https://www.themoviedb.org/tv/${req.tmdb_id}`;
                  return (
                    <tr key={req.id} className="border-b border-[#1A1A1A] hover:bg-[#141414]/50">
                      {/* Poster */}
                      <td className="px-5 py-3">
                        {req.poster_path ? (
                          <img
                            src={`https://image.tmdb.org/t/p/w92${req.poster_path}`}
                            alt={req.title}
                            className="w-10 h-14 object-cover rounded"
                          />
                        ) : (
                          <div className="w-10 h-14 bg-[#141414] rounded flex items-center justify-center">
                            <Film size={16} className="text-[#4a4a4a]" />
                          </div>
                        )}
                      </td>
                      {/* Title + year + type */}
                      <td className="px-5 py-3">
                        <div className="flex flex-col gap-1">
                          <span className="text-sm text-white font-medium truncate max-w-[240px]">
                            {req.title}
                          </span>
                          <div className="flex items-center gap-2">
                            <span className="text-xs text-[#6a6a6a]">{year}</span>
                            <MediaTypeBadge type={req.media_type} />
                          </div>
                        </div>
                      </td>
                      {/* TMDB link */}
                      <td className="px-5 py-3">
                        <a
                          href={tmdbUrl}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="inline-flex items-center gap-1 text-xs text-[#00D9FF] hover:underline font-['JetBrains_Mono']"
                        >
                          {req.tmdb_id}
                          <ExternalLink size={10} />
                        </a>
                      </td>
                      {/* Rating */}
                      <td className="px-5 py-3 text-center">
                        <span className="text-sm text-white font-['JetBrains_Mono']">
                          {req.vote_average != null ? `⭐ ${Number(req.vote_average).toFixed(1)}` : '—'}
                        </span>
                      </td>
                      {/* Request count */}
                      <td className="px-5 py-3 text-center">
                        <span className="text-sm text-white font-['JetBrains_Mono']">
                          {req.request_count}
                        </span>
                      </td>
                      {/* In library */}
                      <td className="px-5 py-3 text-center">
                        {req.in_library ? (
                          <span className="text-[10px] font-semibold font-['JetBrains_Mono'] px-2 py-0.5 rounded bg-[#059669]/10 text-[#059669]">
                            YES
                          </span>
                        ) : (
                          <span className="text-[10px] font-semibold font-['JetBrains_Mono'] px-2 py-0.5 rounded bg-[#141414] text-[#6a6a6a]">
                            NO
                          </span>
                        )}
                      </td>
                      {/* Status */}
                      <td className="px-5 py-3 text-center">
                        <StatusBadge status={req.status} />
                      </td>
                      {/* Actions */}
                      <td className="px-5 py-3 text-right">
                        {req.status === 'pending' && (
                          <div className="flex items-center gap-2 justify-end">
                            <button
                              onClick={() => mutation.mutate({ id: req.id, status: 'fulfilled' })}
                              disabled={mutation.isPending}
                              className="p-1.5 rounded-md hover:bg-[#059669]/10 text-[#6a6a6a] hover:text-[#059669] transition-colors"
                              title="Fulfill"
                            >
                              <Check size={16} />
                            </button>
                            <button
                              onClick={() => mutation.mutate({ id: req.id, status: 'rejected' })}
                              disabled={mutation.isPending}
                              className="p-1.5 rounded-md hover:bg-[#FF4444]/10 text-[#6a6a6a] hover:text-[#FF4444] transition-colors"
                              title="Reject"
                            >
                              <X size={16} />
                            </button>
                          </div>
                        )}
                      </td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </div>

        {/* Pagination */}
        {totalPages > 1 && (
          <div className="flex items-center justify-between mt-4">
            <span className="text-xs text-[#6a6a6a]">
              {total} total results
            </span>
            <div className="flex items-center gap-2">
              <button
                onClick={() => setPage((p) => Math.max(1, p - 1))}
                disabled={page <= 1}
                className="px-3 py-1.5 rounded-md text-xs font-medium text-[#8a8a8a] border border-[#2f2f2f] hover:bg-[#141414] transition-colors disabled:opacity-30"
              >
                Previous
              </button>
              <span className="text-xs text-[#8a8a8a] font-['JetBrains_Mono']">
                {page} / {totalPages}
              </span>
              <button
                onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                disabled={page >= totalPages}
                className="px-3 py-1.5 rounded-md text-xs font-medium text-[#8a8a8a] border border-[#2f2f2f] hover:bg-[#141414] transition-colors disabled:opacity-30"
              >
                Next
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
