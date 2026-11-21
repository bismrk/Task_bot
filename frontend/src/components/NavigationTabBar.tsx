import React from 'react';
import type { AppTab } from '../api/types';
import { CheckSquare, Calendar, BarChart3, Settings } from 'lucide-react';

interface NavigationTabBarProps {
  activeTab: AppTab;
  onTabChange: (tab: AppTab) => void;
}

interface TabItemConfig {
  id: AppTab;
  label: string;
  icon: React.ComponentType<{ className?: string }>;
  disabled?: boolean;
}

const TABS: TabItemConfig[] = [
  { id: 'today', label: 'Сьогодні', icon: CheckSquare },
  { id: 'calendar', label: 'Календар', icon: Calendar },
  { id: 'analytics', label: 'Аналітика', icon: BarChart3 },
  { id: 'settings', label: 'Налаштування', icon: Settings },
];

export const NavigationTabBar: React.FC<NavigationTabBarProps> = ({
  activeTab,
  onTabChange,
}) => {
  const handleTabClick = (tabId: AppTab, disabled?: boolean) => {
    if (disabled) return;
    try {
      window.Telegram?.WebApp?.HapticFeedback?.impactOccurred('light');
    } catch {
      // ignore outside Telegram environment
    }
    onTabChange(tabId);
  };

  return (
    <nav
      role="tablist"
      aria-label="Основна навігація"
      className="w-full grid grid-cols-4 items-center gap-1 p-1.5 rounded-2xl bg-secondary/80 border border-black/5 dark:border-white/5 backdrop-blur-md shadow-sm"
    >
      {TABS.map((tab) => {
        const Icon = tab.icon;
        const isActive = activeTab === tab.id;
        const isDisabled = tab.disabled;

        return (
          <button
            key={tab.id}
            type="button"
            role="tab"
            aria-selected={isActive}
            aria-disabled={isDisabled}
            disabled={isDisabled}
            onClick={() => handleTabClick(tab.id, isDisabled)}
            className={`relative flex flex-col items-center justify-center py-2 px-1 rounded-xl transition-all duration-200 ${
              isDisabled
                ? 'opacity-40 cursor-not-allowed text-muted'
                : isActive
                ? 'bg-background text-primary shadow-xs font-semibold'
                : 'text-muted hover:text-foreground hover:bg-background/40 cursor-pointer'
            }`}
          >
            <Icon className={`w-4 h-4 mb-1 transition-transform ${isActive ? 'scale-110' : ''}`} />
            <span className="text-[10px] leading-tight tracking-tight truncate max-w-full">
              {tab.label}
            </span>
            {isActive && (
              <span className="absolute -bottom-0.5 w-1 h-1 rounded-full bg-primary" />
            )}
          </button>
        );
      })}
    </nav>
  );
};
