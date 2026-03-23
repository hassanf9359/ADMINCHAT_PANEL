import api from './api';
import type { RagConfig, RagConfigCreate, RagConfigUpdate, RAGTestResult } from '../types';

export async function getRagConfigs(): Promise<{ items: RagConfig[]; total: number }> {
  const { data } = await api.get('/rag/configs');
  return data.data;
}

export async function createRagConfig(body: RagConfigCreate): Promise<RagConfig> {
  const { data } = await api.post('/rag/configs', body);
  return data.data;
}

export async function updateRagConfig(id: number, body: RagConfigUpdate): Promise<RagConfig> {
  const { data } = await api.patch(`/rag/configs/${id}`, body);
  return data.data;
}

export async function deleteRagConfig(id: number): Promise<void> {
  await api.delete(`/rag/configs/${id}`);
}

export async function testRagConfig(id: number): Promise<RAGTestResult> {
  const { data } = await api.post(`/rag/configs/${id}/test`);
  return data.data;
}
