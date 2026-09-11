import { useLocation } from 'react-router-dom'
import { Bell, Activity } from 'lucide-react'

// Map pathnames to human-readable page titles
const PAGE_TITLES = {
  '/':            'Dashboard',
  '/reviews':     'Reviews',
  '/products':    'Product Analysis',
  '/sentiment':   'Sentiment Analysis',
  '/forecasting': 'Forecasting',
  '/results':     'Forecast Results',
}

export default function Header() {
  const { pathname } = useLocation()
  const title = PAGE_TITLES[pathname] ?? 'Dashboard'

  return (
    <header className="flex items-center justify-between px-6 py-4 border-b border-surface-border bg-surface-card">
      {/* Page title */}
      <div>
        <h1 className="text-base font-semibold text-white">{title}</h1>
        <p className="text-xs text-slate-500">LLM-Based Sentiment &amp; Sales Forecasting</p>
      </div>

      {/* Right-side controls */}
      <div className="flex items-center gap-3">
        {/* System status pill */}
        <div className="flex items-center gap-1.5 text-xs text-slate-400 bg-surface-raised border border-surface-border px-3 py-1.5 rounded-full">
          <Activity size={12} className="text-emerald-400" />
          Phase 1
        </div>

        {/* Placeholder notification icon */}
        <button
          aria-label="Notifications"
          className="w-8 h-8 flex items-center justify-center rounded-lg text-slate-400 hover:text-slate-200 hover:bg-surface-raised transition-colors"
        >
          <Bell size={16} />
        </button>
      </div>
    </header>
  )
}
