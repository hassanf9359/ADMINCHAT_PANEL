import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Plus, X, Users, ChevronDown, ChevronRight } from 'lucide-react';
import Header from '../components/layout/Header';
import {
  getBots, createBot, updateBot, deleteBot, restartBot,
  getBotGroups, createBotGroup, deleteBotGroup, setBotGroupMembers,
  type BotCreateData, type BotUpdateData, type BotGroupCreateData,
} from '../services/botApi';
import type { Bot, BotGroup } from '../types';

// ---- Status badge component ----
function StatusBadge({ status }: { status: string }) {
  const map: Record<string, { label: string; dotColor: string; textColor: string; bgColor: string }> = {
    online: { label: 'ONLINE', dotColor: 'bg-[#059669]', textColor: 'text-[#059669]', bgColor: 'bg-[#059669]/10' },
    rate_limited: { label: 'LIMITED', dotColor: 'bg-[#FF8800]', textColor: 'text-[#FF8800]', bgColor: 'bg-[#FF8800]/10' },
    offline: { label: 'OFFLINE', dotColor: 'bg-[#FF4444]', textColor: 'text-[#FF4444]', bgColor: 'bg-[#FF4444]/10' },
    error: { label: 'ERROR', dotColor: 'bg-[#FF4444]', textColor: 'text-[#FF4444]', bgColor: 'bg-[#FF4444]/10' },
  };
  const s = map[status] || map.offline;
  return (
    <span className={`inline-flex items-center gap-1.5 px-2 py-0.5 rounded text-[10px] font-semibold font-['JetBrains_Mono'] ${s.textColor} ${s.bgColor}`}>
      <span className={`w-1.5 h-1.5 rounded-full ${s.dotColor}`} />
      {s.label}
    </span>
  );
}

// ---- Priority bar ----
function PriorityBar({ value, max = 10 }: { value: number; max?: number }) {
  const pct = Math.min((value / max) * 100, 100);
  const color = pct > 60 ? 'bg-[#059669]' : pct > 30 ? 'bg-[#FF8800]' : 'bg-[#FF4444]';
  return (
    <div className="flex items-center gap-2">
      <div className="w-20 h-1.5 rounded-full bg-[#141414] overflow-hidden">
        <div className={`h-full rounded-full ${color} transition-all`} style={{ width: `${pct}%` }} />
      </div>
      <span className="text-xs text-[#8a8a8a] font-['JetBrains_Mono']">{value}</span>
    </div>
  );
}

// ---- Bot row ----
function BotRow({ bot, onEdit, onRestart, onDelete }: { bot: Bot; onEdit: (b: Bot) => void; onRestart: (id: number) => void; onDelete: (id: number) => void }) {
  return (
    <tr className="border-b border-[#1A1A1A] hover:bg-[#141414]/30 transition-colors">
      <td className="px-5 py-3.5">
        <StatusBadge status={bot.status} />
      </td>
      <td className="px-5 py-3.5">
        <span className="text-[14px] text-white font-medium">{bot.name}</span>
        {bot.bot_group_name && (
          <span className="ml-2 px-1.5 py-0.5 rounded text-[10px] font-['JetBrains_Mono'] text-[#8B5CF6] bg-[#8B5CF6]/10">
            {bot.bot_group_name}
          </span>
        )}
      </td>
      <td className="px-5 py-3.5">
        <span className="text-[13px] text-[#00D9FF] font-['JetBrains_Mono']">{bot.username}</span>
      </td>
      <td className="px-5 py-3.5">
        <PriorityBar value={bot.priority} />
      </td>
      <td className="px-5 py-3.5">
        <span className="text-sm text-[#8a8a8a] font-['JetBrains_Mono']">{bot.message_count}</span>
      </td>
      <td className="px-5 py-3.5">
        <div className="flex items-center justify-end gap-2">
          <button
            onClick={() => onEdit(bot)}
            className="px-3 py-1 rounded-md text-xs font-medium text-[#8a8a8a] border border-[#2f2f2f] hover:bg-[#141414] hover:text-white transition-colors"
          >
            Edit
          </button>
          <button
            onClick={() => onRestart(bot.id)}
            disabled={!bot.is_active}
            className="px-3 py-1 rounded-md text-xs font-medium text-[#8a8a8a] border border-[#2f2f2f] hover:bg-[#141414] hover:text-white transition-colors disabled:opacity-30"
          >
            Restart
          </button>
          <button
            onClick={() => onDelete(bot.id)}
            className="px-3 py-1 rounded-md text-xs font-medium text-[#FF4444] border border-[#FF4444]/30 hover:bg-[#FF4444]/10 transition-colors"
          >
            Delete
          </button>
        </div>
      </td>
    </tr>
  );
}

export default function BotPool() {
  const queryClient = useQueryClient();
  const [showAddForm, setShowAddForm] = useState(false);
  const [editingBot, setEditingBot] = useState<Bot | null>(null);
  const [deleteConfirm, setDeleteConfirm] = useState<number | null>(null);
  const [showGroupForm, setShowGroupForm] = useState(false);
  const [expandedGroups, setExpandedGroups] = useState<Set<number>>(new Set());
  const [managingMembers, setManagingMembers] = useState<BotGroup | null>(null);
  const [memberBotIds, setMemberBotIds] = useState<number[]>([]);

  // Form state
  const [formToken, setFormToken] = useState('');
  const [formName, setFormName] = useState('');
  const [formPriority, setFormPriority] = useState(0);

  // Edit form state
  const [editName, setEditName] = useState('');
  const [editPriority, setEditPriority] = useState(0);

  // Group form state
  const [groupName, setGroupName] = useState('');
  const [groupDesc, setGroupDesc] = useState('');

  const { data, isLoading } = useQuery({
    queryKey: ['bots'],
    queryFn: getBots,
    refetchInterval: 15000,
    staleTime: 10_000,
  });

  const { data: botGroups = [] } = useQuery({
    queryKey: ['bot-groups'],
    queryFn: getBotGroups,
    staleTime: 30_000,
  });

  const createMutation = useMutation({
    mutationFn: (body: BotCreateData) => createBot(body),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['bots'] });
      setShowAddForm(false);
      setFormToken('');
      setFormName('');
      setFormPriority(0);
    },
  });

  const updateMutation = useMutation({
    mutationFn: ({ id, body }: { id: number; body: BotUpdateData }) => updateBot(id, body),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['bots'] });
      setEditingBot(null);
    },
  });

  const deleteMutation = useMutation({
    mutationFn: (id: number) => deleteBot(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['bots'] });
      setDeleteConfirm(null);
    },
  });

  const restartMutation = useMutation({
    mutationFn: (id: number) => restartBot(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['bots'] }),
  });

  const createGroupMutation = useMutation({
    mutationFn: (body: BotGroupCreateData) => createBotGroup(body),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['bot-groups'] });
      setShowGroupForm(false);
      setGroupName('');
      setGroupDesc('');
    },
  });

  const deleteGroupMutation = useMutation({
    mutationFn: (id: number) => deleteBotGroup(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['bot-groups'] }),
  });

  const setMembersMutation = useMutation({
    mutationFn: ({ groupId, botIds }: { groupId: number; botIds: number[] }) =>
      setBotGroupMembers(groupId, botIds),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['bot-groups'] });
      queryClient.invalidateQueries({ queryKey: ['bots'] });
      setManagingMembers(null);
    },
  });

  const bots = data?.items || [];

  // Group bots by their bot_group_id
  const groupedBots = new Map<number, Bot[]>();
  const ungroupedBots: Bot[] = [];
  for (const bot of bots) {
    if (bot.bot_group_id) {
      const list = groupedBots.get(bot.bot_group_id) || [];
      list.push(bot);
      groupedBots.set(bot.bot_group_id, list);
    } else {
      ungroupedBots.push(bot);
    }
  }

  const toggleGroup = (id: number) => {
    setExpandedGroups(prev => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const handleAddSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!formToken.trim()) return;
    createMutation.mutate({
      token: formToken.trim(),
      display_name: formName.trim() || undefined,
      priority: formPriority,
    });
  };

  const handleEditSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!editingBot) return;
    updateMutation.mutate({
      id: editingBot.id,
      body: {
        display_name: editName.trim() || undefined,
        priority: editPriority,
      },
    });
  };

  const startEdit = (bot: Bot) => {
    setEditingBot(bot);
    setEditName(bot.name || '');
    setEditPriority(bot.priority);
  };

  const startManageMembers = (group: BotGroup) => {
    setManagingMembers(group);
    setMemberBotIds(group.members.map(m => m.bot_id));
  };

  const toggleMemberBot = (botId: number) => {
    setMemberBotIds(prev =>
      prev.includes(botId) ? prev.filter(id => id !== botId) : [...prev, botId]
    );
  };

  const tableHeader = (
    <thead>
      <tr className="border-b border-[#2f2f2f]">
        <th className="text-left text-[11px] font-semibold text-[#6a6a6a] uppercase tracking-[0.5px] font-['JetBrains_Mono'] px-5 py-3">Status</th>
        <th className="text-left text-[11px] font-semibold text-[#6a6a6a] uppercase tracking-[0.5px] font-['JetBrains_Mono'] px-5 py-3">Bot Name</th>
        <th className="text-left text-[11px] font-semibold text-[#6a6a6a] uppercase tracking-[0.5px] font-['JetBrains_Mono'] px-5 py-3">Username</th>
        <th className="text-left text-[11px] font-semibold text-[#6a6a6a] uppercase tracking-[0.5px] font-['JetBrains_Mono'] px-5 py-3">Priority</th>
        <th className="text-left text-[11px] font-semibold text-[#6a6a6a] uppercase tracking-[0.5px] font-['JetBrains_Mono'] px-5 py-3">Msgs Today</th>
        <th className="text-right text-[11px] font-semibold text-[#6a6a6a] uppercase tracking-[0.5px] font-['JetBrains_Mono'] px-5 py-3">Actions</th>
      </tr>
    </thead>
  );

  return (
    <div className="flex flex-col h-full">
      <Header title="Bot Pool" />
      <div className="flex-1 px-8 py-6 overflow-auto">
        <div className="flex items-center justify-between mb-6">
          <p className="text-[#8a8a8a] text-sm">
            Manage your Telegram bots &middot; {bots.length} bot{bots.length !== 1 ? 's' : ''} &middot; {botGroups.length} group{botGroups.length !== 1 ? 's' : ''}
          </p>
          <div className="flex items-center gap-2">
            <button
              onClick={() => setShowGroupForm(!showGroupForm)}
              className="inline-flex items-center gap-2 px-4 py-2 text-sm font-medium text-[#8B5CF6] border border-[#8B5CF6]/30 rounded-lg hover:bg-[#8B5CF6]/10 transition-colors"
            >
              <Users className="w-4 h-4" /> New Group
            </button>
            <button
              onClick={() => setShowAddForm(!showAddForm)}
              className="inline-flex items-center gap-2 px-4 py-2 bg-[#00D9FF] text-black text-sm font-medium rounded-lg hover:opacity-90 transition-opacity"
            >
              <Plus className="w-4 h-4" /> Add Bot
            </button>
          </div>
        </div>

        {/* New Group form */}
        {showGroupForm && (
          <div className="mb-6 bg-[#0A0A0A] border border-[#8B5CF6]/30 rounded-[10px] p-5">
            <form
              onSubmit={(e) => {
                e.preventDefault();
                if (!groupName.trim()) return;
                createGroupMutation.mutate({ name: groupName.trim(), description: groupDesc.trim() || undefined });
              }}
              className="flex items-end gap-4"
            >
              <div className="flex-1">
                <label className="block text-[13px] font-medium text-[#8a8a8a] mb-2">Group Name *</label>
                <input
                  type="text"
                  value={groupName}
                  onChange={(e) => setGroupName(e.target.value)}
                  placeholder="e.g. Sales Team"
                  className="w-full h-10 px-3.5 bg-[#141414] border border-[#2f2f2f] rounded-lg text-sm text-white placeholder:text-[#4a4a4a] focus:outline-none focus:border-[#8B5CF6] transition-colors"
                  required
                />
              </div>
              <div className="flex-1">
                <label className="block text-[13px] font-medium text-[#8a8a8a] mb-2">Description</label>
                <input
                  type="text"
                  value={groupDesc}
                  onChange={(e) => setGroupDesc(e.target.value)}
                  placeholder="Optional description"
                  className="w-full h-10 px-3.5 bg-[#141414] border border-[#2f2f2f] rounded-lg text-sm text-white placeholder:text-[#4a4a4a] focus:outline-none focus:border-[#8B5CF6] transition-colors"
                />
              </div>
              <button
                type="submit"
                disabled={createGroupMutation.isPending}
                className="inline-flex items-center gap-2 h-10 px-4 bg-[#8B5CF6] text-white text-sm font-medium rounded-lg hover:opacity-90 transition-opacity disabled:opacity-50 shrink-0"
              >
                <Users className="w-4 h-4" />
                {createGroupMutation.isPending ? 'Creating...' : 'Create Group'}
              </button>
            </form>
          </div>
        )}

        {/* Add Bot form */}
        {showAddForm && (
          <div className="mb-6 bg-[#0A0A0A] border border-[#00D9FF30] rounded-[10px] p-5">
            <form onSubmit={handleAddSubmit} className="flex items-end gap-4">
              <div className="flex-1">
                <label className="block text-[13px] font-medium text-[#8a8a8a] mb-2 font-['Inter']">Bot Token *</label>
                <input
                  type="text"
                  value={formToken}
                  onChange={(e) => setFormToken(e.target.value)}
                  placeholder="123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11"
                  className="w-full h-10 px-3.5 bg-[#141414] border border-[#2f2f2f] rounded-lg text-sm text-white placeholder:text-[#4a4a4a] focus:outline-none focus:border-[#00D9FF] transition-colors font-['JetBrains_Mono']"
                  required
                />
              </div>
              <div className="w-48">
                <label className="block text-[13px] font-medium text-[#8a8a8a] mb-2 font-['Inter']">Display Name</label>
                <input
                  type="text"
                  value={formName}
                  onChange={(e) => setFormName(e.target.value)}
                  placeholder="My Support Bot"
                  className="w-full h-10 px-3.5 bg-[#141414] border border-[#2f2f2f] rounded-lg text-sm text-white placeholder:text-[#4a4a4a] focus:outline-none focus:border-[#00D9FF] transition-colors"
                />
              </div>
              <div className="w-28">
                <label className="block text-[13px] font-medium text-[#8a8a8a] mb-2 font-['Inter']">Priority</label>
                <input
                  type="number"
                  value={formPriority}
                  onChange={(e) => setFormPriority(Number(e.target.value))}
                  min={0}
                  max={10}
                  className="w-full h-10 px-3.5 bg-[#141414] border border-[#2f2f2f] rounded-lg text-sm text-white focus:outline-none focus:border-[#00D9FF] transition-colors font-['JetBrains_Mono']"
                />
              </div>
              <button
                type="submit"
                disabled={createMutation.isPending}
                className="inline-flex items-center gap-2 h-10 px-4 bg-[#00D9FF] text-black text-sm font-medium rounded-lg hover:opacity-90 transition-opacity disabled:opacity-50 shrink-0"
              >
                <Plus className="w-4 h-4" />
                {createMutation.isPending ? 'Adding...' : 'Add Bot'}
              </button>
            </form>
            {createMutation.isError && (
              <p className="text-xs text-[#FF4444] mt-3">
                Failed to add bot: {(createMutation.error as Error)?.message || 'Unknown error'}
              </p>
            )}
          </div>
        )}

        {/* Bot Groups */}
        {botGroups.map((group) => {
          const botsInGroup = groupedBots.get(group.id) || [];
          const expanded = expandedGroups.has(group.id);
          return (
            <div key={group.id} className="mb-4">
              <div
                className="flex items-center justify-between bg-[#0A0A0A] border border-[#8B5CF6]/20 rounded-t-[10px] px-5 py-3 cursor-pointer hover:bg-[#141414]/50 transition-colors"
                onClick={() => toggleGroup(group.id)}
              >
                <div className="flex items-center gap-3">
                  {expanded ? <ChevronDown className="w-4 h-4 text-[#8B5CF6]" /> : <ChevronRight className="w-4 h-4 text-[#8B5CF6]" />}
                  <Users className="w-4 h-4 text-[#8B5CF6]" />
                  <span className="text-sm font-semibold text-white">{group.name}</span>
                  <span className="text-xs text-[#6a6a6a]">{botsInGroup.length} bot{botsInGroup.length !== 1 ? 's' : ''}</span>
                  {group.description && (
                    <span className="text-xs text-[#4a4a4a] ml-2">&middot; {group.description}</span>
                  )}
                </div>
                <div className="flex items-center gap-2" onClick={(e) => e.stopPropagation()}>
                  <button
                    onClick={() => startManageMembers(group)}
                    className="px-2.5 py-1 rounded text-[11px] font-medium text-[#8B5CF6] border border-[#8B5CF6]/30 hover:bg-[#8B5CF6]/10 transition-colors"
                  >
                    Members
                  </button>
                  <button
                    onClick={() => {
                      if (window.confirm(`Delete bot group "${group.name}"? Bots will be ungrouped.`))
                        deleteGroupMutation.mutate(group.id);
                    }}
                    className="px-2.5 py-1 rounded text-[11px] font-medium text-[#FF4444] border border-[#FF4444]/30 hover:bg-[#FF4444]/10 transition-colors"
                  >
                    Delete
                  </button>
                </div>
              </div>
              {expanded && (
                <div className="bg-[#0A0A0A] border border-t-0 border-[#8B5CF6]/20 rounded-b-[10px] overflow-hidden">
                  <table className="w-full">
                    {tableHeader}
                    <tbody>
                      {botsInGroup.length === 0 ? (
                        <tr><td colSpan={6} className="text-center text-[#6a6a6a] text-sm py-8">No bots in this group. Click Members to add.</td></tr>
                      ) : (
                        botsInGroup.map(bot => (
                          <BotRow key={bot.id} bot={bot} onEdit={startEdit} onRestart={(id) => restartMutation.mutate(id)} onDelete={(id) => setDeleteConfirm(id)} />
                        ))
                      )}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          );
        })}

        {/* Ungrouped bots */}
        <div className="bg-[#0A0A0A] border border-[#2f2f2f] rounded-[10px] overflow-hidden">
          {botGroups.length > 0 && (
            <div className="px-5 py-3 border-b border-[#2f2f2f]">
              <span className="text-xs font-semibold text-[#6a6a6a] uppercase tracking-wider font-['JetBrains_Mono']">
                Ungrouped Bots
              </span>
            </div>
          )}
          <table className="w-full">
            {tableHeader}
            <tbody>
              {isLoading ? (
                <tr>
                  <td colSpan={6} className="text-center text-[#6a6a6a] text-sm py-12">Loading bots...</td>
                </tr>
              ) : ungroupedBots.length === 0 ? (
                <tr>
                  <td colSpan={6} className="text-center text-[#6a6a6a] text-sm py-12">
                    {bots.length === 0 ? 'No bots configured. Add one to get started.' : 'All bots are in groups.'}
                  </td>
                </tr>
              ) : (
                ungroupedBots.map(bot => (
                  <BotRow key={bot.id} bot={bot} onEdit={startEdit} onRestart={(id) => restartMutation.mutate(id)} onDelete={(id) => setDeleteConfirm(id)} />
                ))
              )}
            </tbody>
          </table>
        </div>

        {/* Edit bot modal */}
        {editingBot && (
          <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm">
            <div className="bg-[#0C0C0C] border border-[#2f2f2f] rounded-[10px] p-6 w-full max-w-md shadow-2xl">
              <div className="flex items-center justify-between mb-5">
                <h3 className="text-sm font-semibold text-white">Edit Bot</h3>
                <button onClick={() => setEditingBot(null)} className="text-[#6a6a6a] hover:text-white">
                  <X className="w-4 h-4" />
                </button>
              </div>
              <form onSubmit={handleEditSubmit} className="flex flex-col gap-4">
                <div>
                  <label className="block text-[13px] font-medium text-[#8a8a8a] mb-2">Display Name</label>
                  <input
                    type="text"
                    value={editName}
                    onChange={(e) => setEditName(e.target.value)}
                    className="w-full h-10 px-3.5 bg-[#141414] border border-[#2f2f2f] rounded-lg text-sm text-white focus:outline-none focus:border-[#00D9FF] transition-colors"
                  />
                </div>
                <div>
                  <label className="block text-[13px] font-medium text-[#8a8a8a] mb-2">Priority (0-10)</label>
                  <input
                    type="number"
                    value={editPriority}
                    onChange={(e) => setEditPriority(Number(e.target.value))}
                    min={0}
                    max={10}
                    className="w-full h-10 px-3.5 bg-[#141414] border border-[#2f2f2f] rounded-lg text-sm text-white focus:outline-none focus:border-[#00D9FF] transition-colors font-['JetBrains_Mono']"
                  />
                </div>
                <div className="flex justify-end gap-3 mt-2">
                  <button type="button" onClick={() => setEditingBot(null)} className="px-4 py-2 text-sm text-[#8a8a8a] hover:text-white">Cancel</button>
                  <button type="submit" disabled={updateMutation.isPending} className="px-4 py-2 bg-[#00D9FF] text-black text-sm font-medium rounded-lg hover:opacity-90 disabled:opacity-50">
                    {updateMutation.isPending ? 'Saving...' : 'Save Changes'}
                  </button>
                </div>
              </form>
            </div>
          </div>
        )}

        {/* Manage members modal */}
        {managingMembers && (
          <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm">
            <div className="bg-[#0C0C0C] border border-[#2f2f2f] rounded-[10px] p-6 w-full max-w-md shadow-2xl">
              <div className="flex items-center justify-between mb-5">
                <h3 className="text-sm font-semibold text-white">
                  Manage Members &mdash; {managingMembers.name}
                </h3>
                <button onClick={() => setManagingMembers(null)} className="text-[#6a6a6a] hover:text-white">
                  <X className="w-4 h-4" />
                </button>
              </div>
              <p className="text-xs text-[#8a8a8a] mb-4">
                Select bots to include in this group. Each bot can only belong to one group.
              </p>
              <div className="space-y-2 max-h-64 overflow-y-auto mb-4">
                {bots.map(bot => {
                  const inOtherGroup = bot.bot_group_id && bot.bot_group_id !== managingMembers.id;
                  const selected = memberBotIds.includes(bot.id);
                  return (
                    <label
                      key={bot.id}
                      className={`flex items-center gap-3 px-3 py-2.5 rounded-lg cursor-pointer transition-colors ${
                        selected ? 'bg-[#8B5CF6]/10 border border-[#8B5CF6]/30' : 'bg-[#141414] border border-[#2f2f2f]'
                      } ${inOtherGroup ? 'opacity-40 cursor-not-allowed' : 'hover:border-[#8B5CF6]/50'}`}
                    >
                      <input
                        type="checkbox"
                        checked={selected}
                        onChange={() => !inOtherGroup && toggleMemberBot(bot.id)}
                        disabled={!!inOtherGroup}
                        className="accent-[#8B5CF6]"
                      />
                      <div className="flex-1">
                        <span className="text-sm text-white">{bot.name}</span>
                        <span className="text-xs text-[#00D9FF] ml-2 font-['JetBrains_Mono']">{bot.username}</span>
                      </div>
                      {inOtherGroup && (
                        <span className="text-[10px] text-[#FF8800] font-['JetBrains_Mono']">
                          in {bot.bot_group_name}
                        </span>
                      )}
                    </label>
                  );
                })}
              </div>
              <div className="flex justify-end gap-3">
                <button onClick={() => setManagingMembers(null)} className="px-4 py-2 text-sm text-[#8a8a8a] hover:text-white">Cancel</button>
                <button
                  onClick={() => setMembersMutation.mutate({ groupId: managingMembers.id, botIds: memberBotIds })}
                  disabled={setMembersMutation.isPending}
                  className="px-4 py-2 bg-[#8B5CF6] text-white text-sm font-medium rounded-lg hover:opacity-90 disabled:opacity-50"
                >
                  {setMembersMutation.isPending ? 'Saving...' : 'Save Members'}
                </button>
              </div>
            </div>
          </div>
        )}

        {/* Delete confirmation */}
        {deleteConfirm !== null && (
          <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm">
            <div className="bg-[#0C0C0C] border border-[#2f2f2f] rounded-[10px] p-6 w-full max-w-sm shadow-2xl">
              <h3 className="text-sm font-semibold text-white mb-3">Delete Bot</h3>
              <p className="text-sm text-[#8a8a8a] mb-5">
                Are you sure you want to permanently delete this bot? This action cannot be undone.
              </p>
              <div className="flex justify-end gap-3">
                <button onClick={() => setDeleteConfirm(null)} className="px-4 py-2 text-sm text-[#8a8a8a] hover:text-white">Cancel</button>
                <button
                  onClick={() => deleteMutation.mutate(deleteConfirm)}
                  disabled={deleteMutation.isPending}
                  className="px-4 py-2 bg-[#FF4444] text-white text-sm font-medium rounded-lg hover:opacity-90 disabled:opacity-50"
                >
                  {deleteMutation.isPending ? 'Deleting...' : 'Delete'}
                </button>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
