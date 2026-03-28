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
    online: { label: 'ONLINE', dotColor: 'bg-green', textColor: 'text-green', bgColor: 'bg-green/10' },
    rate_limited: { label: 'LIMITED', dotColor: 'bg-orange', textColor: 'text-orange', bgColor: 'bg-orange/10' },
    offline: { label: 'OFFLINE', dotColor: 'bg-red', textColor: 'text-red', bgColor: 'bg-red/10' },
    error: { label: 'ERROR', dotColor: 'bg-red', textColor: 'text-red', bgColor: 'bg-red/10' },
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
  const color = pct > 60 ? 'bg-green' : pct > 30 ? 'bg-orange' : 'bg-red';
  return (
    <div className="flex items-center gap-2">
      <div className="w-20 h-1.5 rounded-full bg-bg-elevated overflow-hidden">
        <div className={`h-full rounded-full ${color} transition-all`} style={{ width: `${pct}%` }} />
      </div>
      <span className="text-xs text-text-secondary font-['JetBrains_Mono']">{value}</span>
    </div>
  );
}

// ---- Bot row ----
function BotRow({ bot, onEdit, onRestart, onDelete }: { bot: Bot; onEdit: (b: Bot) => void; onRestart: (id: number) => void; onDelete: (id: number) => void }) {
  return (
    <tr className="border-b border-border-subtle hover:bg-bg-elevated/30 transition-colors">
      <td className="px-5 py-3.5">
        <StatusBadge status={bot.status} />
      </td>
      <td className="px-5 py-3.5">
        <span className="text-[14px] text-text-primary font-medium">{bot.name}</span>
        {bot.bot_group_name && (
          <span className="ml-2 px-1.5 py-0.5 rounded text-[10px] font-['JetBrains_Mono'] text-purple bg-purple/10">
            {bot.bot_group_name}
          </span>
        )}
      </td>
      <td className="px-5 py-3.5">
        <span className="text-[13px] text-accent font-['JetBrains_Mono']">{bot.username}</span>
      </td>
      <td className="px-5 py-3.5">
        <PriorityBar value={bot.priority} />
      </td>
      <td className="px-5 py-3.5">
        <span className="text-sm text-text-secondary font-['JetBrains_Mono']">{bot.message_count}</span>
      </td>
      <td className="px-5 py-3.5">
        <div className="flex items-center justify-end gap-2">
          <button
            onClick={() => onEdit(bot)}
            className="px-3 py-1 rounded-md text-xs font-medium text-text-secondary border border-border hover:bg-bg-elevated hover:text-text-primary transition-colors"
          >
            Edit
          </button>
          <button
            onClick={() => onRestart(bot.id)}
            disabled={!bot.is_active}
            className="px-3 py-1 rounded-md text-xs font-medium text-text-secondary border border-border hover:bg-bg-elevated hover:text-text-primary transition-colors disabled:opacity-30"
          >
            Restart
          </button>
          <button
            onClick={() => onDelete(bot.id)}
            className="px-3 py-1 rounded-md text-xs font-medium text-red border border-red/30 hover:bg-red/10 transition-colors"
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
      <tr className="border-b border-border">
        <th className="text-left text-[11px] font-semibold text-text-muted uppercase tracking-[0.5px] font-['JetBrains_Mono'] px-5 py-3">Status</th>
        <th className="text-left text-[11px] font-semibold text-text-muted uppercase tracking-[0.5px] font-['JetBrains_Mono'] px-5 py-3">Bot Name</th>
        <th className="text-left text-[11px] font-semibold text-text-muted uppercase tracking-[0.5px] font-['JetBrains_Mono'] px-5 py-3">Username</th>
        <th className="text-left text-[11px] font-semibold text-text-muted uppercase tracking-[0.5px] font-['JetBrains_Mono'] px-5 py-3">Priority</th>
        <th className="text-left text-[11px] font-semibold text-text-muted uppercase tracking-[0.5px] font-['JetBrains_Mono'] px-5 py-3">Msgs Today</th>
        <th className="text-right text-[11px] font-semibold text-text-muted uppercase tracking-[0.5px] font-['JetBrains_Mono'] px-5 py-3">Actions</th>
      </tr>
    </thead>
  );

  return (
    <div className="flex flex-col h-full">
      <Header title="Bot Pool" />
      <div className="flex-1 px-8 py-6 overflow-auto">
        <div className="flex items-center justify-between mb-6">
          <p className="text-text-secondary text-sm">
            Manage your Telegram bots &middot; {bots.length} bot{bots.length !== 1 ? 's' : ''} &middot; {botGroups.length} group{botGroups.length !== 1 ? 's' : ''}
          </p>
          <div className="flex items-center gap-2">
            <button
              onClick={() => setShowGroupForm(!showGroupForm)}
              className="inline-flex items-center gap-2 px-4 py-2 text-sm font-medium text-purple border border-purple/30 rounded-lg hover:bg-purple/10 transition-colors"
            >
              <Users className="w-4 h-4" /> New Group
            </button>
            <button
              onClick={() => setShowAddForm(!showAddForm)}
              className="inline-flex items-center gap-2 px-4 py-2 bg-accent text-black text-sm font-medium rounded-lg hover:opacity-90 transition-opacity"
            >
              <Plus className="w-4 h-4" /> Add Bot
            </button>
          </div>
        </div>

        {/* New Group form */}
        {showGroupForm && (
          <div className="mb-6 bg-bg-card border border-purple/30 rounded-[10px] p-5">
            <form
              onSubmit={(e) => {
                e.preventDefault();
                if (!groupName.trim()) return;
                createGroupMutation.mutate({ name: groupName.trim(), description: groupDesc.trim() || undefined });
              }}
              className="flex items-end gap-4"
            >
              <div className="flex-1">
                <label className="block text-[13px] font-medium text-text-secondary mb-2">Group Name *</label>
                <input
                  type="text"
                  value={groupName}
                  onChange={(e) => setGroupName(e.target.value)}
                  placeholder="e.g. Sales Team"
                  className="w-full h-10 px-3.5 bg-bg-elevated border border-border rounded-lg text-sm text-text-primary placeholder:text-text-placeholder focus:outline-none focus:border-purple transition-colors"
                  required
                />
              </div>
              <div className="flex-1">
                <label className="block text-[13px] font-medium text-text-secondary mb-2">Description</label>
                <input
                  type="text"
                  value={groupDesc}
                  onChange={(e) => setGroupDesc(e.target.value)}
                  placeholder="Optional description"
                  className="w-full h-10 px-3.5 bg-bg-elevated border border-border rounded-lg text-sm text-text-primary placeholder:text-text-placeholder focus:outline-none focus:border-purple transition-colors"
                />
              </div>
              <button
                type="submit"
                disabled={createGroupMutation.isPending}
                className="inline-flex items-center gap-2 h-10 px-4 bg-purple text-text-primary text-sm font-medium rounded-lg hover:opacity-90 transition-opacity disabled:opacity-50 shrink-0"
              >
                <Users className="w-4 h-4" />
                {createGroupMutation.isPending ? 'Creating...' : 'Create Group'}
              </button>
            </form>
          </div>
        )}

        {/* Add Bot form */}
        {showAddForm && (
          <div className="mb-6 bg-bg-card border border-accent/20 rounded-[10px] p-5">
            <form onSubmit={handleAddSubmit} className="flex items-end gap-4">
              <div className="flex-1">
                <label className="block text-[13px] font-medium text-text-secondary mb-2 font-['Inter']">Bot Token *</label>
                <input
                  type="text"
                  value={formToken}
                  onChange={(e) => setFormToken(e.target.value)}
                  placeholder="123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11"
                  className="w-full h-10 px-3.5 bg-bg-elevated border border-border rounded-lg text-sm text-text-primary placeholder:text-text-placeholder focus:outline-none focus:border-accent transition-colors font-['JetBrains_Mono']"
                  required
                />
              </div>
              <div className="w-48">
                <label className="block text-[13px] font-medium text-text-secondary mb-2 font-['Inter']">Display Name</label>
                <input
                  type="text"
                  value={formName}
                  onChange={(e) => setFormName(e.target.value)}
                  placeholder="My Support Bot"
                  className="w-full h-10 px-3.5 bg-bg-elevated border border-border rounded-lg text-sm text-text-primary placeholder:text-text-placeholder focus:outline-none focus:border-accent transition-colors"
                />
              </div>
              <div className="w-28">
                <label className="block text-[13px] font-medium text-text-secondary mb-2 font-['Inter']">Priority</label>
                <input
                  type="number"
                  value={formPriority}
                  onChange={(e) => setFormPriority(Number(e.target.value))}
                  min={0}
                  max={10}
                  className="w-full h-10 px-3.5 bg-bg-elevated border border-border rounded-lg text-sm text-text-primary focus:outline-none focus:border-accent transition-colors font-['JetBrains_Mono']"
                />
              </div>
              <button
                type="submit"
                disabled={createMutation.isPending}
                className="inline-flex items-center gap-2 h-10 px-4 bg-accent text-black text-sm font-medium rounded-lg hover:opacity-90 transition-opacity disabled:opacity-50 shrink-0"
              >
                <Plus className="w-4 h-4" />
                {createMutation.isPending ? 'Adding...' : 'Add Bot'}
              </button>
            </form>
            {createMutation.isError && (
              <p className="text-xs text-red mt-3">
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
                className="flex items-center justify-between bg-bg-card border border-purple/20 rounded-t-[10px] px-5 py-3 cursor-pointer hover:bg-bg-elevated/50 transition-colors"
                onClick={() => toggleGroup(group.id)}
              >
                <div className="flex items-center gap-3">
                  {expanded ? <ChevronDown className="w-4 h-4 text-purple" /> : <ChevronRight className="w-4 h-4 text-purple" />}
                  <Users className="w-4 h-4 text-purple" />
                  <span className="text-sm font-semibold text-text-primary">{group.name}</span>
                  <span className="text-xs text-text-muted">{botsInGroup.length} bot{botsInGroup.length !== 1 ? 's' : ''}</span>
                  {group.description && (
                    <span className="text-xs text-text-placeholder ml-2">&middot; {group.description}</span>
                  )}
                </div>
                <div className="flex items-center gap-2" onClick={(e) => e.stopPropagation()}>
                  <button
                    onClick={() => startManageMembers(group)}
                    className="px-2.5 py-1 rounded text-[11px] font-medium text-purple border border-purple/30 hover:bg-purple/10 transition-colors"
                  >
                    Members
                  </button>
                  <button
                    onClick={() => {
                      if (window.confirm(`Delete bot group "${group.name}"? Bots will be ungrouped.`))
                        deleteGroupMutation.mutate(group.id);
                    }}
                    className="px-2.5 py-1 rounded text-[11px] font-medium text-red border border-red/30 hover:bg-red/10 transition-colors"
                  >
                    Delete
                  </button>
                </div>
              </div>
              {expanded && (
                <div className="bg-bg-card border border-t-0 border-purple/20 rounded-b-[10px] overflow-hidden">
                  <table className="w-full">
                    {tableHeader}
                    <tbody>
                      {botsInGroup.length === 0 ? (
                        <tr><td colSpan={6} className="text-center text-text-muted text-sm py-8">No bots in this group. Click Members to add.</td></tr>
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
        <div className="bg-bg-card border border-border rounded-[10px] overflow-hidden">
          {botGroups.length > 0 && (
            <div className="px-5 py-3 border-b border-border">
              <span className="text-xs font-semibold text-text-muted uppercase tracking-wider font-['JetBrains_Mono']">
                Ungrouped Bots
              </span>
            </div>
          )}
          <table className="w-full">
            {tableHeader}
            <tbody>
              {isLoading ? (
                <tr>
                  <td colSpan={6} className="text-center text-text-muted text-sm py-12">Loading bots...</td>
                </tr>
              ) : ungroupedBots.length === 0 ? (
                <tr>
                  <td colSpan={6} className="text-center text-text-muted text-sm py-12">
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
            <div className="bg-bg-page border border-border rounded-[10px] p-6 w-full max-w-md shadow-2xl">
              <div className="flex items-center justify-between mb-5">
                <h3 className="text-sm font-semibold text-text-primary">Edit Bot</h3>
                <button onClick={() => setEditingBot(null)} className="text-text-muted hover:text-text-primary">
                  <X className="w-4 h-4" />
                </button>
              </div>
              <form onSubmit={handleEditSubmit} className="flex flex-col gap-4">
                <div>
                  <label className="block text-[13px] font-medium text-text-secondary mb-2">Display Name</label>
                  <input
                    type="text"
                    value={editName}
                    onChange={(e) => setEditName(e.target.value)}
                    className="w-full h-10 px-3.5 bg-bg-elevated border border-border rounded-lg text-sm text-text-primary focus:outline-none focus:border-accent transition-colors"
                  />
                </div>
                <div>
                  <label className="block text-[13px] font-medium text-text-secondary mb-2">Priority (0-10)</label>
                  <input
                    type="number"
                    value={editPriority}
                    onChange={(e) => setEditPriority(Number(e.target.value))}
                    min={0}
                    max={10}
                    className="w-full h-10 px-3.5 bg-bg-elevated border border-border rounded-lg text-sm text-text-primary focus:outline-none focus:border-accent transition-colors font-['JetBrains_Mono']"
                  />
                </div>
                <div className="flex justify-end gap-3 mt-2">
                  <button type="button" onClick={() => setEditingBot(null)} className="px-4 py-2 text-sm text-text-secondary hover:text-text-primary">Cancel</button>
                  <button type="submit" disabled={updateMutation.isPending} className="px-4 py-2 bg-accent text-black text-sm font-medium rounded-lg hover:opacity-90 disabled:opacity-50">
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
            <div className="bg-bg-page border border-border rounded-[10px] p-6 w-full max-w-md shadow-2xl">
              <div className="flex items-center justify-between mb-5">
                <h3 className="text-sm font-semibold text-text-primary">
                  Manage Members &mdash; {managingMembers.name}
                </h3>
                <button onClick={() => setManagingMembers(null)} className="text-text-muted hover:text-text-primary">
                  <X className="w-4 h-4" />
                </button>
              </div>
              <p className="text-xs text-text-secondary mb-4">
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
                        selected ? 'bg-purple/10 border border-purple/30' : 'bg-bg-elevated border border-border'
                      } ${inOtherGroup ? 'opacity-40 cursor-not-allowed' : 'hover:border-purple/50'}`}
                    >
                      <input
                        type="checkbox"
                        checked={selected}
                        onChange={() => !inOtherGroup && toggleMemberBot(bot.id)}
                        disabled={!!inOtherGroup}
                        className="accent-purple"
                      />
                      <div className="flex-1">
                        <span className="text-sm text-text-primary">{bot.name}</span>
                        <span className="text-xs text-accent ml-2 font-['JetBrains_Mono']">{bot.username}</span>
                      </div>
                      {inOtherGroup && (
                        <span className="text-[10px] text-orange font-['JetBrains_Mono']">
                          in {bot.bot_group_name}
                        </span>
                      )}
                    </label>
                  );
                })}
              </div>
              <div className="flex justify-end gap-3">
                <button onClick={() => setManagingMembers(null)} className="px-4 py-2 text-sm text-text-secondary hover:text-text-primary">Cancel</button>
                <button
                  onClick={() => setMembersMutation.mutate({ groupId: managingMembers.id, botIds: memberBotIds })}
                  disabled={setMembersMutation.isPending}
                  className="px-4 py-2 bg-purple text-text-primary text-sm font-medium rounded-lg hover:opacity-90 disabled:opacity-50"
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
            <div className="bg-bg-page border border-border rounded-[10px] p-6 w-full max-w-sm shadow-2xl">
              <h3 className="text-sm font-semibold text-text-primary mb-3">Delete Bot</h3>
              <p className="text-sm text-text-secondary mb-5">
                Are you sure you want to permanently delete this bot? This action cannot be undone.
              </p>
              <div className="flex justify-end gap-3">
                <button onClick={() => setDeleteConfirm(null)} className="px-4 py-2 text-sm text-text-secondary hover:text-text-primary">Cancel</button>
                <button
                  onClick={() => deleteMutation.mutate(deleteConfirm)}
                  disabled={deleteMutation.isPending}
                  className="px-4 py-2 bg-red text-white text-sm font-medium rounded-lg hover:opacity-90 disabled:opacity-50"
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
