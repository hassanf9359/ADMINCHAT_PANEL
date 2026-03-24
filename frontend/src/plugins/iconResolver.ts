import * as LucideIcons from 'lucide-react';
import { type LucideIcon } from 'lucide-react';

const iconCache = new Map<string, LucideIcon>();

export function resolveIcon(name: string): LucideIcon {
  if (iconCache.has(name)) {
    return iconCache.get(name)!;
  }

  const icon = (LucideIcons as Record<string, unknown>)[name] as LucideIcon | undefined;
  if (icon && typeof icon === 'function') {
    iconCache.set(name, icon);
    return icon;
  }

  iconCache.set(name, LucideIcons.Puzzle);
  return LucideIcons.Puzzle;
}
