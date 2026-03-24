import api from './api';

// These endpoints go through the Panel backend which proxies to Market
// Panel backend handles Market API key management

export interface MarketPlugin {
  plugin_id: string;
  name: string;
  description: string;
  icon?: string;
  color?: string;
  categories: string[];
  tags: string[];
  author: { username: string; display_name: string; verified: boolean };
  pricing_model: 'free' | 'one_time' | 'subscription_monthly' | 'subscription_yearly';
  price_cents: number;
  currency: string;
  download_count: number;
  latest_version: string;
  min_panel_version?: string;
  is_featured: boolean;
  updated_at: string;
}

export interface MarketPluginDetail extends MarketPlugin {
  long_description?: string;
  versions: Array<{
    version: string;
    changelog?: string;
    min_panel_version?: string;
    published_at: string;
  }>;
  screenshots?: string[];
}

export async function searchMarketPlugins(params: {
  q?: string;
  category?: string;
  sort?: 'popular' | 'newest' | 'updated';
  page?: number;
  page_size?: number;
  pricing?: 'free' | 'paid' | 'all';
}): Promise<{ items: MarketPlugin[]; total: number; page: number; total_pages: number }> {
  const { data } = await api.get('/plugins/market', { params });
  return data.data;
}

export async function getMarketPluginDetail(pluginId: string): Promise<MarketPluginDetail> {
  const { data } = await api.get(`/plugins/market/${pluginId}`);
  return data.data;
}

export async function installFromMarket(pluginId: string, version: string, licenseKey?: string): Promise<unknown> {
  const { data } = await api.post('/plugins/install', {
    plugin_id: pluginId,
    version,
    market_url: `https://acpmarket.novahelix.org/api/v1/plugins/${pluginId}/versions/${version}/download`,
    license_key: licenseKey,
  });
  return data.data;
}

export async function checkPluginUpdates(): Promise<Array<{
  plugin_id: string;
  current: string;
  latest: string;
  changelog?: string;
  compatible: boolean;
}>> {
  const { data } = await api.post('/plugins/market/check-updates');
  return data.data?.updates || [];
}
