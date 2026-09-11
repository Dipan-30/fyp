import { MessageSquare, Upload, Filter, Search } from 'lucide-react'

function EmptyState({ icon: Icon, title, description, phase }) {
  return (
    <div className="flex flex-col items-center justify-center py-20 text-center">
      <div className="w-16 h-16 rounded-2xl bg-brand/10 border border-brand/20 flex items-center justify-center mb-4">
        <Icon size={28} className="text-brand-light" />
      </div>
      <h3 className="text-base font-semibold text-white mb-1">{title}</h3>
      <p className="text-sm text-slate-500 max-w-sm leading-relaxed">{description}</p>
      <span className="badge-brand mt-4">{phase}</span>
    </div>
  )
}

export default function Reviews() {
  return (
    <div className="flex flex-col gap-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-xl font-bold text-white">Customer Reviews</h2>
          <p className="text-sm text-slate-500 mt-1">
            Browse and manage customer review data from <code className="text-brand-light text-xs font-mono">customer_reviews_data.csv</code>
          </p>
        </div>
      </div>

      {/* Placeholder controls */}
      <div className="flex gap-3">
        <div className="card flex items-center gap-2 flex-1 opacity-40 cursor-not-allowed">
          <Search size={14} className="text-slate-500" />
          <span className="text-sm text-slate-500">Search reviews…</span>
        </div>
        <button disabled className="btn-primary opacity-40 cursor-not-allowed">
          <Filter size={14} /> Filter
        </button>
        <button disabled className="btn-primary opacity-40 cursor-not-allowed">
          <Upload size={14} /> Import CSV
        </button>
      </div>

      <EmptyState
        icon={MessageSquare}
        title="Review data will appear here"
        description="In Phase 2, the customer_reviews_data.csv file will be processed and loaded into MongoDB. Reviews will be displayed, searchable, and filterable here."
        phase="Coming in Phase 2"
      />
    </div>
  )
}
