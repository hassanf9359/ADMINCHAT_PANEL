import { Suspense, useEffect, useState, type ComponentType } from 'react';
import { PluginErrorBoundary } from './PluginErrorBoundary';
import { PluginProvider } from './PluginContext';

interface PluginRegistry {
  get(moduleName: string): Promise<{ default: ComponentType }>;
}

declare global {
  interface Window {
    [key: `__acp_plugin_${string}`]: PluginRegistry | undefined;
  }
}

function PageLoader() {
  return (
    <div className="flex items-center justify-center h-full">
      <div className="flex flex-col items-center gap-3">
        <div className="w-8 h-8 border-2 border-[#00D9FF] border-t-transparent rounded-full animate-spin" />
        <span className="text-sm text-[#6a6a6a]">Loading plugin...</span>
      </div>
    </div>
  );
}

const moduleCache = new Map<string, ComponentType>();

async function loadRemoteModule(pluginId: string, moduleName: string): Promise<ComponentType> {
  const cacheKey = `${pluginId}/${moduleName}`;
  if (moduleCache.has(cacheKey)) {
    return moduleCache.get(cacheKey)!;
  }

  const remoteUrl = `/plugins/${pluginId}/remoteEntry.js`;

  await new Promise<void>((resolve, reject) => {
    if (window[`__acp_plugin_${pluginId}`]) {
      resolve();
      return;
    }

    const script = document.createElement('script');
    script.src = remoteUrl;
    script.type = 'module';
    script.onload = () => resolve();
    script.onerror = () => reject(new Error(`Failed to load plugin: ${pluginId}`));
    document.head.appendChild(script);
  });

  const pluginRegistry = window[`__acp_plugin_${pluginId}`];
  if (!pluginRegistry) {
    throw new Error(`Plugin ${pluginId} did not register itself`);
  }

  const mod = await pluginRegistry.get(moduleName);
  if (!mod || !mod.default) {
    throw new Error(`Module ${moduleName} not found in plugin ${pluginId}`);
  }

  const component = mod.default as ComponentType;
  moduleCache.set(cacheKey, component);
  return component;
}

export function PluginLoader({
  pluginId,
  pluginName,
  moduleName = './pages/Main',
}: {
  pluginId: string;
  pluginName?: string;
  moduleName?: string;
}) {
  const [Component, setComponent] = useState<ComponentType | null>(null);
  const [error, setError] = useState<Error | null>(null);

  useEffect(() => {
    let cancelled = false;

    loadRemoteModule(pluginId, moduleName)
      .then(comp => {
        if (!cancelled) setComponent(() => comp);
      })
      .catch(err => {
        if (!cancelled) setError(err);
      });

    return () => { cancelled = true; };
  }, [pluginId, moduleName]);

  if (error) {
    return (
      <div className="flex items-center justify-center h-full">
        <div className="text-center p-8">
          <p className="text-[#FF4444] text-sm mb-2">Failed to load plugin</p>
          <p className="text-[#6a6a6a] text-xs">{error.message}</p>
        </div>
      </div>
    );
  }

  if (!Component) {
    return <PageLoader />;
  }

  return (
    <PluginErrorBoundary pluginId={pluginId} pluginName={pluginName}>
      <PluginProvider pluginId={pluginId}>
        <Suspense fallback={<PageLoader />}>
          <Component />
        </Suspense>
      </PluginProvider>
    </PluginErrorBoundary>
  );
}
