import { useState, useEffect } from 'react'
import { Link } from 'react-router-dom'
import {
  MessageSquare, Package, ShoppingCart, Brain, Cpu, CheckCircle,
  TrendingDown, ArrowRight, ArrowDown, BarChart2, Activity, TrendingUp, Layers
} from 'lucide-react'
import {
  PieChart, Pie, Cell, BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip as RechartsTooltip, Legend, ResponsiveContainer
} from 'recharts'
import { getResearchSummary, getDatasetStats, getProducts } from '../services/api'

// Colors matching the existing theme
const COLORS = {
  positive: '#14b8a6', // teal-500
  neutral: '#64748b',  // slate-500
  negative: '#f43f5e', // rose-500
  brand: '#3b82f6',    // blue-500
}

export default function Dashboard() {
  const [summaryData, setSummaryData] = useState(null)
  const [statsData, setStatsData] = useState(null)
  const [productsData, setProductsData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  useEffect(() => {
    Promise.all([getResearchSummary(), getDatasetStats(), getProducts()])
      .then(([summaryRes, statsRes, productsRes]) => {
        setSummaryData(summaryRes.data)
        setStatsData(statsRes)
        setProductsData(productsRes)
        setLoading(false)
      })
      .catch((err) => {
        setError(err.message)
        setLoading(false)
      })
  }, [])

  if (loading) {
    return (
      <div className="flex items-center justify-center h-full min-h-[50vh]">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-brand"></div>
      </div>
    )
  }

  if (error || !summaryData || !statsData || !productsData) {
    return (
      <div className="flex flex-col items-center justify-center h-full min-h-[50vh] text-center">
        <div className="w-12 h-12 bg-rose-500/10 text-rose-500 rounded-full flex items-center justify-center mb-4">
          <TrendingDown size={24} />
        </div>
        <h3 className="text-lg font-medium text-white mb-2">Unable to load research data</h3>
        <p className="text-slate-400 text-sm max-w-sm">{error || "Data missing"}</p>
        <button 
          onClick={() => window.location.reload()}
          className="mt-4 px-4 py-2 bg-surface-raised border border-surface-border text-slate-300 rounded-lg hover:bg-surface-card transition-colors"
        >
          Retry
        </button>
      </div>
    )
  }

  const {
    llm_sentiment_stats: llm,
    ensemble_stats: ens
  } = summaryData

  const totalModelsRun = 
    (llm['llama3.1:8b']?.total_records || 0) + 
    (llm['qwen2.5:7b']?.total_records || 0) + 
    (llm['gemma3:4b']?.total_records || 0)

  // Sentiment Pie Chart Data
  const pieData = [
    { name: 'Positive', value: ens.positive_labels, color: COLORS.positive },
    { name: 'Neutral', value: ens.neutral_labels, color: COLORS.neutral },
    { name: 'Negative', value: ens.negative_labels, color: COLORS.negative },
  ]

  // Model comparison bar chart data
  const modelCompData = [
    {
      name: 'Llama 3.1 8B',
      pos: llm['llama3.1:8b']?.positive_pct || 0,
      neu: llm['llama3.1:8b']?.neutral_pct || 0,
      neg: llm['llama3.1:8b']?.negative_pct || 0,
    },
    {
      name: 'Qwen 2.5 7B',
      pos: llm['qwen2.5:7b']?.positive_pct || 0,
      neu: llm['qwen2.5:7b']?.neutral_pct || 0,
      neg: llm['qwen2.5:7b']?.negative_pct || 0,
    },
    {
      name: 'Gemma 3 4B',
      pos: llm['gemma3:4b']?.positive_pct || 0,
      neu: llm['gemma3:4b']?.neutral_pct || 0,
      neg: llm['gemma3:4b']?.negative_pct || 0,
    }
  ]

  return (
    <div className="p-4 md:p-8 max-w-7xl mx-auto space-y-10 animate-in fade-in duration-500">
      
      {/* ── Header ──────────────────────────────────────────────────────── */}
      <div className="border-b border-surface-border pb-6">
        <h1 className="text-2xl font-semibold text-white tracking-tight">
          LLM-Based Product Intelligence System
        </h1>
        <p className="text-slate-400 text-sm mt-2">
          Overview of customer sentiment extraction and global project metrics.
        </p>
      </div>

      {/* ── PRODUCT DETAILS CTA ─────────────────────────────────────────── */}
      <div className="bg-gradient-to-r from-teal-500/20 to-surface-card border border-teal-500/30 rounded-xl p-8 flex flex-col md:flex-row items-center justify-between gap-6 shadow-lg shadow-teal-500/5 mb-6">
        <div>
          <h2 className="text-2xl font-semibold text-white mb-2 tracking-tight">PRODUCT DETAILS</h2>
          <p className="text-slate-300 max-w-xl leading-relaxed">
            Explore sales performance, customer sentiment, and purchase recommendations for all 100 products.
          </p>
        </div>
        <Link 
          to="/products" 
          className="shrink-0 bg-teal-500 hover:bg-teal-400 text-white font-medium py-3 px-8 rounded-lg transition-colors flex items-center gap-2 shadow-sm"
        >
          View Products <ArrowRight size={18} />
        </Link>
      </div>

      {/* ── PRODUCT ANALYSIS CTA ────────────────────────────────────────── */}
      <div className="bg-gradient-to-r from-brand/20 to-surface-card border border-brand/30 rounded-xl p-8 flex flex-col md:flex-row items-center justify-between gap-6 shadow-lg shadow-brand/5">
        <div>
          <h2 className="text-2xl font-semibold text-white mb-2 tracking-tight">PRODUCT ANALYSIS</h2>
          <p className="text-slate-300 max-w-xl leading-relaxed">
            Select a product to explore customer sentiment, sales history, purchase recommendation and future sales prediction.
          </p>
        </div>
        <Link 
          to="/product-analysis" 
          className="shrink-0 bg-brand hover:bg-brand-light text-white font-medium py-3 px-8 rounded-lg transition-colors flex items-center gap-2 shadow-sm"
        >
          Analyze Product <ArrowRight size={18} />
        </Link>
      </div>

      {/* ── KPI SECTION ─────────────────────────────────────────────────── */}
      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-4">
        <KPICard icon={<Package size={18} />} label="Total Products" value={statsData.unique_products_total?.toLocaleString() || 0} />
        <KPICard icon={<MessageSquare size={18} />} label="Total Reviews" value={statsData.review_count?.toLocaleString() || 0} />
        <KPICard icon={<ShoppingCart size={18} />} label="Total Sales Units" value={statsData.total_purchase_quantity?.toLocaleString() || 0} />
        <KPICard icon={<Brain size={18} />} label="LLM Models" value={Object.keys(llm).length} />
        <KPICard icon={<Cpu size={18} />} label="Model Inferences" value={totalModelsRun.toLocaleString()} />
        <KPICard icon={<CheckCircle size={18} />} label="Ensemble Agreement" value={`${ens.full_agreement_pct?.toFixed(1)}%`} />
      </div>

      {/* ── RESEARCH PIPELINE ───────────────────────────────────────────── */}
      <div>
        <h2 className="text-lg font-medium text-white mb-4">Research Pipeline</h2>
        <div className="flex flex-col lg:flex-row items-center justify-between bg-surface-card border border-surface-border rounded-xl p-6 gap-4">
          <PipelineNode icon={<Package size={20} />} title="Product Selection" desc={`${productsData.total} products available`} />
          <PipelineArrow />
          <PipelineNode icon={<Brain size={20} />} title="LLM Analysis" desc="3 local LLMs on reviews" />
          <PipelineArrow />
          <PipelineNode icon={<Layers size={20} />} title="Ensemble Sentiment" desc="Product-level sentiment" />
          <PipelineArrow />
          <PipelineNode icon={<CheckCircle size={20} />} title="Recommendation" desc="Buy / Consider / Don't Buy" />
          <PipelineArrow />
          <PipelineNode icon={<TrendingUp size={20} />} title="Sales Forecasting" desc="Sales Only vs Sales+Sentiment" />
        </div>
      </div>

      {/* ── SENTIMENT OVERVIEW ──────────────────────────────────────────── */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="bg-surface-card border border-surface-border rounded-xl p-5 flex flex-col h-[380px]">
          <div className="flex justify-between items-center mb-6">
            <h2 className="text-base font-medium text-white">Global Ensemble Sentiment</h2>
            <Link to="/sentiment" className="text-xs font-medium text-brand-light hover:text-brand flex items-center gap-1 transition-colors">
              View Sentiment Analysis <ArrowRight size={14} />
            </Link>
          </div>
          <div className="flex-1 w-full">
            <ResponsiveContainer width="100%" height="100%">
              <PieChart>
                <Pie
                  data={pieData}
                  cx="50%"
                  cy="50%"
                  innerRadius={70}
                  outerRadius={100}
                  paddingAngle={5}
                  dataKey="value"
                  stroke="none"
                >
                  {pieData.map((entry, index) => (
                    <Cell key={`cell-${index}`} fill={entry.color} />
                  ))}
                </Pie>
                <RechartsTooltip 
                  formatter={(value) => [`${value} reviews`, 'Count']}
                  contentStyle={{ backgroundColor: '#1e293b', borderColor: '#334155', color: '#f8fafc', borderRadius: '8px', fontSize: '13px' }}
                />
                <Legend iconType="circle" wrapperStyle={{ fontSize: '13px', color: '#94a3b8' }} />
              </PieChart>
            </ResponsiveContainer>
          </div>
        </div>

        <div className="bg-surface-card border border-surface-border rounded-xl p-5 flex flex-col h-[380px]">
          <h2 className="text-base font-medium text-white mb-6">LLM Model Overview</h2>
          <div className="flex-1 w-full">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={modelCompData} layout="vertical" margin={{ top: 0, right: 30, left: 30, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" horizontal={false} stroke="#334155" opacity={0.5} />
                <XAxis type="number" hide />
                <YAxis dataKey="name" type="category" axisLine={false} tickLine={false} tick={{ fill: '#94a3b8', fontSize: 13 }} width={90} />
                <RechartsTooltip 
                  formatter={(value) => [`${value}%`, '']}
                  contentStyle={{ backgroundColor: '#1e293b', borderColor: '#334155', color: '#f8fafc', borderRadius: '8px', fontSize: '13px' }}
                />
                <Legend iconType="circle" wrapperStyle={{ fontSize: '13px', paddingTop: '10px' }} />
                <Bar dataKey="pos" name="Positive" stackId="a" fill={COLORS.positive} radius={[0, 0, 0, 0]} barSize={32} />
                <Bar dataKey="neu" name="Neutral" stackId="a" fill={COLORS.neutral} radius={[0, 0, 0, 0]} />
                <Bar dataKey="neg" name="Negative" stackId="a" fill={COLORS.negative} radius={[0, 6, 6, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
      </div>

    </div>
  )
}

// ── Helper Components ───────────────────────────────────────────────────────

function KPICard({ icon, label, value }) {
  return (
    <div className="bg-surface-card border border-surface-border rounded-xl p-4 flex flex-col items-center justify-center text-center group hover:border-brand/40 transition-colors">
      <div className="text-slate-400 mb-2 group-hover:text-brand-light transition-colors">
        {icon}
      </div>
      <div className="text-xl md:text-2xl font-semibold text-white mb-1 tracking-tight">{value}</div>
      <div className="text-[10px] md:text-xs text-slate-500 uppercase tracking-wider">{label}</div>
    </div>
  )
}

function PipelineNode({ icon, title, desc }) {
  return (
    <div className="flex flex-col items-center text-center min-w-[140px]">
      <div className="w-12 h-12 rounded-full bg-surface-raised border border-surface-border flex items-center justify-center text-brand-light mb-3 shadow-sm">
        {icon}
      </div>
      <h3 className="text-sm font-medium text-white mb-1">{title}</h3>
      <p className="text-[11px] text-slate-400 whitespace-nowrap">{desc}</p>
    </div>
  )
}

function PipelineArrow() {
  return (
    <>
      <div className="hidden lg:flex text-slate-600 px-1"><ArrowRight size={18} /></div>
      <div className="flex lg:hidden text-slate-600 py-2"><ArrowDown size={18} /></div>
    </>
  )
}
