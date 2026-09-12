import { useLocation } from 'react-router-dom'

// Map pathnames to human-readable page titles
const PAGE_TITLES = {
  '/':            'Dashboard',
  '/reviews':     'Reviews',
  '/sales':       'Sales Transactions',
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
      </div>
    </header>
  )
}
