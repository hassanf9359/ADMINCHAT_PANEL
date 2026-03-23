import api from './api';
import type { AIConfig, AIConfigCreate, AIConfigUpdate, AITestResult, AIUsageStats, RAGConfig, RAGTestResult } from '../types';

export async function getAIConfigs(): Promise<{ items: AIConfig[]; total: number }> {
  const { data } = await api.get('/ai/configs');
  return data.data;
}

export async function createAIConfig(body: AIConfigCreate): Promise<AIConfig> {
  const { data } = await api.post('/ai/configs', body);
  return data.data;
}

export async function updateAIConfig(id: number, body: AIConfigUpdate): Promise<AIConfig> {
  const { data } = await api.patch(`/ai/configs/${id}`, body);
  return data.data;
}

export async function deleteAIConfig(id: number): Promise<void> {
  await api.delete(`/ai/configs/${id}`);
}

export async function testAIConfig(id: number): Promise<AITestResult> {
  const { data } = await api.post(`/ai/configs/${id}/test`);
  return data.data;
}

export async function getAIUsage(days: number = 30): Promise<AIUsageStats> {
  const { data } = await api.get('/ai/usage', { params: { days } });
  return data.data;
}

// ---- RAG Config ----

export async function getRAGConfig(): Promise<RAGConfig> {
  const { data } = await api.get('/ai/rag-config');
  return data.data;
}

export async function saveRAGConfig(body: {
  provider: string;
  dify_base_url: string;
  dify_api_key?: string;
  dify_dataset_id: string;
  top_k: number;
}): Promise<RAGConfig> {
  // Strip empty api_key so backend knows to preserve existing
  const payload = { ...body };
  if (!payload.dify_api_key) delete payload.dify_api_key;
  const { data } = await api.put('/ai/rag-config', payload);
  return data.data;
}

export async function deleteRAGConfig(): Promise<RAGConfig> {
  const { data } = await api.delete('/ai/rag-config');
  return data.data;
}

export async function testRAGConfig(): Promise<RAGTestResult> {
  const { data } = await api.post('/ai/rag-config/test');
  return data.data;
}
