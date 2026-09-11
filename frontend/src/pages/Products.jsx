import { useEffect, useState } from 'react'
import { getProducts } from '../services/api.js'
import { Package, Loader2, ShoppingCart, MessageSquare, Archive } from 'lucide-react'

function EmptyState() {
  return (
    <div className="flex flex-col items-center justify-center py-20 text-center">
      <div className="w-14 h-14 rounded-2xl bg-brand/10 border border-brand/20 flex items-center justify-center mb-4">
        <Package size={24} className="text-brand-light" />
      </div>
      <h3 className="text-base font-semibold text-white mb-1">No products found</h3>
      <p className="text-sm text-slate-500 max-w-sm">
        Import the dataset first using <code className="font-mono text-brand-light text-xs">POST /api/dataset/import</code>.
      </p>
    </div>
  )
}

function ProductRow({ product }) {
  return (
    <div className="card flex items-center justify-between gap-4 py-4">
      <div className="flex items-center gap-3 min-w-0">
        <div className="w-9 h-9 rounded-lg bg-surface-raised border border-surface-border flex items-center justify-center shrink-0">
          <Package size={15} className="text-slate-400" />
        </div>
        <div className="min-w-0">
          <p className="text-sm font-semibold text-white truncate">
            {product.product_name ?? <span className="text-slate-500 italic">No name (reviews-only)</span>}
          </p>
          <p className="text-xs text-slate-500 font-mono">ID: {product.product_id}</p>
          {product.product_category && (
            <p className="text-xs text-slate-600">{product.product_category}</p>
          )}
        </div>
      </div>

      <div className="flex items-center gap-6 shrink-0">
        <div className="text-center">
          <div className="flex items-center gap-1 text-brand-light justify-center">
            <MessageSquare size={12} />
            <span className="text-sm font-semibold text-white">{product.review_count}</span>
          </div>
          <p className="text-[10px] text-slate-500 mt-0.5">Reviews</p>
        </div>
        <div className="text-center">
          <div className="flex items-center gap-1 text-accent-teal justify-center">
            <ShoppingCart size={12} />
            <span className="text-sm font-semibold text-white">{product.purchase_count}</span>
          </div>
          <p className="text-[10px] text-slate-500 mt-0.5">Purchases</p>
        </div>
        <div className="text-center">
          <div className="flex items-center gap-1 text-accent-amber justify-center">
            <Archive size={12} />
            <span className="text-sm font-semibold text-white">{product.total_quantity}</span>
          </div>
          <p className="text-[10px] text-slate-500 mt-0.5">Qty</p>
        </div>
      </div>
    </div>
  )
}

export default function Products() {
  const [state, setState] = useState({ loading: true, data: null, error: null })

  useEffect(() => {
    getProducts()
      .then((data) => setState({ loading: false, data, error: null }))
      .catch((err) => setState({ loading: false, data: null, error: err.message }))
  }, [])

  const products = state.data?.products ?? []

  return (
    <div className="flex flex-col gap-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-xl font-bold text-white">Product Analysis</h2>
          <p className="text-sm text-slate-500 mt-1">
            Per-product review and purchase summary. Sentiment scores will be added in Phase 3.
          </p>
        </div>
        {state.data && (
          <span className="text-xs text-slate-500 bg-surface-raised border border-surface-border px-3 py-1.5 rounded-full">
            {state.data.total} products
          </span>
        )}
      </div>

      {state.loading && (
        <div className="flex items-center gap-2 text-sm text-slate-500">
          <Loader2 size={14} className="animate-spin" /> Loading products…
        </div>
      )}

      {state.error && (
        <div className="card border-rose-500/20 bg-rose-500/5">
          <p className="text-xs text-rose-400">Failed to load products: {state.error}</p>
        </div>
      )}

      {!state.loading && !state.error && products.length === 0 && <EmptyState />}

      {products.length > 0 && (
        <div className="flex flex-col gap-3">
          {products.map((p) => (
            <ProductRow key={p.product_id} product={p} />
          ))}
        </div>
      )}
    </div>
  )
}
