export interface PluginManifest {
  id: string;
  name: string;
  version: string;
  description?: string;
  icon?: string;
  color?: string;

  frontend?: {
    remote_entry?: string;
    sidebar?: PluginSidebarItem[];
    settings_tabs?: PluginSettingsTab[];
    exposed_modules?: Record<string, string>;
  };

  capabilities?: {
    database?: boolean;
    bot_handler?: boolean;
    api_routes?: boolean;
    frontend_pages?: boolean;
    settings_tab?: boolean;
  };
}

export interface PluginSidebarItem {
  path: string;
  label: string;
  icon: string;
  minRole: 'agent' | 'admin' | 'super_admin';
  position?: string;
  badge_api?: string;
}

export interface PluginSettingsTab {
  key: string;
  label: string;
  module: string;
}

export interface InstalledPlugin {
  plugin_id: string;
  name: string;
  version: string;
  status: 'installed' | 'active' | 'disabled' | 'error' | 'updating';
  manifest: PluginManifest;
  config: Record<string, unknown>;
  error_count: number;
  last_error?: string;
  license_key_set: boolean;
  installed_at: string;
  activated_at?: string;
  updated_at: string;
}
