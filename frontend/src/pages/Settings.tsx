import { useState, useEffect } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Save, Clock, Shield, Database, Settings as SettingsIcon, Loader2, RefreshCw, ExternalLink, Plus, Trash2, Key, FlaskConical } from 'lucide-react';
import Header from '../components/layout/Header';
import { getSettings, updateSettings, getVersionInfo } from '../services/settingsApi';
import {
  getTmdbKeys, createTmdbKey, deleteTmdbKey,
  getMediaLibraryConfig, saveMediaLibraryConfig, deleteMediaLibraryConfig, testMediaLibraryConfig,
} from '../services/movieRequestApi';
import type { SettingItem, TmdbApiKey } from '../types';

// ---- Tab definitions ----
const TABS = [
  { key: 'admins', label: 'Admins' },
  { key: 'system', label: 'System' },
  { key: 'ai', label: 'AI Config' },
  { key: 'permissions', label: 'Permissions' },
  { key: 'tmdb', label: 'TMDB Keys' },
] as const;

type TabKey = typeof TABS[number]['key'];

// ---- Helpers ----
function getSettingValue(items: SettingItem[], key: string, fallback: unknown = ''): unknown {
  const item = items.find((s) => s.key === key);
  if (!item) return fallback;
  const val = item.value;
  if (typeof val === 'object' && val !== null && 'value' in (val as Record<string, unknown>)) {
    return (val as Record<string, unknown>).value;
  }
  return val;
}

// ---- Setting card component ----
function SettingCard({
  label,
  description,
  children,
}: {
  label: string;
  description?: string;
  children: React.ReactNode;
}) {
  return (
    <div className="flex items-start justify-between gap-8 px-5 py-4 border-b border-[#1A1A1A] last:border-0">
      <div className="flex-1 min-w-0">
        <h4 className="text-sm font-medium text-white">{label}</h4>
        {description && <p className="text-xs text-[#6a6a6a] mt-0.5">{description}</p>}
      </div>
      <div className="flex-shrink-0">{children}</div>
    </div>
  );
}

// ---- Toggle component ----
function Toggle({ value, onChange }: { value: boolean; onChange: (v: boolean) => void }) {
  return (
    <button
      type="button"
      onClick={() => onChange(!value)}
      className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors ${
        value ? 'bg-[#00D9FF]' : 'bg-[#141414] border border-[#2f2f2f]'
      }`}
    >
      <span
        className={`inline-block h-4 w-4 rounded-full bg-white transition-transform ${
          value ? 'translate-x-6' : 'translate-x-1'
        }`}
      />
    </button>
  );
}

function TmdbKeysTab() {
  const queryClient = useQueryClient();
  const [showForm, setShowForm] = useState(false);
  const [formName, setFormName] = useState('');
  const [formApiKey, setFormApiKey] = useState('');
  const [formAccessToken, setFormAccessToken] = useState('');

  const { data, isLoading } = useQuery({
    queryKey: ['tmdb-keys'],
    queryFn: getTmdbKeys,
  });

  const addMutation = useMutation({
    mutationFn: () =>
      createTmdbKey({
        name: formName,
        api_key: formApiKey,
        access_token: formAccessToken || undefined,
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['tmdb-keys'] });
      setShowForm(false);
      setFormName('');
      setFormApiKey('');
      setFormAccessToken('');
    },
  });

  const deleteMutation = useMutation({
    mutationFn: (id: number) => deleteTmdbKey(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['tmdb-keys'] }),
  });

  const keys: TmdbApiKey[] = data?.items || [];

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h3 className="text-[18px] font-semibold text-white font-['Space_Grotesk']">TMDB API Keys</h3>
        <button
          onClick={() => setShowForm(!showForm)}
          className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium bg-[#00D9FF]/10 text-[#00D9FF] hover:bg-[#00D9FF]/20 transition-colors"
        >
          <Plus size={14} />
          Add Key
        </button>
      </div>

      {/* Add form */}
      {showForm && (
        <div className="bg-[#0A0A0A] border border-[#2f2f2f] rounded-[10px] p-5 space-y-4">
          <div className="grid grid-cols-3 gap-4">
            <div>
              <label className="block text-xs text-[#6a6a6a] mb-1.5">Name</label>
              <input
                type="text"
                value={formName}
                onChange={(e) => setFormName(e.target.value)}
                placeholder="My TMDB Key"
                className="w-full h-10 px-3.5 bg-[#141414] border border-[#2f2f2f] rounded-lg text-sm text-white placeholder:text-[#4a4a4a] focus:outline-none focus:border-[#00D9FF] transition-colors"
              />
            </div>
            <div>
              <label className="block text-xs text-[#6a6a6a] mb-1.5">API Key</label>
              <input
                type="text"
                value={formApiKey}
                onChange={(e) => setFormApiKey(e.target.value)}
                placeholder="API key"
                className="w-full h-10 px-3.5 bg-[#141414] border border-[#2f2f2f] rounded-lg text-sm text-white placeholder:text-[#4a4a4a] font-['JetBrains_Mono'] focus:outline-none focus:border-[#00D9FF] transition-colors"
              />
            </div>
            <div>
              <label className="block text-xs text-[#6a6a6a] mb-1.5">Access Token (optional)</label>
              <input
                type="text"
                value={formAccessToken}
                onChange={(e) => setFormAccessToken(e.target.value)}
                placeholder="Bearer token"
                className="w-full h-10 px-3.5 bg-[#141414] border border-[#2f2f2f] rounded-lg text-sm text-white placeholder:text-[#4a4a4a] font-['JetBrains_Mono'] focus:outline-none focus:border-[#00D9FF] transition-colors"
              />
            </div>
          </div>
          <div className="flex justify-end gap-2">
            <button
              onClick={() => setShowForm(false)}
              className="px-3 py-1.5 rounded-md text-xs font-medium text-[#8a8a8a] border border-[#2f2f2f] hover:bg-[#141414] transition-colors"
            >
              Cancel
            </button>
            <button
              onClick={() => addMutation.mutate()}
              disabled={!formName || !formApiKey || addMutation.isPending}
              className="inline-flex items-center gap-1.5 px-4 py-1.5 bg-[#00D9FF] text-black text-xs font-medium rounded-md hover:opacity-90 transition-opacity disabled:opacity-30"
            >
              {addMutation.isPending ? <Loader2 size={12} className="animate-spin" /> : <Plus size={12} />}
              Add
            </button>
          </div>
        </div>
      )}

      {/* Key cards */}
      {isLoading ? (
        <div className="flex items-center justify-center py-12">
          <Loader2 className="w-6 h-6 text-[#6a6a6a] animate-spin" />
        </div>
      ) : keys.length === 0 ? (
        <div className="bg-[#0A0A0A] border border-[#2f2f2f] rounded-[10px] p-8 text-center">
          <Key size={24} className="text-[#4a4a4a] mx-auto mb-2" />
          <p className="text-sm text-[#6a6a6a]">No TMDB API keys configured</p>
        </div>
      ) : (
        <div className="grid grid-cols-2 gap-4">
          {keys.map((k) => (
            <div
              key={k.id}
              className="bg-[#0A0A0A] border border-[#2f2f2f] rounded-[10px] p-5"
            >
              <div className="flex items-start justify-between mb-3">
                <div>
                  <h4 className="text-sm font-medium text-white">{k.name}</h4>
                  <p className="text-xs text-[#6a6a6a] font-['JetBrains_Mono'] mt-1">{k.api_key_masked}</p>
                </div>
                <button
                  onClick={() => deleteMutation.mutate(k.id)}
                  disabled={deleteMutation.isPending}
                  className="p-1.5 rounded-md hover:bg-[#FF4444]/10 text-[#6a6a6a] hover:text-[#FF4444] transition-colors"
                  title="Delete key"
                >
                  <Trash2 size={14} />
                </button>
              </div>
              <div className="flex items-center gap-3">
                {k.is_active ? (
                  k.is_rate_limited ? (
                    <span className="text-[10px] font-semibold font-['JetBrains_Mono'] px-2 py-0.5 rounded bg-[#FF8800]/10 text-[#FF8800]">
                      RATE LIMITED
                    </span>
                  ) : (
                    <span className="text-[10px] font-semibold font-['JetBrains_Mono'] px-2 py-0.5 rounded bg-[#059669]/10 text-[#059669]">
                      ACTIVE
                    </span>
                  )
                ) : (
                  <span className="text-[10px] font-semibold font-['JetBrains_Mono'] px-2 py-0.5 rounded bg-[#141414] text-[#6a6a6a]">
                    INACTIVE
                  </span>
                )}
                <span className="text-[10px] text-[#6a6a6a] font-['JetBrains_Mono']">
                  {k.request_count} requests
                </span>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Media Library Config */}
      <MediaLibrarySection />
    </div>
  );
}

function MediaLibrarySection() {
  const queryClient = useQueryClient();
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState({
    name: '',
    db_type: 'postgresql' as string,
    host: '',
    port: '',
    database: '',
    username: '',
    password: '',
    table_name: '',
    tmdb_id_column: 'tmdb_id',
    media_type_column: '',
  });

  const { data: config, isLoading } = useQuery({
    queryKey: ['media-library-config'],
    queryFn: getMediaLibraryConfig,
  });

  const saveMutation = useMutation({
    mutationFn: () =>
      saveMediaLibraryConfig({
        ...form,
        port: form.port ? Number(form.port) : undefined,
        media_type_column: form.media_type_column || undefined,
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['media-library-config'] });
      setShowForm(false);
    },
  });

  const deleteMutation = useMutation({
    mutationFn: deleteMediaLibraryConfig,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['media-library-config'] }),
  });

  const testMutation = useMutation({
    mutationFn: testMediaLibraryConfig,
  });

  const updateForm = (key: string, value: string) =>
    setForm((prev) => ({ ...prev, [key]: value }));

  return (
    <div className="space-y-4 mt-8">
      <div className="flex items-center justify-between">
        <div>
          <h3 className="text-[18px] font-semibold text-white font-['Space_Grotesk']">Media Library Database</h3>
          <p className="text-xs text-[#6a6a6a] mt-1">
            Optional: connect to an external database to check if a title is already in your media library.
            If not configured, all requests are forwarded to the admin panel.
          </p>
        </div>
      </div>

      {isLoading ? (
        <div className="flex items-center justify-center py-8">
          <Loader2 className="w-5 h-5 text-[#6a6a6a] animate-spin" />
        </div>
      ) : config ? (
        /* Show current config */
        <div className="bg-[#0A0A0A] border border-[#2f2f2f] rounded-[10px] p-5 space-y-3">
          <div className="flex items-start justify-between">
            <div>
              <h4 className="text-sm font-medium text-white">{config.name}</h4>
              <p className="text-xs text-[#6a6a6a] font-['JetBrains_Mono'] mt-1">
                {config.db_type.toUpperCase()} @ {config.host}:{config.port || (config.db_type === 'postgresql' ? 5432 : 3306)} / {config.database}
              </p>
            </div>
            <div className="flex items-center gap-2">
              <button
                onClick={() => testMutation.mutate()}
                disabled={testMutation.isPending}
                className="inline-flex items-center gap-1 px-2.5 py-1 rounded-md text-xs font-medium text-[#00D9FF] border border-[#00D9FF]/20 hover:bg-[#00D9FF]/10 transition-colors disabled:opacity-40"
              >
                {testMutation.isPending ? <Loader2 size={12} className="animate-spin" /> : <FlaskConical size={12} />}
                Test
              </button>
              <button
                onClick={() => deleteMutation.mutate()}
                disabled={deleteMutation.isPending}
                className="p-1.5 rounded-md hover:bg-[#FF4444]/10 text-[#6a6a6a] hover:text-[#FF4444] transition-colors"
                title="Remove config"
              >
                <Trash2 size={14} />
              </button>
            </div>
          </div>
          <div className="grid grid-cols-3 gap-3 text-xs">
            <div>
              <span className="text-[#6a6a6a]">Table:</span>{' '}
              <span className="text-white font-['JetBrains_Mono']">{config.table_name}</span>
            </div>
            <div>
              <span className="text-[#6a6a6a]">TMDB ID Column:</span>{' '}
              <span className="text-white font-['JetBrains_Mono']">{config.tmdb_id_column}</span>
            </div>
            <div>
              <span className="text-[#6a6a6a]">Type Column:</span>{' '}
              <span className="text-white font-['JetBrains_Mono']">{config.media_type_column || '—'}</span>
            </div>
          </div>
          {config.is_active && (
            <span className="text-[10px] font-semibold font-['JetBrains_Mono'] px-2 py-0.5 rounded bg-[#059669]/10 text-[#059669]">
              ACTIVE
            </span>
          )}
          {testMutation.data && (
            <p className={`text-xs font-['JetBrains_Mono'] ${testMutation.data.success ? 'text-[#059669]' : 'text-[#FF4444]'}`}>
              {testMutation.data.message}
            </p>
          )}
        </div>
      ) : (
        /* No config — show add button or form */
        !showForm ? (
          <button
            onClick={() => setShowForm(true)}
            className="w-full py-6 bg-[#0A0A0A] border border-dashed border-[#2f2f2f] rounded-[10px] text-sm text-[#6a6a6a] hover:text-white hover:border-[#00D9FF]/30 transition-colors"
          >
            <Database size={20} className="mx-auto mb-2 opacity-50" />
            Configure External Media Library
          </button>
        ) : null
      )}

      {/* Config form */}
      {showForm && !config && (
        <div className="bg-[#0A0A0A] border border-[#2f2f2f] rounded-[10px] p-5 space-y-4">
          <div className="grid grid-cols-3 gap-4">
            <div>
              <label className="block text-xs text-[#6a6a6a] mb-1.5">Name</label>
              <input type="text" value={form.name} onChange={(e) => updateForm('name', e.target.value)} placeholder="My Media Server" className="w-full h-10 px-3.5 bg-[#141414] border border-[#2f2f2f] rounded-lg text-sm text-white placeholder:text-[#4a4a4a] focus:outline-none focus:border-[#00D9FF] transition-colors" />
            </div>
            <div>
              <label className="block text-xs text-[#6a6a6a] mb-1.5">Database Type</label>
              <select value={form.db_type} onChange={(e) => updateForm('db_type', e.target.value)} className="w-full h-10 px-3.5 bg-[#141414] border border-[#2f2f2f] rounded-lg text-sm text-white focus:outline-none focus:border-[#00D9FF] transition-colors">
                <option value="postgresql">PostgreSQL</option>
                <option value="mysql">MySQL</option>
              </select>
            </div>
            <div>
              <label className="block text-xs text-[#6a6a6a] mb-1.5">Host</label>
              <input type="text" value={form.host} onChange={(e) => updateForm('host', e.target.value)} placeholder="192.168.1.100" className="w-full h-10 px-3.5 bg-[#141414] border border-[#2f2f2f] rounded-lg text-sm text-white placeholder:text-[#4a4a4a] font-['JetBrains_Mono'] focus:outline-none focus:border-[#00D9FF] transition-colors" />
            </div>
          </div>
          <div className="grid grid-cols-4 gap-4">
            <div>
              <label className="block text-xs text-[#6a6a6a] mb-1.5">Port</label>
              <input type="text" value={form.port} onChange={(e) => updateForm('port', e.target.value)} placeholder={form.db_type === 'postgresql' ? '5432' : '3306'} className="w-full h-10 px-3.5 bg-[#141414] border border-[#2f2f2f] rounded-lg text-sm text-white placeholder:text-[#4a4a4a] font-['JetBrains_Mono'] focus:outline-none focus:border-[#00D9FF] transition-colors" />
            </div>
            <div>
              <label className="block text-xs text-[#6a6a6a] mb-1.5">Database</label>
              <input type="text" value={form.database} onChange={(e) => updateForm('database', e.target.value)} placeholder="media_db" className="w-full h-10 px-3.5 bg-[#141414] border border-[#2f2f2f] rounded-lg text-sm text-white placeholder:text-[#4a4a4a] font-['JetBrains_Mono'] focus:outline-none focus:border-[#00D9FF] transition-colors" />
            </div>
            <div>
              <label className="block text-xs text-[#6a6a6a] mb-1.5">Username</label>
              <input type="text" value={form.username} onChange={(e) => updateForm('username', e.target.value)} placeholder="db_user" className="w-full h-10 px-3.5 bg-[#141414] border border-[#2f2f2f] rounded-lg text-sm text-white placeholder:text-[#4a4a4a] font-['JetBrains_Mono'] focus:outline-none focus:border-[#00D9FF] transition-colors" />
            </div>
            <div>
              <label className="block text-xs text-[#6a6a6a] mb-1.5">Password</label>
              <input type="password" value={form.password} onChange={(e) => updateForm('password', e.target.value)} placeholder="********" className="w-full h-10 px-3.5 bg-[#141414] border border-[#2f2f2f] rounded-lg text-sm text-white placeholder:text-[#4a4a4a] font-['JetBrains_Mono'] focus:outline-none focus:border-[#00D9FF] transition-colors" />
            </div>
          </div>
          <div className="grid grid-cols-3 gap-4">
            <div>
              <label className="block text-xs text-[#6a6a6a] mb-1.5">Table Name</label>
              <input type="text" value={form.table_name} onChange={(e) => updateForm('table_name', e.target.value)} placeholder="movies" className="w-full h-10 px-3.5 bg-[#141414] border border-[#2f2f2f] rounded-lg text-sm text-white placeholder:text-[#4a4a4a] font-['JetBrains_Mono'] focus:outline-none focus:border-[#00D9FF] transition-colors" />
            </div>
            <div>
              <label className="block text-xs text-[#6a6a6a] mb-1.5">TMDB ID Column</label>
              <input type="text" value={form.tmdb_id_column} onChange={(e) => updateForm('tmdb_id_column', e.target.value)} placeholder="tmdb_id" className="w-full h-10 px-3.5 bg-[#141414] border border-[#2f2f2f] rounded-lg text-sm text-white placeholder:text-[#4a4a4a] font-['JetBrains_Mono'] focus:outline-none focus:border-[#00D9FF] transition-colors" />
            </div>
            <div>
              <label className="block text-xs text-[#6a6a6a] mb-1.5">Media Type Column (optional)</label>
              <input type="text" value={form.media_type_column} onChange={(e) => updateForm('media_type_column', e.target.value)} placeholder="media_type" className="w-full h-10 px-3.5 bg-[#141414] border border-[#2f2f2f] rounded-lg text-sm text-white placeholder:text-[#4a4a4a] font-['JetBrains_Mono'] focus:outline-none focus:border-[#00D9FF] transition-colors" />
            </div>
          </div>
          <div className="flex justify-end gap-2">
            <button onClick={() => setShowForm(false)} className="px-3 py-1.5 rounded-md text-xs font-medium text-[#8a8a8a] border border-[#2f2f2f] hover:bg-[#141414] transition-colors">
              Cancel
            </button>
            <button
              onClick={() => saveMutation.mutate()}
              disabled={!form.name || !form.host || !form.database || !form.username || !form.password || !form.table_name || !form.tmdb_id_column || saveMutation.isPending}
              className="inline-flex items-center gap-1.5 px-4 py-1.5 bg-[#00D9FF] text-black text-xs font-medium rounded-md hover:opacity-90 transition-opacity disabled:opacity-30"
            >
              {saveMutation.isPending ? <Loader2 size={12} className="animate-spin" /> : <Save size={12} />}
              Save
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

function VersionInfoCard() {
  const { data: versionInfo, isLoading: versionLoading, refetch } = useQuery({
    queryKey: ['version-info'],
    queryFn: getVersionInfo,
    staleTime: 300_000,
  });

  return (
    <div className="mt-8 bg-[#0A0A0A] border border-[#2f2f2f] rounded-[10px] overflow-hidden">
      <div className="px-5 py-4 border-b border-[#2f2f2f] flex items-center justify-between">
        <h3 className="text-sm font-semibold text-white font-['Space_Grotesk']">Version Info</h3>
        <button
          onClick={() => refetch()}
          disabled={versionLoading}
          className="p-1.5 rounded-md hover:bg-[#141414] text-[#6a6a6a] hover:text-white transition-colors disabled:opacity-40"
          title="Check for updates"
        >
          <RefreshCw size={14} className={versionLoading ? 'animate-spin' : ''} />
        </button>
      </div>
      <div className="px-5 py-4">
        {versionLoading && !versionInfo ? (
          <div className="flex items-center gap-2 text-[#6a6a6a] text-sm">
            <Loader2 size={14} className="animate-spin" />
            Checking version...
          </div>
        ) : versionInfo ? (
          <div className="space-y-3">
            <div className="flex items-center gap-4">
              <div className="flex-1">
                <p className="text-[11px] text-[#6a6a6a] mb-1">Current Version</p>
                <p className="text-sm text-white font-['JetBrains_Mono']">v{versionInfo.current_version}</p>
              </div>
              <div className="flex-1">
                <p className="text-[11px] text-[#6a6a6a] mb-1">Build</p>
                <p className="text-sm text-[#8a8a8a] font-['JetBrains_Mono']">{versionInfo.build_version}</p>
              </div>
              <div className="flex-1">
                <p className="text-[11px] text-[#6a6a6a] mb-1">Latest on GitHub</p>
                <p className="text-sm text-white font-['JetBrains_Mono']">
                  {versionInfo.latest_version ? `v${versionInfo.latest_version}` : 'Unable to check'}
                </p>
              </div>
            </div>
            {versionInfo.update_available && (
              <div className="flex items-center gap-2 mt-2 px-3 py-2 bg-[#00D9FF]/5 border border-[#00D9FF]/20 rounded-lg">
                <span className="text-[11px] font-semibold font-['JetBrains_Mono'] px-2 py-0.5 rounded bg-[#00D9FF]/10 text-[#00D9FF]">
                  Update available: v{versionInfo.latest_version}
                </span>
                <a
                  href="https://github.com/fxxkrlab/ADMINCHAT_PANEL/releases"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-[11px] text-[#00D9FF] hover:underline flex items-center gap-1 ml-auto"
                >
                  View releases <ExternalLink size={11} />
                </a>
              </div>
            )}
            {!versionInfo.update_available && versionInfo.latest_version && (
              <p className="text-[11px] text-[#059669] font-['JetBrains_Mono']">You're on the latest version.</p>
            )}
          </div>
        ) : (
          <p className="text-sm text-[#6a6a6a]">Failed to load version info.</p>
        )}
      </div>
    </div>
  );
}

export default function Settings() {
  const queryClient = useQueryClient();
  const [activeTab, setActiveTab] = useState<TabKey>('admins');
  const [localSettings, setLocalSettings] = useState<Record<string, unknown>>({});
  const [hasChanges, setHasChanges] = useState(false);

  const { data, isLoading } = useQuery({
    queryKey: ['settings'],
    queryFn: getSettings,
  });

  const saveMutation = useMutation({
    mutationFn: (settings: Record<string, unknown>) => updateSettings(settings),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['settings'] });
      setHasChanges(false);
    },
  });

  const items = data?.items || [];

  // Initialize local settings from fetched data
  useEffect(() => {
    if (items.length > 0) {
      const settings: Record<string, unknown> = {};
      items.forEach((item) => {
        settings[item.key] = getSettingValue(items, item.key);
      });
      setLocalSettings(settings);
    }
  }, [items]);

  const updateLocal = (key: string, value: unknown) => {
    setLocalSettings((prev) => ({ ...prev, [key]: value }));
    setHasChanges(true);
  };

  const handleSave = () => {
    saveMutation.mutate(localSettings);
  };

  const getLocal = (key: string, fallback: unknown = '') => {
    if (key in localSettings) return localSettings[key];
    return getSettingValue(items, key, fallback);
  };

  return (
    <div className="flex flex-col h-full">
      <Header title="System Settings" />
      <div className="flex-1 px-8 py-6 overflow-auto">
        {/* Tab navigation */}
        <div className="flex items-center gap-6 mb-8 border-b border-[#1A1A1A]">
          {TABS.map(({ key, label }) => (
            <button
              key={key}
              onClick={() => setActiveTab(key)}
              className={`pb-3 text-sm font-medium transition-colors relative ${
                activeTab === key
                  ? 'text-[#00D9FF]'
                  : 'text-[#6a6a6a] hover:text-white'
              }`}
            >
              {label}
              {activeTab === key && (
                <div className="absolute bottom-0 left-0 right-0 h-0.5 bg-[#00D9FF]" />
              )}
            </button>
          ))}
        </div>

        {isLoading ? (
          <div className="flex items-center justify-center py-20">
            <Loader2 className="w-6 h-6 text-[#6a6a6a] animate-spin" />
          </div>
        ) : (
          <>
            {/* Admins tab - admin table placeholder */}
            {activeTab === 'admins' && (
              <div className="space-y-6">
                {/* Admin table */}
                <div className="bg-[#0A0A0A] border border-[#2f2f2f] rounded-[10px] overflow-hidden">
                  <table className="w-full">
                    <thead>
                      <tr className="border-b border-[#2f2f2f]">
                        <th className="text-left text-[11px] font-semibold text-[#6a6a6a] uppercase tracking-[0.5px] font-['JetBrains_Mono'] px-5 py-3">Username</th>
                        <th className="text-left text-[11px] font-semibold text-[#6a6a6a] uppercase tracking-[0.5px] font-['JetBrains_Mono'] px-5 py-3">Role</th>
                        <th className="text-left text-[11px] font-semibold text-[#6a6a6a] uppercase tracking-[0.5px] font-['JetBrains_Mono'] px-5 py-3">Status</th>
                        <th className="text-right text-[11px] font-semibold text-[#6a6a6a] uppercase tracking-[0.5px] font-['JetBrains_Mono'] px-5 py-3">Actions</th>
                      </tr>
                    </thead>
                    <tbody>
                      <tr className="border-b border-[#1A1A1A]">
                        <td className="px-5 py-3.5 text-sm text-white">admin</td>
                        <td className="px-5 py-3.5">
                          <span className="text-[10px] font-semibold font-['JetBrains_Mono'] px-2 py-0.5 rounded bg-[#00D9FF]/10 text-[#00D9FF]">SUPER ADMIN</span>
                        </td>
                        <td className="px-5 py-3.5">
                          <span className="text-[10px] font-semibold font-['JetBrains_Mono'] px-2 py-0.5 rounded bg-[#059669]/10 text-[#059669]">ACTIVE</span>
                        </td>
                        <td className="px-5 py-3.5 text-right">
                          <button className="px-3 py-1 rounded-md text-xs font-medium text-[#8a8a8a] border border-[#2f2f2f] hover:bg-[#141414] transition-colors">
                            Edit
                          </button>
                        </td>
                      </tr>
                    </tbody>
                  </table>
                </div>

                {/* Bottom settings cards row */}
                <div className="grid grid-cols-4 gap-4">
                  <div className="bg-[#0A0A0A] border border-[#2f2f2f] rounded-[10px] p-5">
                    <div className="flex items-center gap-2 mb-3">
                      <Shield size={16} className="text-[#00D9FF]" />
                      <span className="text-[13px] font-medium text-white">Turnstile</span>
                    </div>
                    <Toggle
                      value={!!getLocal('turnstile_enabled', false)}
                      onChange={(v) => updateLocal('turnstile_enabled', v)}
                    />
                  </div>
                  <div className="bg-[#0A0A0A] border border-[#2f2f2f] rounded-[10px] p-5">
                    <div className="flex items-center gap-2 mb-3">
                      <Database size={16} className="text-[#00D9FF]" />
                      <span className="text-[13px] font-medium text-white">Media Cache</span>
                    </div>
                    <span className="text-sm text-[#8a8a8a] font-['JetBrains_Mono']">{String(getLocal('media_cache_days', 7))} days</span>
                  </div>
                  <div className="bg-[#0A0A0A] border border-[#2f2f2f] rounded-[10px] p-5">
                    <div className="flex items-center gap-2 mb-3">
                      <SettingsIcon size={16} className="text-[#00D9FF]" />
                      <span className="text-[13px] font-medium text-white">Sessions</span>
                    </div>
                    <Toggle
                      value={!!getLocal('auto_assign_enabled', false)}
                      onChange={(v) => updateLocal('auto_assign_enabled', v)}
                    />
                  </div>
                  <div className="bg-[#0A0A0A] border border-[#2f2f2f] rounded-[10px] p-5">
                    <div className="flex items-center gap-2 mb-3">
                      <Clock size={16} className="text-[#00D9FF]" />
                      <span className="text-[13px] font-medium text-white">Knowledge</span>
                    </div>
                    <span className="text-sm text-[#8a8a8a] font-['JetBrains_Mono']">{String(getLocal('missed_knowledge_update_hour', 3))}:00 UTC</span>
                  </div>
                </div>
              </div>
            )}

            {/* System tab */}
            {activeTab === 'system' && (
              <div className="bg-[#0A0A0A] border border-[#2f2f2f] rounded-[10px] overflow-hidden">
                <div className="px-5 py-4 border-b border-[#2f2f2f]">
                  <h3 className="text-[18px] font-semibold text-white font-['Space_Grotesk']">General System Settings</h3>
                </div>
                <SettingCard
                  label="Auto-Assign Conversations"
                  description="Automatically assign new conversations to available agents"
                >
                  <Toggle
                    value={!!getLocal('auto_assign_enabled', false)}
                    onChange={(v) => updateLocal('auto_assign_enabled', v)}
                  />
                </SettingCard>
                <SettingCard
                  label="Session Timeout (minutes)"
                  description="Admin session inactivity timeout"
                >
                  <input
                    type="number"
                    value={String(getLocal('session_timeout_minutes', 60))}
                    onChange={(e) => updateLocal('session_timeout_minutes', Number(e.target.value))}
                    min={5}
                    max={1440}
                    className="w-24 h-10 px-3.5 bg-[#141414] border border-[#2f2f2f] rounded-lg text-sm text-white text-right font-['JetBrains_Mono'] focus:outline-none focus:border-[#00D9FF] transition-colors"
                  />
                </SettingCard>
                <SettingCard
                  label="Default Language"
                  description="Default language for AI and system responses"
                >
                  <select
                    value={String(getLocal('default_language', 'zh-CN'))}
                    onChange={(e) => updateLocal('default_language', e.target.value)}
                    className="h-10 px-3.5 bg-[#141414] border border-[#2f2f2f] rounded-lg text-sm text-white focus:outline-none focus:border-[#00D9FF] transition-colors"
                  >
                    <option value="zh-CN">Chinese (Simplified)</option>
                    <option value="en">English</option>
                    <option value="zh-TW">Chinese (Traditional)</option>
                  </select>
                </SettingCard>
              </div>
            )}

            {/* AI Config tab */}
            {activeTab === 'ai' && (
              <div className="bg-[#0A0A0A] border border-[#2f2f2f] rounded-[10px] overflow-hidden">
                <div className="px-5 py-4 border-b border-[#2f2f2f]">
                  <h3 className="text-[18px] font-semibold text-white font-['Space_Grotesk']">AI Configuration</h3>
                </div>
                <SettingCard
                  label="Turnstile Enabled"
                  description="Require Turnstile verification for new users"
                >
                  <Toggle
                    value={!!getLocal('turnstile_enabled', false)}
                    onChange={(v) => updateLocal('turnstile_enabled', v)}
                  />
                </SettingCard>
                <SettingCard
                  label="Turnstile Site Key"
                  description="Public site key for the Turnstile widget"
                >
                  <input
                    type="text"
                    value={String(getLocal('turnstile_site_key', ''))}
                    onChange={(e) => updateLocal('turnstile_site_key', e.target.value)}
                    placeholder="0x..."
                    className="w-64 h-10 px-3.5 bg-[#141414] border border-[#2f2f2f] rounded-lg text-sm text-white placeholder:text-[#4a4a4a] font-['JetBrains_Mono'] focus:outline-none focus:border-[#00D9FF] transition-colors"
                  />
                </SettingCard>
              </div>
            )}

            {/* Permissions tab */}
            {activeTab === 'permissions' && (
              <div className="bg-[#0A0A0A] border border-[#2f2f2f] rounded-[10px] overflow-hidden">
                <div className="px-5 py-4 border-b border-[#2f2f2f]">
                  <h3 className="text-[18px] font-semibold text-white font-['Space_Grotesk']">Permissions</h3>
                </div>
                <SettingCard
                  label="Media Cache TTL (days)"
                  description="How long media files are cached before automatic cleanup"
                >
                  <input
                    type="number"
                    value={String(getLocal('media_cache_days', 7))}
                    onChange={(e) => updateLocal('media_cache_days', Number(e.target.value))}
                    min={1}
                    max={90}
                    className="w-24 h-10 px-3.5 bg-[#141414] border border-[#2f2f2f] rounded-lg text-sm text-white text-right font-['JetBrains_Mono'] focus:outline-none focus:border-[#00D9FF] transition-colors"
                  />
                </SettingCard>
                <SettingCard
                  label="Missed Knowledge Update Hour"
                  description="Hour of day (0-23 UTC) to run the missed knowledge analysis"
                >
                  <input
                    type="number"
                    value={String(getLocal('missed_knowledge_update_hour', 3))}
                    onChange={(e) => updateLocal('missed_knowledge_update_hour', Number(e.target.value))}
                    min={0}
                    max={23}
                    className="w-24 h-10 px-3.5 bg-[#141414] border border-[#2f2f2f] rounded-lg text-sm text-white text-right font-['JetBrains_Mono'] focus:outline-none focus:border-[#00D9FF] transition-colors"
                  />
                </SettingCard>
              </div>
            )}

            {/* TMDB Keys tab */}
            {activeTab === 'tmdb' && <TmdbKeysTab />}

            {/* Save button */}
            <div className="mt-6 flex justify-end">
              <button
                onClick={handleSave}
                disabled={!hasChanges || saveMutation.isPending}
                className="inline-flex items-center gap-2 px-5 py-2.5 bg-[#00D9FF] text-black text-sm font-medium rounded-lg hover:opacity-90 transition-opacity disabled:opacity-30"
              >
                {saveMutation.isPending ? (
                  <Loader2 className="w-4 h-4 animate-spin" />
                ) : (
                  <Save className="w-4 h-4" />
                )}
                {saveMutation.isPending ? 'Saving...' : 'Save Settings'}
              </button>
            </div>

            {saveMutation.isSuccess && (
              <p className="mt-3 text-xs text-[#059669] text-right">Settings saved successfully.</p>
            )}
            {saveMutation.isError && (
              <p className="mt-3 text-xs text-[#FF4444] text-right">
                Failed to save: {(saveMutation.error as Error)?.message || 'Unknown error'}
              </p>
            )}

            {/* Version Info */}
            <VersionInfoCard />
          </>
        )}
      </div>
    </div>
  );
}
