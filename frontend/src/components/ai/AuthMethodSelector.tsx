import { Key, Globe, Cookie } from 'lucide-react';
import type { AuthMethod } from '../../types';

const AUTH_METHODS: {
  value: AuthMethod;
  label: string;
  description: string;
  icon: React.ReactNode;
  iconColor: string;
}[] = [
  {
    value: 'api_key',
    label: 'API Key',
    description: 'Manually enter Base URL and API Key',
    icon: <Key className="w-5 h-5" />,
    iconColor: 'text-[#8a8a8a]',
  },
  {
    value: 'openai_oauth',
    label: 'OpenAI OAuth',
    description: 'Sign in with your OpenAI account',
    icon: <span className="text-sm font-bold">OAI</span>,
    iconColor: 'text-[#059669]',
  },
  {
    value: 'claude_oauth',
    label: 'Claude OAuth',
    description: 'Authorize via Claude (paste code)',
    icon: <span className="text-sm font-bold">CL</span>,
    iconColor: 'text-[#FF8800]',
  },
  {
    value: 'claude_session',
    label: 'Claude Session Token',
    description: 'Paste claude.ai session cookie',
    icon: <Cookie className="w-5 h-5" />,
    iconColor: 'text-[#FF8800]',
  },
  {
    value: 'gemini_oauth',
    label: 'Gemini OAuth',
    description: 'Sign in with your Google account',
    icon: <Globe className="w-5 h-5" />,
    iconColor: 'text-[#8B5CF6]',
  },
];

interface AuthMethodSelectorProps {
  selected: AuthMethod;
  onSelect: (method: AuthMethod) => void;
}

export default function AuthMethodSelector({ selected, onSelect }: AuthMethodSelectorProps) {
  return (
    <div className="grid grid-cols-1 gap-2">
      <label className="block text-xs text-[#8a8a8a] mb-1">Authentication Method</label>
      {AUTH_METHODS.map((method) => (
        <button
          key={method.value}
          type="button"
          onClick={() => onSelect(method.value)}
          className={`flex items-center gap-3 w-full px-4 py-3 rounded-lg border text-left transition-colors ${
            selected === method.value
              ? 'border-[#00D9FF] bg-[#00D9FF]/5'
              : 'border-[#2f2f2f] bg-[#141414] hover:border-[#4a4a4a]'
          }`}
        >
          <div className={`flex items-center justify-center w-8 h-8 rounded-md bg-[#0A0A0A] ${method.iconColor}`}>
            {method.icon}
          </div>
          <div className="flex-1 min-w-0">
            <p className={`text-sm font-medium ${selected === method.value ? 'text-[#00D9FF]' : 'text-[#FFFFFF]'}`}>
              {method.label}
            </p>
            <p className="text-[11px] text-[#6a6a6a] truncate">{method.description}</p>
          </div>
          <div className={`w-4 h-4 rounded-full border-2 flex items-center justify-center ${
            selected === method.value
              ? 'border-[#00D9FF]'
              : 'border-[#4a4a4a]'
          }`}>
            {selected === method.value && (
              <div className="w-2 h-2 rounded-full bg-[#00D9FF]" />
            )}
          </div>
        </button>
      ))}
    </div>
  );
}
