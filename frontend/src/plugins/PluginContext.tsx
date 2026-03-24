import { createContext, useContext, useMemo, type ReactNode } from 'react';
import api from '../services/api';

export interface PluginSDK {
  pluginId: string;
  api: {
    get: (path: string, config?: object) => Promise<any>;
    post: (path: string, data?: unknown, config?: object) => Promise<any>;
    patch: (path: string, data?: unknown, config?: object) => Promise<any>;
    delete: (path: string, config?: object) => Promise<any>;
  };
}

const PluginCtx = createContext<PluginSDK | null>(null);

export function PluginProvider({ pluginId, children }: { pluginId: string; children: ReactNode }) {
  const sdk = useMemo<PluginSDK>(() => ({
    pluginId,
    api: {
      get: (path, config) => api.get(`/p/${pluginId}${path}`, config).then(r => r.data),
      post: (path, data, config) => api.post(`/p/${pluginId}${path}`, data, config).then(r => r.data),
      patch: (path, data, config) => api.patch(`/p/${pluginId}${path}`, data, config).then(r => r.data),
      delete: (path, config) => api.delete(`/p/${pluginId}${path}`, config).then(r => r.data),
    },
  }), [pluginId]);

  return <PluginCtx.Provider value={sdk}>{children}</PluginCtx.Provider>;
}

export function usePluginSDK(): PluginSDK {
  const ctx = useContext(PluginCtx);
  if (!ctx) throw new Error('usePluginSDK must be used within a PluginProvider');
  return ctx;
}
