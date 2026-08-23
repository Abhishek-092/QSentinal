import React from 'react';
import { Moon, Sun } from 'lucide-react';
import { useTheme } from '../ThemeContext';

export default function ThemeToggle({ className = '' }) {
  const { theme, toggleTheme } = useTheme();
  const isDark = theme === 'dark';

  return (
    <button
      type="button"
      onClick={toggleTheme}
      aria-label={isDark ? 'Switch to light mode' : 'Switch to dark mode'}
      title={isDark ? 'Light mode' : 'Dark mode'}
      className={`flex items-center gap-2 border border-line bg-panel px-3 py-2 text-xs uppercase tracking-widest text-dim transition-all hover:border-neon/50 hover:text-neon ${className}`}
    >
      {isDark ? <Sun size={14} className="text-acid" /> : <Moon size={14} className="text-neon" />}
      {isDark ? 'Light' : 'Dark'}
    </button>
  );
}
