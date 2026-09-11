import { Package, BarChart2 } from 'lucide-react'

export default function Products() {
  return (
    <div className="flex flex-col gap-6">
      <div>
        <h2 className="text-xl font-bold text-white">Product Analysis</h2>
        <p className="text-sm text-slate-500 mt-1">
          Per-product sentiment breakdown and purchase trend analysis.
        </p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {['Top Sentiment Products', 'Lowest Rated Products', 'Purchase vs Sentiment'].map((title) => (
          <div key={title} className="card opacity-40">
            <div className="flex items-center gap-2 mb-3">
              <BarChart2 size={14} className="text-slate-500" />
              <p className="text-xs font-semibold text-slate-400 uppercase tracking-wider">{title}</p>
            </div>
            <div className="h-24 flex items-center justify-center border border-dashed border-surface-border rounded-lg">
              <p className="text-xs text-slate-600">Chart placeholder</p>
            </div>
          </div>
        ))}
      </div>

      <div className="flex flex-col items-center justify-center py-12 text-center">
        <div className="w-14 h-14 rounded-2xl bg-brand/10 border border-brand/20 flex items-center justify-center mb-4">
          <Package size={24} className="text-brand-light" />
        </div>
        <h3 className="text-base font-semibold text-white mb-1">Product analytics coming soon</h3>
        <p className="text-sm text-slate-500 max-w-md leading-relaxed">
          After sentiment analysis is complete (Phase 3), per-product sentiment scores and
          purchase correlations will be visualised here using Recharts.
        </p>
        <span className="badge-brand mt-4">Coming in Phase 3+</span>
      </div>
    </div>
  )
}
