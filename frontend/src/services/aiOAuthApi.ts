import api from './api';
import type { AIConfig, OAuthAuthUrlResponse, OAuthStatusResponse } from '../types';

export async function getOAuthAuthUrl(
  authMethod: string,
  configMeta: {
    name: string;
    provider: string;
    base_url?: string;
    model?: string;
    api_format?: string;
    default_params?: Record<string, unknown>;
  },
): Promise<OAuthAuthUrlResponse> {
  const { data } = await api.post(`/ai/oauth/${authMethod}/auth-url`, configMeta);
  return data.data;
}

export async function exchangeOAuthCode(
  code: string,
  state: string,
): Promise<AIConfig> {
  const { data } = await api.post('/ai/oauth/exchange', { code, state });
  return data.data;
}

export async function exchangeClaudeSessionToken(body: {
  session_cookie: string;
  name: string;
  base_url?: string;
  model?: string;
  api_format?: string;
  default_params?: Record<string, unknown>;
}): Promise<AIConfig> {
  const { data } = await api.post('/ai/oauth/claude/session-token', body);
  return data.data;
}

export async function getOAuthStatus(configId: number): Promise<OAuthStatusResponse> {
  const { data } = await api.get(`/ai/oauth/${configId}/status`);
  return data.data;
}
