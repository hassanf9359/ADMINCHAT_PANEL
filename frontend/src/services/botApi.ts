import api from './api';
import type { Bot, BotGroup } from '../types';

export interface BotCreateData {
  token: string;
  display_name?: string;
  priority?: number;
}

export interface BotUpdateData {
  display_name?: string;
  is_active?: boolean;
  priority?: number;
}

export interface BotStatusData {
  id: number;
  bot_username: string | null;
  is_active: boolean;
  is_online: boolean;
  is_rate_limited: boolean;
  rate_limit_until: string | null;
  messages_today: number;
  last_send_at: string | null;
}

export async function getBots(): Promise<{ items: Bot[]; total: number }> {
  const { data } = await api.get('/bots');
  // Map backend BotResponse fields to frontend Bot type
  const items = (data.data.items || []).map((b: Record<string, unknown>) => ({
    id: b.id,
    name: b.display_name || b.bot_username || `Bot #${b.id}`,
    username: b.bot_username ? `@${b.bot_username}` : '',
    token_masked: '***',
    status: !b.is_active ? 'offline' : b.is_rate_limited ? 'rate_limited' : 'online',
    priority: b.priority ?? 0,
    rate_limit_until: b.rate_limit_until,
    message_count: 0,
    is_active: b.is_active,
    bot_group_id: b.bot_group_id,
    bot_group_name: b.bot_group_name,
    created_at: b.created_at,
  }));
  return { items, total: data.data.total };
}

// === Bot Groups ===

export interface BotGroupCreateData {
  name: string;
  description?: string;
  is_active?: boolean;
}

export interface BotGroupUpdateData {
  name?: string;
  description?: string;
  is_active?: boolean;
}

export async function getBotGroups(): Promise<BotGroup[]> {
  const { data } = await api.get('/bot-groups');
  return data.data;
}

export async function createBotGroup(body: BotGroupCreateData): Promise<BotGroup> {
  const { data } = await api.post('/bot-groups', body);
  return data.data;
}

export async function updateBotGroup(id: number, body: BotGroupUpdateData): Promise<BotGroup> {
  const { data } = await api.patch(`/bot-groups/${id}`, body);
  return data.data;
}

export async function deleteBotGroup(id: number): Promise<void> {
  await api.delete(`/bot-groups/${id}`);
}

export async function setBotGroupMembers(groupId: number, botIds: number[]): Promise<BotGroup> {
  const { data } = await api.put(`/bot-groups/${groupId}/members`, { bot_ids: botIds });
  return data.data;
}

export async function createBot(body: BotCreateData): Promise<Bot> {
  const { data } = await api.post('/bots', body);
  return data.data;
}

export async function updateBot(id: number, body: BotUpdateData): Promise<Bot> {
  const { data } = await api.patch(`/bots/${id}`, body);
  return data.data;
}

export async function deleteBot(id: number): Promise<void> {
  await api.delete(`/bots/${id}`);
}

export async function restartBot(id: number): Promise<void> {
  await api.post(`/bots/${id}/restart`);
}

export async function getBotStatus(id: number): Promise<BotStatusData> {
  const { data } = await api.get(`/bots/${id}/status`);
  return data.data;
}
