import { useState, useEffect } from 'react'
import { getResearchSummary } from '../services/api'
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer, PieChart, Pie, Cell } from 'recharts'
import { MessageSquare, Layers } from 'lucide-react'

export default function Sentiment() {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    getResearchSummary()
      .then((res) => {
        setData(res.data)
        setLoading(false)
      })
      .catch((err) => {
        console.error(err)
        setLoading(false)
      })
  }, [])

  if (loading || !data) {
    return (
      <div className="flex items-center justify-center h-full">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-brand"></div>
      </div>
    )
  }

  const llm = data.llm_sentiment_stats
  
  // Data for Model Distribution Bar Chart
  const modelDistData = [
    {
      name: 'Llama 3.1 8B',
      Positive: llm['llama3.1:8b'].positive_count,
      Neutral: llm['llama3.1:8b'].neutral_count,
      Negative: llm['llama3.1:8b'].negative_count,
    },
    {
      name: 'Qwen 2.5 7B',
      Positive: llm['qwen2.5:7b'].positive_count,
      Neutral: llm['qwen2.5:7b'].neutral_count,
      Negative: llm['qwen2.5:7b'].negative_count,
    },
    {
      name: 'Gemma 3 4B',
      Positive: llm['gemma3:4b'].positive_count,
      Neutral: llm['gemma3:4b'].neutral_count,
      Negative: llm['gemma3:4b'].negative_count,
    },
  ]

  // Data for Ensemble Distribution Pie Chart
  const ens = data.ensemble_stats
  const ensembleDistData = [
    { name: 'Positive', value: ens.positive_labels },
    { name: 'Neutral', value: ens.neutral_labels },
    { name: 'Negative', value: ens.negative_labels },
  ]

  const agreementData = [
    { name: 'Unanimous (3)', value: ens.full_agreement_count_3 },
    { name: 'Majority (2)', value: ens.partial_agreement_count_2 },
    { name: 'Split (1)', value: ens.disagreement_count_1 },
  ]

  const COLORS = ['#059669', '#64748b', '#dc2626']
  const AGREE_COLORS = ['#2563eb', '#d97706', '#dc2626']

  const CustomTooltip = ({ active, payload, label }) => {
    if (active && payload && payload.length) {
      return (
        <div className="bg-surface border border-surface-border p-3 rounded-lg shadow-xl">
          <p className="text-white font-medium mb-2">{label}</p>
          {payload.map((entry, idx) => (
            <p key={idx} style={{ color: entry.color }} className="text-sm">
              {entry.name}: {entry.value}
            </p>
          ))}
        </div>
      )
    }
    return null
  }

  return (
    <div className="p-8 max-w-7xl mx-auto space-y-8 animate-in fade-in duration-500">
      
      {/* ── Header ──────────────────────────────────────────────────────── */}
      <div>
        <h1 className="text-2xl font-semibold text-white tracking-tight flex items-center gap-2">
          <MessageSquare className="text-brand" /> Sentiment Analysis Pipeline
        </h1>
        <p className="text-slate-400 text-sm mt-1">
          Review-level sentiment extraction across three local LLMs and majority-voting ensemble results.
        </p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        
        {/* ── Model Distribution ──────────────────────────────────────────── */}
        <div className="card col-span-1 lg:col-span-2 flex flex-col">
          <h2 className="text-base font-medium text-white mb-6">Sentiment Class Distribution by LLM</h2>
          <div className="h-80 w-full">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={modelDistData} margin={{ top: 20, right: 30, left: 20, bottom: 5 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#334155" vertical={false} />
                <XAxis dataKey="name" stroke="#94a3b8" tick={{ fill: '#94a3b8' }} />
                <YAxis stroke="#94a3b8" tick={{ fill: '#94a3b8' }} />
                <Tooltip content={<CustomTooltip />} cursor={{ fill: '#334155', opacity: 0.4 }} />
                <Legend wrapperStyle={{ paddingTop: '20px' }} />
                <Bar dataKey="Positive" fill={COLORS[0]} radius={[4, 4, 0, 0]} />
                <Bar dataKey="Neutral" fill={COLORS[1]} radius={[4, 4, 0, 0]} />
                <Bar dataKey="Negative" fill={COLORS[2]} radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* ── Ensemble Distribution ───────────────────────────────────────── */}
        <div className="card flex flex-col">
          <h2 className="text-base font-medium text-white mb-6 flex items-center gap-2">
            <Layers size={18} className="text-teal-400" /> Ensemble Final Distribution
          </h2>
          <div className="h-64 w-full relative">
            <ResponsiveContainer width="100%" height="100%">
              <PieChart>
                <Pie
                  data={ensembleDistData}
                  cx="50%"
                  cy="50%"
                  innerRadius={60}
                  outerRadius={80}
                  paddingAngle={5}
                  dataKey="value"
                  label={({ name, percent }) => `${name} ${(percent * 100).toFixed(1)}%`}
                  labelLine={false}
                >
                  {ensembleDistData.map((entry, index) => (
                    <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                  ))}
                </Pie>
                <Tooltip content={<CustomTooltip />} />
              </PieChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* ── Model Agreement ─────────────────────────────────────────────── */}
        <div className="card flex flex-col">
          <h2 className="text-base font-medium text-white mb-6">Inter-Model Agreement (N=1,000)</h2>
          <div className="h-64 w-full relative">
            <ResponsiveContainer width="100%" height="100%">
              <PieChart>
                <Pie
                  data={agreementData}
                  cx="50%"
                  cy="50%"
                  innerRadius={60}
                  outerRadius={80}
                  paddingAngle={5}
                  dataKey="value"
                  label={({ name, percent }) => `${name} ${(percent * 100).toFixed(1)}%`}
                  labelLine={false}
                >
                  {agreementData.map((entry, index) => (
                    <Cell key={`cell-${index}`} fill={AGREE_COLORS[index % AGREE_COLORS.length]} />
                  ))}
                </Pie>
                <Tooltip content={<CustomTooltip />} />
              </PieChart>
            </ResponsiveContainer>
          </div>
        </div>

      </div>
    </div>
  )
}
