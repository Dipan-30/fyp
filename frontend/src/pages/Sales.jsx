import { useEffect, useState, useCallback } from 'react'
import { getSales } from '../services/api.js'
import { ShoppingCart, Loader2, ChevronLeft, ChevronRight, Calendar, MapPin, Package } from 'lucide-react'

const LIMIT = 15

function EmptyState() {
  return (
    <div className="flex flex-col items-center justify-center py-20 text-center">
      <div className="w-14 h-14 rounded-2xl bg-accent-teal/10 border border-accent-teal/20 flex items-center justify-center mb-4">
        <ShoppingCart size={24} className="text-accent-teal" />
      </div>
      <h3 className="text-base font-semibold text-white mb-1">No sales transactions found</h3>
      <p className="text-sm text-slate-500 max-w-sm">
        Import the dataset first using <code className="font-mono text-brand-light text-xs">POST /api/dataset/import</code>.
      </p>
    </div>
  )
}

function SaleRow({ sale }) {
  return (
    <div className="card flex items-center justify-between gap-4">
      <div className="flex items-center gap-3 min-w-0">
        <div className="w-9 h-9 rounded-lg bg-surface-raised border border-surface-border flex items-center justify-center shrink-0">
          <Package size={14} className="text-slate-400" />
        </div>
        <div className="min-w-0">
          <p className="text-sm font-semibold text-white truncate">{sale.product_name}</p>
          <p className="text-xs text-slate-500 font-mono">TXN {sale.transaction_id} · Product {sale.product_id}</p>
          <p className="text-xs text-slate-600">{sale.product_category}</p>
        </div>
      </div>

      <div className="flex items-center gap-5 shrink-0 text-right">
        <div>
          <p className="text-sm font-semibold text-white">×{sale.quantity}</p>
          <p className="text-[10px] text-slate-500">Qty</p>
        </div>
        <div>
          <p className="text-sm font-semibold text-white">${sale.purchase_price.toFixed(2)}</p>
          <p className="text-[10px] text-slate-500">Price</p>
        </div>
        <div className="text-xs text-slate-500 flex flex-col items-end gap-0.5">
          <span className="flex items-center gap-1">
            <Calendar size={10} /> {sale.purchase_date}
          </span>
          <span className="flex items-center gap-1">
            <MapPin size={10} /> {sale.country}
          </span>
        </div>
      </div>
    </div>
  )
}

function Pagination({ page, totalPages, onPageChange }) {
  if (totalPages <= 1) return null
  return (
    <div className="flex items-center justify-center gap-3 mt-2">
      <button
        onClick={() => onPageChange(page - 1)}
        disabled={page <= 1}
        className="w-8 h-8 flex items-center justify-center rounded-lg border border-surface-border text-slate-400
                   hover:text-white hover:bg-surface-raised disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
      >
        <ChevronLeft size={15} />
      </button>
      <span className="text-xs text-slate-400">
        Page {page} of {totalPages}
      </span>
      <button
        onClick={() => onPageChange(page + 1)}
        disabled={page >= totalPages}
        className="w-8 h-8 flex items-center justify-center rounded-lg border border-surface-border text-slate-400
                   hover:text-white hover:bg-surface-raised disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
      >
        <ChevronRight size={15} />
      </button>
    </div>
  )
}

export default function Sales() {
  const [page, setPage]   = useState(1)
  const [state, setState] = useState({ loading: true, data: null, error: null })

  const fetchSales = useCallback((p) => {
    setState((prev) => ({ ...prev, loading: true, error: null }))
    getSales({ page: p, limit: LIMIT })
      .then((data) => setState({ loading: false, data, error: null }))
      .catch((err) => setState({ loading: false, data: null, error: err.message }))
  }, [])

  useEffect(() => { fetchSales(page) }, [page, fetchSales])

  const transactions = state.data?.sales      ?? []
  const totalPages   = state.data?.total_pages ?? 1
  const total        = state.data?.total       ?? 0

  return (
    <div className="flex flex-col gap-5">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-xl font-bold text-white">Sales Transactions</h2>
          <p className="text-sm text-slate-500 mt-1">
            Purchase data from <code className="text-brand-light text-xs font-mono">customer_purchase_data.csv</code>
            {total > 0 && <span className="ml-1">— {total.toLocaleString()} total records</span>}
          </p>
        </div>
        {!state.loading && total > 0 && (
          <span className="text-xs text-slate-500 bg-surface-raised border border-surface-border px-3 py-1.5 rounded-full">
            {total} transactions
          </span>
        )}
      </div>

      {state.loading && (
        <div className="flex items-center gap-2 text-sm text-slate-500">
          <Loader2 size={14} className="animate-spin" /> Loading transactions…
        </div>
      )}

      {state.error && (
        <div className="card border-rose-500/20 bg-rose-500/5">
          <p className="text-xs text-rose-400">Failed to load sales: {state.error}</p>
        </div>
      )}

      {!state.loading && !state.error && transactions.length === 0 && <EmptyState />}

      {transactions.length > 0 && (
        <>
          <div className="flex flex-col gap-3">
            {transactions.map((s) => (
              <SaleRow key={s.transaction_id} sale={s} />
            ))}
          </div>
          <Pagination
            page={page}
            totalPages={totalPages}
            onPageChange={(p) => { setPage(p); fetchSales(p) }}
          />
        </>
      )}
    </div>
  )
}
