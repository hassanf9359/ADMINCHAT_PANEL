import api from './api';
import type { MovieRequest, MovieRequestDetail, MovieRequestStats, TmdbApiKey, MediaLibraryConfig, PaginatedResponse } from '../types';

export async function getMovieRequestStats(): Promise<MovieRequestStats> {
  const { data } = await api.get('/requests/stats');
  return data.data;
}

export async function getMovieRequests(params: {
  page?: number;
  page_size?: number;
  status?: string;
  media_type?: string;
}): Promise<PaginatedResponse<MovieRequest>> {
  const { data } = await api.get('/requests', { params });
  return data.data;
}

export async function getMovieRequestDetail(id: number): Promise<MovieRequestDetail> {
  const { data } = await api.get(`/requests/${id}`);
  return data.data;
}

export async function updateMovieRequest(
  id: number,
  body: { status?: string; admin_note?: string }
): Promise<MovieRequest> {
  const { data } = await api.patch(`/requests/${id}`, body);
  return data.data;
}

// TMDB API Keys
export async function getTmdbKeys(): Promise<{ items: TmdbApiKey[] }> {
  const { data } = await api.get('/requests/tmdb-keys');
  return data.data;
}

export async function createTmdbKey(body: {
  name: string;
  api_key: string;
  access_token?: string;
}): Promise<{ id: number; name: string }> {
  const { data } = await api.post('/requests/tmdb-keys', body);
  return data.data;
}

export async function deleteTmdbKey(id: number): Promise<void> {
  await api.delete(`/requests/tmdb-keys/${id}`);
}

// Media Library Config
export async function getMediaLibraryConfig(): Promise<MediaLibraryConfig | null> {
  const { data } = await api.get('/requests/media-library');
  return data.data;
}

export async function saveMediaLibraryConfig(body: {
  name: string;
  db_type: string;
  host: string;
  port?: number;
  database: string;
  username: string;
  password: string;
  table_name: string;
  tmdb_id_column: string;
  media_type_column?: string;
}): Promise<{ id: number; name: string }> {
  const { data } = await api.post('/requests/media-library', body);
  return data.data;
}

export async function deleteMediaLibraryConfig(): Promise<void> {
  await api.delete('/requests/media-library');
}

export async function testMediaLibraryConfig(): Promise<{ success: boolean; message: string }> {
  const { data } = await api.post('/requests/media-library/test');
  return data.data;
}
