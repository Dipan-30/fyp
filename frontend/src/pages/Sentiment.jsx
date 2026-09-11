import { BarChart2, Brain, Cpu } from 'lucide-react'

const LLM_MODELS = [
  { name: 'llama3.1:8b',  color: 'bg-brand/15 border-brand/30 text-brand-light' },
  { name: 'qwen2.5:7b',   color: 'bg-accent-teal/15 border-accent-teal/30 text-accent-teal' },
  { name: 'gemma3:4b',    color: 'bg-accent-purple/15 border-accent-purple/30 text-accent-purple' },
]

export default function Sentiment() {
  return (
    <div className="flex flex-col gap-6">
      <div>
        <h2 className="text-xl font-bold text-white">Sentiment Analysis</h2>
        <p className="text-sm text-slate-500 mt-1">
          Multi-model LLM sentiment scoring with ensemble aggregation.
        </p>
      </div>

      {/* LLM model cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {LLM_MODELS.map(({ name, color }) => (
          <div key={name} className="card flex flex-col gap-3">
            <div className="flex items-center gap-2">
              <Brain size={15} className="text-slate-400" />
              <p className="text-sm font-semibold text-white font-mono">{name}</p>
            </div>
            <div className={`text-[11px] font-medium px-2.5 py-1 rounded-full border w-fit ${color}`}>
              via Ollama
            </div>
            <div className="h-16 flex items-center justify-center border border-dashed border-surface-border rounded-lg">
              <p className="text-xs text-slate-600">Score distribution placeholder</p>
            </div>
          </div>
        ))}
      </div>

      {/* Ensemble card */}
      <div className="card opacity-40">
        <div className="flex items-center gap-2 mb-2">
          <Cpu size={14} className="text-slate-400" />
          <p className="text-sm font-semibold text-white">Ensemble Sentiment Index</p>
        </div>
        <p className="text-xs text-slate-500 leading-relaxed">
          The ensemble aggregates scores from all three LLMs into a single daily sentiment index,
          which is later used as an exogenous variable in SARIMAX forecasting.
        </p>
      </div>

      <div className="flex flex-col items-center justify-center py-8 text-center">
        <BarChart2 size={28} className="text-brand-light mb-3" />
        <h3 className="text-base font-semibold text-white mb-1">Sentiment pipeline coming in Phase 3</h3>
        <p className="text-sm text-slate-500 max-w-md">
          Ollama must be running locally with the three models pulled.
          This page will trigger analysis, display per-review scores, and show the daily sentiment index chart.
        </p>
      </div>
    </div>
  )
}
