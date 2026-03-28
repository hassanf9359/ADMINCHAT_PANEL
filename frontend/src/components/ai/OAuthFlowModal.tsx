import { useState, useEffect, useRef } from 'react';
import { X, Loader2, ExternalLink, CheckCircle, XCircle } from 'lucide-react';
import type { AuthMethod } from '../../types';
import { getOAuthAuthUrl, exchangeOAuthCode, exchangeClaudeSessionToken } from '../../services/aiOAuthApi';

const PROVIDER_DEFAULTS: Record<string, { provider: string; base_url: string; model: string; api_format: string }> = {
  openai_oauth: { provider: 'openai', base_url: 'https://api.openai.com/v1', model: 'gpt-4o', api_format: 'openai_chat' },
  claude_oauth: { provider: 'anthropic', base_url: 'https://api.anthropic.com/v1', model: 'claude-sonnet-4-20250514', api_format: 'anthropic_responses' },
  claude_session: { provider: 'anthropic', base_url: 'https://api.anthropic.com/v1', model: 'claude-sonnet-4-20250514', api_format: 'anthropic_responses' },
  gemini_oauth: { provider: 'custom', base_url: 'https://generativelanguage.googleapis.com/v1beta', model: 'gemini-2.0-flash', api_format: 'openai_chat' },
};

const CODE_PASTE_HINTS: Record<string, { linkText: string; step2Text: string }> = {
  openai_oauth: {
    linkText: 'Open OpenAI Authorization',
    step2Text: 'After login, you will be redirected to a localhost page that won\'t load. Copy the FULL URL from your browser address bar and paste it below:',
  },
  claude_oauth: {
    linkText: 'Open Claude Authorization',
    step2Text: 'After authorization, Claude will show you a code. Paste it below:',
  },
  gemini_oauth: {
    linkText: 'Open Google Authorization',
    step2Text: 'After login, you will be redirected to a localhost page that won\'t load. Copy the FULL URL from your browser address bar and paste it below:',
  },
};

interface OAuthFlowModalProps {
  authMethod: AuthMethod;
  onClose: () => void;
  onSuccess: () => void;
}

export default function OAuthFlowModal({ authMethod, onClose, onSuccess }: OAuthFlowModalProps) {
  const defaults = PROVIDER_DEFAULTS[authMethod] || PROVIDER_DEFAULTS.openai_oauth;

  const [name, setName] = useState('');
  const [baseUrl, setBaseUrl] = useState(defaults.base_url);
  const [model, setModel] = useState(defaults.model);
  const [apiFormat] = useState(defaults.api_format);
  const [temperature, setTemperature] = useState(0.7);
  const [maxTokens, setMaxTokens] = useState(500);

  // Flow state
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);

  // Code-paste flow (OpenAI / Claude / Gemini)
  const [authUrl, setAuthUrl] = useState('');
  const [oauthState, setOauthState] = useState('');
  const [pastedCode, setPastedCode] = useState('');

  // Claude session token flow
  const [sessionCookie, setSessionCookie] = useState('');

  const timeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  useEffect(() => {
    return () => { if (timeoutRef.current) clearTimeout(timeoutRef.current); };
  }, []);

  const isCodePasteFlow = authMethod === 'openai_oauth' || authMethod === 'claude_oauth' || authMethod === 'gemini_oauth';
  // Claude OAuth/Session proxy doesn't accept temperature
  const supportsTemperature = authMethod !== 'claude_oauth' && authMethod !== 'claude_session';

  const configMeta = {
    name: name.trim(),
    provider: defaults.provider,
    base_url: baseUrl.trim(),
    model: model.trim() || undefined,
    api_format: apiFormat,
    default_params: {
      ...(supportsTemperature ? { temperature } : {}),
      max_tokens: maxTokens,
    },
  };

  // Step 1: Get auth URL
  const startCodePasteFlow = async () => {
    if (!name.trim()) { setError('Name is required'); return; }
    setLoading(true);
    setError(null);
    try {
      const resp = await getOAuthAuthUrl(authMethod, configMeta);
      setAuthUrl(resp.auth_url);
      setOauthState(resp.state);
      setLoading(false);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
      setLoading(false);
    }
  };

  // Step 2: Exchange code/URL
  const submitCode = async () => {
    if (!pastedCode.trim()) { setError('Code or URL is required'); return; }
    setLoading(true);
    setError(null);
    try {
      await exchangeOAuthCode(pastedCode.trim(), oauthState);
      setSuccess(true);
      timeoutRef.current = setTimeout(() => onSuccess(), 500);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
      setLoading(false);
    }
  };

  // Claude session token flow
  const submitSessionToken = async () => {
    if (!name.trim()) { setError('Name is required'); return; }
    if (!sessionCookie.trim()) { setError('Session cookie is required'); return; }
    setLoading(true);
    setError(null);
    try {
      await exchangeClaudeSessionToken({
        session_cookie: sessionCookie.trim(),
        name: name.trim(),
        base_url: baseUrl.trim(),
        model: model.trim() || undefined,
        api_format: apiFormat,
        default_params: { max_tokens: maxTokens },
      });
      setSuccess(true);
      timeoutRef.current = setTimeout(() => onSuccess(), 500);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
      setLoading(false);
    }
  };

  const methodLabels: Record<string, string> = {
    openai_oauth: 'OpenAI',
    claude_oauth: 'Claude',
    claude_session: 'Claude (Session Token)',
    gemini_oauth: 'Gemini',
    api_key: 'API Key',
  };
  const methodLabel = methodLabels[authMethod] || authMethod;
  const hints = CODE_PASTE_HINTS[authMethod];

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm">
      <div className="bg-bg-page border border-border rounded-xl p-6 w-full max-w-lg shadow-2xl max-h-[90vh] overflow-auto">
        <div className="flex items-center justify-between mb-5">
          <h3 className="text-sm font-semibold text-text-primary">
            Add Provider via {methodLabel}
          </h3>
          <button onClick={onClose} className="text-text-muted hover:text-text-primary">
            <X className="w-4 h-4" />
          </button>
        </div>

        {success ? (
          <div className="flex flex-col items-center py-8">
            <CheckCircle className="w-12 h-12 text-green mb-3" />
            <p className="text-sm text-green font-medium">Authentication successful!</p>
          </div>
        ) : (
          <div className="flex flex-col gap-4">
            {/* Common fields */}
            <div>
              <label className="block text-xs text-text-secondary mb-2">Name *</label>
              <input
                type="text"
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder={`My ${methodLabel} Config`}
                className="w-full h-11 px-4 bg-bg-elevated border border-border rounded-lg text-sm text-text-primary placeholder:text-text-placeholder focus:outline-none focus:border-accent transition-colors"
              />
            </div>

            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="block text-xs text-text-secondary mb-2">Base URL</label>
                <input
                  type="text"
                  value={baseUrl}
                  onChange={(e) => setBaseUrl(e.target.value)}
                  className="w-full h-11 px-4 bg-bg-elevated border border-border rounded-lg text-sm text-text-primary font-mono focus:outline-none focus:border-accent transition-colors"
                />
              </div>
              <div>
                <label className="block text-xs text-text-secondary mb-2">Model</label>
                <input
                  type="text"
                  value={model}
                  onChange={(e) => setModel(e.target.value)}
                  className="w-full h-11 px-4 bg-bg-elevated border border-border rounded-lg text-sm text-text-primary font-mono focus:outline-none focus:border-accent transition-colors"
                />
              </div>
            </div>

            <div>
              <label className="block text-xs text-text-secondary mb-2">API Format</label>
              <div className="w-full h-11 px-4 bg-bg-elevated border border-border rounded-lg text-sm text-text-secondary flex items-center font-mono">
                {apiFormat === 'anthropic_responses' ? 'Anthropic Responses (CRS)' : 'OpenAI Chat Completions'}
              </div>
            </div>

            <div className={`grid ${supportsTemperature ? 'grid-cols-2' : 'grid-cols-1'} gap-3`}>
              {supportsTemperature && (
                <div>
                  <label className="block text-xs text-text-secondary mb-2">
                    Temperature: <span className="text-accent font-mono">{temperature.toFixed(2)}</span>
                  </label>
                  <input type="range" min={0} max={2} step={0.05} value={temperature}
                    onChange={(e) => setTemperature(Number(e.target.value))} className="w-full accent-accent" />
                </div>
              )}
              <div>
                <label className="block text-xs text-text-secondary mb-2">
                  Max Tokens: <span className="text-accent font-mono">{maxTokens}</span>
                </label>
                <input type="range" min={50} max={4000} step={50} value={maxTokens}
                  onChange={(e) => setMaxTokens(Number(e.target.value))} className="w-full accent-accent" />
              </div>
            </div>

            {/* Session Token specific: cookie input */}
            {authMethod === 'claude_session' && (
              <div>
                <label className="block text-xs text-text-secondary mb-2">Session Cookie (sessionKey) *</label>
                <textarea
                  value={sessionCookie}
                  onChange={(e) => setSessionCookie(e.target.value)}
                  placeholder="Paste your claude.ai sessionKey cookie value here..."
                  rows={3}
                  className="w-full px-4 py-3 bg-bg-elevated border border-border rounded-lg text-sm text-text-primary placeholder:text-text-placeholder font-mono focus:outline-none focus:border-accent transition-colors resize-none"
                />
                <p className="text-[10px] text-text-muted mt-1">
                  Open claude.ai, inspect cookies, copy the "sessionKey" value.
                </p>
              </div>
            )}

            {/* Code-paste flow: show auth link + code input when URL is ready */}
            {isCodePasteFlow && authUrl && hints && (
              <div className="bg-bg-elevated border border-border rounded-lg p-4 space-y-3">
                <div>
                  <p className="text-xs text-text-secondary mb-2">Step 1: Open the link below and authorize:</p>
                  <a
                    href={authUrl}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="inline-flex items-center gap-1.5 text-sm text-accent hover:underline break-all"
                  >
                    <ExternalLink className="w-3.5 h-3.5 flex-shrink-0" />
                    {hints.linkText}
                  </a>
                </div>
                <div>
                  <p className="text-xs text-text-secondary mb-2">Step 2: {hints.step2Text}</p>
                  <textarea
                    value={pastedCode}
                    onChange={(e) => setPastedCode(e.target.value)}
                    placeholder={authMethod === 'claude_oauth'
                      ? 'Paste authorization code here...'
                      : 'Paste the full URL from your browser address bar here...'}
                    rows={2}
                    className="w-full px-4 py-3 bg-bg-card border border-border rounded-lg text-sm text-text-primary placeholder:text-text-placeholder font-mono focus:outline-none focus:border-accent transition-colors resize-none"
                  />
                </div>
              </div>
            )}

            {/* Error */}
            {error && (
              <div className="flex items-center gap-2 p-3 rounded-lg bg-red/5 border border-red/20">
                <XCircle className="w-4 h-4 text-red flex-shrink-0" />
                <p className="text-xs text-red">{error}</p>
              </div>
            )}

            {/* Action buttons */}
            <div className="flex justify-end gap-3 mt-2">
              <button
                type="button"
                onClick={onClose}
                className="px-4 py-2 text-sm text-text-secondary hover:text-text-primary"
              >
                Cancel
              </button>

              {/* Code-paste flow: Get Link button (before auth URL is shown) */}
              {isCodePasteFlow && !authUrl && (
                <button
                  onClick={startCodePasteFlow}
                  disabled={loading || !name.trim()}
                  className="inline-flex items-center gap-2 px-4 py-2 bg-accent text-black text-sm font-medium rounded-lg hover:opacity-90 disabled:opacity-50"
                >
                  {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : <ExternalLink className="w-4 h-4" />}
                  Get Authorization Link
                </button>
              )}

              {/* Code-paste flow: Exchange Code button (after auth URL is shown) */}
              {isCodePasteFlow && authUrl && (
                <button
                  onClick={submitCode}
                  disabled={loading || !pastedCode.trim()}
                  className="inline-flex items-center gap-2 px-4 py-2 bg-accent text-black text-sm font-medium rounded-lg hover:opacity-90 disabled:opacity-50"
                >
                  {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : <CheckCircle className="w-4 h-4" />}
                  Exchange Code
                </button>
              )}

              {/* Claude session token flow */}
              {authMethod === 'claude_session' && (
                <button
                  onClick={submitSessionToken}
                  disabled={loading || !name.trim() || !sessionCookie.trim()}
                  className="inline-flex items-center gap-2 px-4 py-2 bg-accent text-black text-sm font-medium rounded-lg hover:opacity-90 disabled:opacity-50"
                >
                  {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : <CheckCircle className="w-4 h-4" />}
                  Exchange Token
                </button>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
