import { useEffect, useState } from 'react'
import { getHealth } from '../services/api.js'
import {
  CheckCircle2,
  XCircle,
  Loader2,
  Database,
  Brain,
  TrendingUp,
  MessageSquare,
} from 'lucide-react'

// ── Backend status badge ──────────────────────────────────────────────────────

function StatusBadge({ status }) {
  if (status === 'loading') {
    return (
      <span className="flex items-center gap-1.5 text-xs text-slate-400">
        <Loader2 size={13} className="animate-spin" /> Checking…
      </span>
    )
  }
  if (status === 'ok') {
    return (
      <span className="badge-green">
        <CheckCircle2 size={12} /> Online
      </span>
    )
  }
  return (
    <span className="badge-red">
      <XCircle size={12} /> Offline
    </span>
  )
}

// ── Upcoming-feature card ─────────────────────────────────────────────────────

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

// ── Dashboard page ────────────────────────────────────────────────────────────

export default function Dashboard() {
  const [health, setHealth] = useState({ status: 'loading', data: null })

  useEffect(() => {
    getHealth()
      .then((data) => setHealth({ status: 'ok', data }))
      .catch(() => setHealth({ status: 'error', data: null }))
  }, [])

  return (
    <div className="flex flex-col gap-6">
      {/* ── Page heading ─────────────────────────────────────────────────── */}
      <div>
        <h2 className="text-xl font-bold text-white">
          LLM-Based Sentiment Analysis &amp; Sales Forecasting
        </h2>
        <p className="text-sm text-slate-500 mt-1">
          Final Year Project — Phase 1: Project Foundation
        </p>
      </div>

      {/* ── Backend health card ───────────────────────────────────────────── */}
      <div className="card flex items-start justify-between gap-4">
        <div className="flex flex-col gap-1">
          <p className="text-xs text-slate-500 uppercase tracking-wider font-medium">
            Backend Status
          </p>
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
              Could not reach the FastAPI backend. Make sure it is running on port 8000.
            </p>
          )}
        </div>

        {/* Endpoint info */}
        <div className="bg-surface-raised border border-surface-border rounded-lg px-3 py-2 text-xs font-mono text-slate-400 shrink-0">
          GET /api/health
        </div>
      </div>

      {/* ── Architecture overview ─────────────────────────────────────────── */}
      <div className="card">
        <h3 className="text-sm font-semibold text-white mb-3">System Architecture</h3>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3 text-center text-xs text-slate-400">
          {[
            { label: 'React + Vite', sub: 'Frontend' },
            { label: 'FastAPI',      sub: 'Backend' },
            { label: 'MongoDB Atlas',sub: 'Database' },
            { label: 'Ollama LLM',   sub: 'AI Engine' },
          ].map(({ label, sub }) => (
            <div key={label} className="bg-surface-raised border border-surface-border rounded-lg p-3">
              <p className="text-white font-medium">{label}</p>
              <p className="text-slate-500 text-[11px] mt-0.5">{sub}</p>
            </div>
          ))}
        </div>
      </div>

      {/* ── Upcoming features ─────────────────────────────────────────────── */}
      <div>
        <p className="text-xs text-slate-500 uppercase tracking-wider font-medium mb-3">
          Upcoming Phases
        </p>
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
          <FeatureCard
            icon={MessageSquare}
            title="Multi-Model Sentiment Analysis"
            description="Analyse customer reviews using llama3.1:8b, qwen2.5:7b, and gemma3:4b via Ollama."
            phase="Phase 3"
            color="bg-brand"
          />
          <FeatureCard
            icon={TrendingUp}
            title="Sales Forecasting (SARIMA/SARIMAX)"
            description="Time-series forecasting using statsmodels SARIMA and SARIMAX with sentiment features."
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
          <FeatureCard
            icon={Database}
            title="MongoDB Integration"
            description="Store and query review data, sentiment scores, and forecast results from MongoDB Atlas."
            phase="Phase 2"
            color="bg-accent-amber"
          />
        </div>
      </div>
    </div>
  )
}
