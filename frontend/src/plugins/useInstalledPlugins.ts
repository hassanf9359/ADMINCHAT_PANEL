import { useQuery, useQueryClient } from '@tanstack/react-query';
import api from '../services/api';
import type { InstalledPlugin } from './types';

export function useInstalledPlugins() {
  return useQuery({
    queryKey: ['installed-plugins'],
    queryFn: async (): Promise<InstalledPlugin[]> => {
      const { data } = await api.get('/plugins');
      return data.data?.plugins || [];
    },
    staleTime: 60_000,
    refetchOnWindowFocus: false,
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
