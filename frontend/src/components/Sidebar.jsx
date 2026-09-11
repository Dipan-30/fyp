import { NavLink } from 'react-router-dom'
import {
  LayoutDashboard,
  MessageSquare,
  Package,
  BarChart2,
  TrendingUp,
  FileBarChart,
  BrainCircuit,
} from 'lucide-react'

const NAV_ITEMS = [
  { to: '/',            label: 'Dashboard',         icon: LayoutDashboard },
  { to: '/reviews',     label: 'Reviews',           icon: MessageSquare },
  { to: '/products',    label: 'Product Analysis',  icon: Package },
  { to: '/sentiment',   label: 'Sentiment',         icon: BarChart2 },
  { to: '/forecasting', label: 'Forecasting',       icon: TrendingUp },
  { to: '/results',     label: 'Forecast Results',  icon: FileBarChart },
]

export default function Sidebar() {
  return (
    <aside className="flex flex-col w-64 shrink-0 bg-surface-card border-r border-surface-border min-h-screen">
      {/* ── Brand ──────────────────────────────────────────────────────── */}
      <div className="flex items-center gap-3 px-5 py-5 border-b border-surface-border">
        <div className="w-8 h-8 rounded-lg bg-brand flex items-center justify-center shrink-0">
          <BrainCircuit size={18} className="text-white" />
        </div>
        <div>
          <p className="text-sm font-semibold text-white leading-tight">SentiForecast</p>
          <p className="text-[10px] text-slate-500 leading-tight">AI Analytics Dashboard</p>
        </div>
      </div>

      {/* ── Navigation ─────────────────────────────────────────────────── */}
      <nav className="flex flex-col gap-1 px-3 pt-4 flex-1">
        <p className="text-[10px] uppercase tracking-widest text-slate-600 px-2 mb-1">
          Navigation
        </p>
        {NAV_ITEMS.map(({ to, label, icon: Icon }) => (
          <NavLink
            key={to}
            to={to}
            end={to === '/'}  // exact match for root
            className={({ isActive }) =>
              `flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-colors ${
                isActive
                  ? 'bg-brand/20 text-brand-light border border-brand/30'
                  : 'text-slate-400 hover:text-slate-200 hover:bg-surface-raised'
              }`
            }
          >
            <Icon size={16} className="shrink-0" />
            {label}
          </NavLink>
        ))}
      </nav>

      {/* ── Footer ─────────────────────────────────────────────────────── */}
      <div className="px-5 py-4 border-t border-surface-border">
        <p className="text-[10px] text-slate-600 leading-relaxed">
          FYP — LLM-Based Sentiment Analysis &amp; Sales Forecasting
        </p>
      </div>
    </aside>
  )
}
