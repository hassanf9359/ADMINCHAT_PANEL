import { useQuery, useQueryClient } from '@tanstack/react-query';
import api from '../services/api';
import { useAuthStore } from '../stores/authStore';
import type { InstalledPlugin } from './types';

export function useInstalledPlugins() {
  const isAuthenticated = useAuthStore((s) => s.isAuthenticated);
  return useQuery({
    queryKey: ['installed-plugins'],
    queryFn: async (): Promise<InstalledPlugin[]> => {
      const { data } = await api.get('/plugins');
      return data.data?.plugins || [];
    },
    staleTime: 60_000,
    refetchOnWindowFocus: false,
    enabled: isAuthenticated,
  });
}

export function useActivePlugins() {
  const { data, ...rest } = useInstalledPlugins();
  return {
    data: data?.filter(p => p.status === 'active') || [],
    ...rest,
  };
}

export function useInvalidatePlugins() {
  const queryClient = useQueryClient();
  return () => queryClient.invalidateQueries({ queryKey: ['installed-plugins'] });
}
