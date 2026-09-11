import { useEffect, useState } from 'react'
import { getHealth, getDatasetStats } from '../services/api.js'
import {
  CheckCircle2, XCircle, Loader2,
  MessageSquare, ShoppingCart, Package,
  Archive, Calendar, Brain, TrendingUp,
} from 'lucide-react'

// ── Reusable sub-components ───────────────────────────────────────────────────

function StatusBadge({ status }) {
  if (status === 'loading') return (
    <span className="flex items-center gap-1.5 text-xs text-slate-400">
      <Loader2 size={13} className="animate-spin" /> Checking…
    </span>
  )
  if (status === 'ok') return (
    <span className="badge-green"><CheckCircle2 size={12} /> Online</span>
  )
  return (
    <span className="badge-red"><XCircle size={12} /> Offline</span>
  )
}

function DbBadge({ status }) {
  if (status === 'connected') return (
    <span className="badge-green"><CheckCircle2 size={12} /> Connected</span>
  )
  if (status === null) return (
    <span className="flex items-center gap-1.5 text-xs text-slate-400">
      <Loader2 size={13} className="animate-spin" /> Checking…
    </span>
  )
  return (
    <span className="badge-red"><XCircle size={12} /> Unreachable</span>
  )
}

function StatCard({ icon: Icon, label, value, sub, color = 'text-brand-light' }) {
  return (
    <div className="card flex flex-col gap-2">
      <div className="flex items-center gap-2">
        <Icon size={15} className={color} />
        <p className="text-xs text-slate-500 uppercase tracking-wider font-medium">{label}</p>
      </div>
      <p className="text-2xl font-bold text-white">
        {value ?? <span className="text-slate-600">—</span>}
      </p>
      {sub && <p className="text-xs text-slate-500">{sub}</p>}
    </div>
  )
}

function FeatureCard({ icon: Icon, title, description, phase, color }) {
  return (
    <div className="card flex flex-col gap-3">
      <div className={`w-10 h-10 rounded-lg flex items-center justify-center ${color}`}>
        <Icon size={20} className="text-white" />
      </div>
      <div>
        <h3 className="text-sm font-semibold text-white">{title}</h3>
        <p className="text-xs text-slate-500 mt-0.5 leading-relaxed">{description}</p>
      </div>
      <span className="badge-brand self-start">{phase}</span>
    </div>
  )
}

// ── Dashboard ─────────────────────────────────────────────────────────────────

export default function Dashboard() {
  const [health, setHealth] = useState({ status: 'loading', data: null })
  const [stats,  setStats]  = useState({ loading: true, data: null, error: null })

  useEffect(() => {
    getHealth()
      .then((data) => setHealth({ status: 'ok', data }))
      .catch(() => setHealth({ status: 'error', data: null }))

    getDatasetStats()
      .then((data) => setStats({ loading: false, data, error: null }))
      .catch((err) => setStats({ loading: false, data: null, error: err.message }))
  }, [])

  const s = stats.data

  return (
    <div className="flex flex-col gap-6">
      {/* Page heading */}
      <div>
        <h2 className="text-xl font-bold text-white">
          LLM-Based Sentiment Analysis &amp; Sales Forecasting
        </h2>
        <p className="text-sm text-slate-500 mt-1">
          Final Year Project — Phase 2: Data Ingestion &amp; MongoDB Integration
        </p>
      </div>

      {/* System status row */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div className="card flex items-start justify-between gap-4">
          <div className="flex flex-col gap-1">
            <p className="text-xs text-slate-500 uppercase tracking-wider font-medium">Backend API</p>
            <div className="flex items-center gap-3 mt-1">
              <StatusBadge status={health.status} />
              {health.data && (
                <span className="text-xs text-slate-500 font-mono">
                  {health.data.app} v{health.data.version}
                </span>
              )}
            </div>
            {health.status === 'error' && (
              <p className="text-xs text-rose-400 mt-1">
                Cannot reach FastAPI backend on port 8000.
              </p>
            )}
          </div>
          <div className="bg-surface-raised border border-surface-border rounded-lg px-3 py-2 text-xs font-mono text-slate-400 shrink-0">
            GET /api/health
          </div>
        </div>

        <div className="card flex items-start justify-between gap-4">
          <div className="flex flex-col gap-1">
            <p className="text-xs text-slate-500 uppercase tracking-wider font-medium">MongoDB Atlas</p>
            <div className="flex items-center gap-3 mt-1">
              <DbBadge status={health.data?.database ?? null} />
            </div>
          </div>
          <div className="bg-surface-raised border border-surface-border rounded-lg px-3 py-2 text-xs font-mono text-slate-400 shrink-0">
            fyp_db
          </div>
        </div>
      </div>

      {/* Live stats grid */}
      <div>
        <p className="text-xs text-slate-500 uppercase tracking-wider font-medium mb-3">
          Dataset Overview
        </p>

        {stats.loading && (
          <div className="flex items-center gap-2 text-sm text-slate-500">
            <Loader2 size={14} className="animate-spin" /> Loading statistics…
          </div>
        )}

        {stats.error && (
          <div className="card border-rose-500/20 bg-rose-500/5">
            <p className="text-xs text-rose-400">
              Could not load statistics. Make sure the dataset has been imported
              (<code className="font-mono">POST /api/dataset/import</code>).
            </p>
          </div>
        )}

        {s && (
          <div className="grid grid-cols-2 md:grid-cols-3 xl:grid-cols-4 gap-4">
            <StatCard
              icon={MessageSquare} label="Total Reviews"
              value={s.review_count.toLocaleString()}
              sub={`${s.unique_products_reviews} unique products`}
              color="text-brand-light"
            />
            <StatCard
              icon={ShoppingCart} label="Purchase Transactions"
              value={s.sales_transaction_count.toLocaleString()}
              sub={`${s.unique_products_sales} unique products`}
              color="text-accent-teal"
            />
            <StatCard
              icon={Package} label="Total Products"
              value={s.unique_products_total.toLocaleString()}
              sub={`${s.product_overlap_count} overlap (reviews ∩ sales)`}
              color="text-accent-purple"
            />
            <StatCard
              icon={Archive} label="Total Quantity Sold"
              value={s.total_purchase_quantity.toLocaleString()}
              sub={`avg ${s.avg_purchases_per_product} purchases/product`}
              color="text-accent-amber"
            />
            <StatCard
              icon={Calendar} label="Review Date Range"
              value={s.review_date_min || '—'}
              sub={`to ${s.review_date_max || '—'}`}
              color="text-brand-light"
            />
            <StatCard
              icon={Calendar} label="Sales Date Range"
              value={s.sales_date_min || '—'}
              sub={`to ${s.sales_date_max || '—'}`}
              color="text-accent-teal"
            />
          </div>
        )}
      </div>

      {/* Upcoming phases */}
      <div>
        <p className="text-xs text-slate-500 uppercase tracking-wider font-medium mb-3">
          Upcoming Phases
        </p>
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
          <FeatureCard
            icon={MessageSquare}
            title="Multi-Model Sentiment Analysis"
            description="Analyse reviews using llama3.1:8b, qwen2.5:7b, and gemma3:4b via Ollama."
            phase="Phase 3"
            color="bg-brand"
          />
          <FeatureCard
            icon={TrendingUp}
            title="Sales Forecasting (SARIMA/SARIMAX)"
            description="Time-series forecasting with statsmodels, using sentiment as an exogenous variable."
            phase="Phase 4"
            color="bg-accent-teal"
          />
          <FeatureCard
            icon={Brain}
            title="Ensemble Scoring"
            description="Combine outputs of three LLMs into a daily sentiment index for improved accuracy."
            phase="Phase 3"
            color="bg-accent-purple"
          />
        </div>
      </div>
    </div>
  )
}
