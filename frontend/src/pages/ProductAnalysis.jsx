import { useState, useEffect } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import {
  Brain, Package, ShoppingCart, TrendingUp, AlertTriangle, CheckCircle, XCircle, ChevronDown
} from 'lucide-react'
import {
  ComposedChart, LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip as RechartsTooltip,
  Legend, ResponsiveContainer, BarChart, Bar, Cell, AreaChart, Area
} from 'recharts'
import {
  getProducts, getProductOverview, getProductSales, getProductSentiment, getProductForecast
} from '../services/api'

// Colors
const COLORS = {
  positive: '#10b981', // emerald-500
  neutral: '#64748b',  // slate-500
  negative: '#ef4444', // red-500
  brand: '#3b82f6',    // blue-500
  actual: '#f8fafc',   // slate-50
  naive: '#fbbf24',    // amber-400
  arima: '#3b82f6',    // blue-500
  arimax: '#14b8a6',   // teal-500
}

export default function ProductAnalysis() {
  const { productId } = useParams()
  const navigate = useNavigate()
  
  const [products, setProducts] = useState([])
  const [selectedProductId, setSelectedProductId] = useState(productId || '')
  
  const [overview, setOverview] = useState(null)
  const [sales, setSales] = useState(null)
  const [sentiment, setSentiment] = useState(null)
  const [forecast, setForecast] = useState(null)
  
  const [loadingList, setLoadingList] = useState(true)
  const [loadingData, setLoadingData] = useState(false)
  const [error, setError] = useState(null)

  useEffect(() => {
    getProducts()
      .then(res => {
        setProducts(res.products)
        setLoadingList(false)
        if (res.products.length > 0) {
          const initialId = productId || res.products[0].product_id
          if (initialId !== selectedProductId) {
            setSelectedProductId(initialId)
          }
          handleSelectProduct(initialId, false)
        }
      })
      .catch(err => {
        setError(err.message)
        setLoadingList(false)
      })
  }, []) // Load list once

  // When productId in URL changes, update data
  useEffect(() => {
    if (productId && products.length > 0) {
      if (productId !== selectedProductId) {
        setSelectedProductId(productId)
        handleSelectProduct(productId, false)
      }
    }
  }, [productId, products])

  const handleSelectProduct = (id, updateUrl = true) => {
    if (updateUrl) {
      navigate(`/product-analysis/${id}`)
      return // useEffect will catch the URL change
    }
    
    setSelectedProductId(id)
    setLoadingData(true)
    setError(null)
    
    Promise.all([
      getProductOverview(id),
      getProductSentiment(id),
      getProductSales(id),
      getProductForecast(id)
    ])
    .then(([overviewRes, sentimentRes, salesRes, forecastRes]) => {
      setOverview(overviewRes)
      setSentiment(sentimentRes)
      setSales(salesRes.sales)
      setForecast(forecastRes)
      setLoadingData(false)
    })
    .catch(err => {
      setError(err.message)
      setLoadingData(false)
    })
  }

  if (loadingList) {
    return (
      <div className="flex items-center justify-center h-full min-h-[50vh]">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-brand"></div>
      </div>
    )
  }

  return (
    <div className="p-4 md:p-8 max-w-6xl mx-auto space-y-8 animate-in fade-in duration-500">
      
      {/* ── HEADER & SELECTOR ───────────────────────────────────────────── */}
      <div className="border-b border-surface-border pb-6 flex flex-col md:flex-row md:items-end justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold text-white tracking-tight">
            INDIVIDUAL PRODUCT ANALYSIS
          </h1>
          <p className="text-slate-400 text-sm mt-2">
            Analyze customer sentiment and predict future sales for an individual product.
          </p>
        </div>
        
        <div className="relative min-w-[240px]">
          <select
            value={selectedProductId}
            onChange={(e) => handleSelectProduct(e.target.value)}
            className="w-full appearance-none bg-surface-card border border-surface-border text-white text-sm rounded-xl px-4 py-2.5 outline-none focus:border-brand/50 transition-colors cursor-pointer"
          >
            {products.map(p => (
              <option key={p.product_id} value={p.product_id}>
                {p.product_id} — {p.product_name}
              </option>
            ))}
          </select>
          <ChevronDown className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400 pointer-events-none" size={16} />
        </div>
      </div>

      {error && (
        <div className="bg-rose-500/10 border border-rose-500/20 text-rose-500 rounded-xl p-4 flex items-center gap-3">
          <AlertTriangle size={20} />
          <p className="text-sm">{error}</p>
        </div>
      )}

      {loadingData && !error && (
        <div className="flex items-center justify-center py-20">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-brand"></div>
        </div>
      )}

      {!loadingData && !error && overview && (
        <div className="flex flex-col gap-8">
          {/* ── PRODUCT OVERVIEW ───────────────────────────────────────────── */}
          <div>
            <h2 className="text-lg font-medium text-white mb-4">PRODUCT OVERVIEW</h2>
            <div className="bg-surface-card border border-surface-border rounded-xl p-6 grid grid-cols-2 md:grid-cols-4 gap-y-6 gap-x-4">
              <OverviewItem label="Product ID" value={overview.product_id} />
              <OverviewItem label="Product Name" value={overview.product_name} className="col-span-2 md:col-span-1" />
              <OverviewItem label="Category" value={overview.category} />
              <OverviewItem label="Price" value={overview.price ? `$${overview.price.toFixed(2)}` : 'N/A'} />
              <OverviewItem label="Total Units Sold" value={overview.total_units_sold} />
              <OverviewItem label="Transactions" value={overview.number_of_transactions} />
              <OverviewItem label="Active Sales Days" value={overview.active_sales_days} />
              <OverviewItem label="Number of Reviews" value={overview.number_of_reviews} />
            </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
            {/* ── CUSTOMER SENTIMENT ───────────────────────────────────────── */}
            <div className="flex flex-col">
              <h2 className="text-lg font-medium text-white mb-4">CUSTOMER SENTIMENT</h2>
              <div className="bg-surface-card border border-surface-border rounded-xl p-6 flex-1 flex flex-col justify-center">
                
                <div className="flex items-center gap-4 mb-6 pb-6 border-b border-surface-border">
                  <div className="flex-1">
                    <p className="text-sm text-slate-400 mb-1">Overall Sentiment</p>
                    <div className="flex items-center gap-2">
                      {sentiment.sentiment_score >= 0.5 ? (
                        <div className="w-3 h-3 rounded-full bg-emerald-500"></div>
                      ) : sentiment.sentiment_score > -0.25 ? (
                        <div className="w-3 h-3 rounded-full bg-amber-500"></div>
                      ) : (
                        <div className="w-3 h-3 rounded-full bg-rose-500"></div>
                      )}
                      <span className="text-xl font-semibold text-white">
                        {sentiment.sentiment_score >= 0.5 ? 'POSITIVE' : sentiment.sentiment_score > -0.25 ? 'MIXED/NEUTRAL' : 'NEGATIVE'}
                      </span>
                    </div>
                  </div>
                  <div className="text-right">
                    <p className="text-sm text-slate-400 mb-1">Score</p>
                    <p className="text-xl font-medium text-white">{sentiment.sentiment_score > 0 ? `+${sentiment.sentiment_score}` : sentiment.sentiment_score}</p>
                  </div>
                </div>

                <div className="space-y-3 mb-6">
                  <SentimentBar label="Positive" pct={sentiment.positive_pct} color={COLORS.positive} />
                  <SentimentBar label="Neutral" pct={sentiment.neutral_pct} color={COLORS.neutral} />
                  <SentimentBar label="Negative" pct={sentiment.negative_pct} color={COLORS.negative} />
                </div>

                <div className="flex justify-between items-center text-sm text-slate-400 mt-auto pt-4 border-t border-surface-border">
                  <span>Reviews: <strong className="text-white font-medium">{sentiment.review_count}</strong></span>
                  <span>LLM Agreement: <strong className="text-white font-medium">{sentiment.agreement_pct}%</strong></span>
                </div>
              </div>
            </div>

            {/* ── PURCHASE RECOMMENDATION ──────────────────────────────────── */}
            <div className="flex flex-col">
              <h2 className="text-lg font-medium text-white mb-4">PURCHASE RECOMMENDATION</h2>
              <div className="bg-surface-card border border-surface-border rounded-xl p-6 flex-1 flex flex-col justify-center items-center text-center">
                
                {sentiment.recommendation === 'RECOMMENDED' && (
                  <>
                    <div className="w-20 h-20 bg-emerald-500/10 rounded-full flex items-center justify-center mb-4 border border-emerald-500/20">
                      <CheckCircle className="text-emerald-500" size={40} />
                    </div>
                    <h3 className="text-2xl font-bold text-emerald-500 tracking-tight mb-3">RECOMMENDED</h3>
                    <p className="text-slate-300 leading-relaxed max-w-sm">
                      Based on customer review sentiment, this product is recommended.
                    </p>
                  </>
                )}

                {sentiment.recommendation === 'CONSIDER' && (
                  <>
                    <div className="w-20 h-20 bg-amber-500/10 rounded-full flex items-center justify-center mb-4 border border-amber-500/20">
                      <AlertTriangle className="text-amber-500" size={40} />
                    </div>
                    <h3 className="text-2xl font-bold text-amber-500 tracking-tight mb-3">CONSIDER</h3>
                    <p className="text-slate-300 leading-relaxed max-w-sm">
                      Customer sentiment is mixed, so consider additional factors before purchasing.
                    </p>
                  </>
                )}

                {sentiment.recommendation === 'NOT RECOMMENDED' && (
                  <>
                    <div className="w-20 h-20 bg-rose-500/10 rounded-full flex items-center justify-center mb-4 border border-rose-500/20">
                      <XCircle className="text-rose-500" size={40} />
                    </div>
                    <h3 className="text-2xl font-bold text-rose-500 tracking-tight mb-3">NOT RECOMMENDED</h3>
                    <p className="text-slate-300 leading-relaxed max-w-sm">
                      Based on negative customer review sentiment, this product is not recommended.
                    </p>
                  </>
                )}

                {sentiment.recommendation === 'NOT ENOUGH DATA' && (
                  <>
                    <div className="w-20 h-20 bg-slate-500/10 rounded-full flex items-center justify-center mb-4 border border-slate-500/20">
                      <Package className="text-slate-500" size={40} />
                    </div>
                    <h3 className="text-2xl font-bold text-slate-500 tracking-tight mb-3">NO RECOMMENDATION</h3>
                    <p className="text-slate-300 leading-relaxed max-w-sm">
                      There are not enough reviews to provide a sentiment-based recommendation.
                    </p>
                  </>
                )}
              </div>
            </div>
          </div>

          {/* ── HISTORICAL SALES ─────────────────────────────────────────── */}
          <div>
            <h2 className="text-lg font-medium text-white mb-4">HISTORICAL SALES</h2>
            <div className="bg-surface-card border border-surface-border rounded-xl p-6">
              <p className="text-xs font-medium text-slate-400 mb-6 tracking-wider uppercase">Observed Sales Activity</p>
              <div className="h-64 w-full">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={sales} margin={{ top: 5, right: 10, left: -20, bottom: 0 }}>
                    <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#334155" opacity={0.5} />
                    <XAxis dataKey="date" stroke="#64748b" tick={{ fontSize: 11 }} tickLine={false} axisLine={false} minTickGap={30} />
                    <YAxis stroke="#64748b" tick={{ fontSize: 11 }} tickLine={false} axisLine={false} />
                    <RechartsTooltip 
                      contentStyle={{ backgroundColor: '#1e293b', borderColor: '#334155', color: '#f8fafc', borderRadius: '8px', fontSize: '13px' }}
                    />
                    <Bar dataKey="sales" name="Sales Units" fill={COLORS.brand} radius={[2, 2, 0, 0]} maxBarSize={40} />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </div>
          </div>

          {/* ── FUTURE SALES PREDICTION ──────────────────────────────────── */}
          <div>
            <h2 className="text-lg font-medium text-white mb-4">FUTURE SALES PREDICTION</h2>
            
            {!forecast.forecast_feasible ? (
              <div className="bg-surface-card border border-surface-border rounded-xl p-8 text-center">
                <div className="inline-flex w-12 h-12 bg-slate-800 rounded-full items-center justify-center mb-4 text-slate-400">
                  <AlertTriangle size={24} />
                </div>
                <h3 className="text-lg font-medium text-white mb-2">FORECAST UNAVAILABLE</h3>
                <p className="text-slate-400 text-sm max-w-md mx-auto leading-relaxed">
                  Insufficient historical observations for a reliable individual product forecast.
                </p>
                <p className="text-slate-500 text-xs mt-4">
                  {forecast.reason}
                </p>
              </div>
            ) : (
              <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
                <div className="lg:col-span-2 bg-surface-card border border-surface-border rounded-xl p-6">
                  <p className="text-xs font-medium text-slate-400 mb-6 tracking-wider uppercase">Actual vs Expected Future Sales</p>
                  <div className="h-72 w-full">
                    <ResponsiveContainer width="100%" height="100%">
                      <ComposedChart margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
                        <defs>
                          <linearGradient id="colorActual" x1="0" y1="0" x2="0" y2="1">
                            <stop offset="5%" stopColor={COLORS.brand} stopOpacity={0.4}/>
                            <stop offset="95%" stopColor={COLORS.brand} stopOpacity={0}/>
                          </linearGradient>
                        </defs>
                        <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#334155" opacity={0.3} />
                        <XAxis dataKey="date" stroke="#94a3b8" tick={{ fontSize: 11 }} tickLine={false} axisLine={false} minTickGap={30} allowDuplicatedCategory={false} />
                        <YAxis stroke="#94a3b8" tick={{ fontSize: 11 }} tickLine={false} axisLine={false} />
                        <RechartsTooltip 
                          contentStyle={{ backgroundColor: '#1e293b', borderColor: '#334155', color: '#f8fafc', borderRadius: '8px', fontSize: '13px', boxShadow: '0 4px 6px -1px rgb(0 0 0 / 0.3)' }}
                          itemStyle={{ padding: '2px 0' }}
                        />
                        <Legend wrapperStyle={{ fontSize: '12px', paddingTop: '15px' }} iconType="circle" />
                        <Area data={forecast.historical_chart} type="linear" dataKey="actual_sales" name="Actual Sales" stroke={COLORS.brand} strokeWidth={2} fillOpacity={1} fill="url(#colorActual)" />
                        <Line data={forecast.future_predictions} type="linear" dataKey="arima_pred" name="Sales-Only Forecast" stroke={COLORS.naive} strokeDasharray="4 4" strokeWidth={2} dot={{r:3, fill: COLORS.naive, stroke: "none"}} activeDot={{r:5}} />
                        {forecast.sentiment_available && (
                           <Line data={forecast.future_predictions} type="linear" dataKey="arimax_pred" name="Sales + Sentiment Forecast" stroke={COLORS.arimax} strokeDasharray="4 4" strokeWidth={2} dot={{r:3, fill: COLORS.arimax, stroke: "none"}} activeDot={{r:5}} />
                        )}
                      </ComposedChart>
                    </ResponsiveContainer>
                  </div>
                </div>

                <div className="flex flex-col gap-6">
                  <div className="bg-surface-card border border-surface-border rounded-xl p-5">
                    <h3 className="text-sm font-medium text-white mb-4 uppercase tracking-wider">Model Comparison</h3>
                    <div className="overflow-x-auto">
                      <table className="w-full text-sm text-left">
                        <thead className="text-xs text-slate-400 border-b border-surface-border">
                          <tr>
                            <th className="pb-2 font-medium">Model</th>
                            <th className="pb-2 font-medium">MAE</th>
                            <th className="pb-2 font-medium">RMSE</th>
                          </tr>
                        </thead>
                        <tbody className="divide-y divide-surface-border">
                          <tr>
                            <td className="py-2 text-slate-300">Naive</td>
                            <td className="py-2 text-white">{forecast.metrics.naive.mae}</td>
                            <td className="py-2 text-white">{forecast.metrics.naive.rmse}</td>
                          </tr>
                          <tr>
                            <td className="py-2 text-slate-300">ARIMA</td>
                            <td className="py-2 text-brand-light">{forecast.metrics.arima.mae}</td>
                            <td className="py-2 text-brand-light">{forecast.metrics.arima.rmse}</td>
                          </tr>
                          {forecast.sentiment_available && (
                            <tr>
                              <td className="py-2 text-slate-300">ARIMA + Sent.</td>
                              <td className="py-2 text-teal-400">{forecast.metrics.arimax.mae}</td>
                              <td className="py-2 text-teal-400">{forecast.metrics.arimax.rmse}</td>
                            </tr>
                          )}
                        </tbody>
                      </table>
                    </div>
                  </div>

                  <div className="bg-surface-card border border-surface-border rounded-xl p-5 flex-1">
                    <h3 className="text-sm font-medium text-white mb-3 uppercase tracking-wider">Sentiment Impact</h3>
                    {!forecast.sentiment_available ? (
                      <p className="text-sm text-slate-400 leading-relaxed">
                        Sentiment-enhanced forecasting unavailable for this product due to insufficient aligned sales and sentiment observations.
                      </p>
                    ) : (
                      <>
                        <div className="space-y-2 mb-4">
                          <div className="flex justify-between text-sm">
                            <span className="text-slate-400">Sales Only MAE:</span>
                            <span className="text-white">{forecast.metrics.arima.mae}</span>
                          </div>
                          <div className="flex justify-between text-sm">
                            <span className="text-slate-400">Sales + Sent MAE:</span>
                            <span className="text-white">{forecast.metrics.arimax.mae}</span>
                          </div>
                        </div>
                        {forecast.improvement_pct > 0 ? (
                          <div className="bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 rounded-lg p-3 text-sm text-center">
                            Improvement: <strong className="font-semibold text-emerald-300">{forecast.improvement_pct}%</strong>
                          </div>
                        ) : (
                          <div className="bg-slate-800 border border-surface-border text-slate-400 rounded-lg p-3 text-sm text-center">
                            Sentiment did not improve forecasting accuracy for this product.
                          </div>
                        )}
                      </>
                    )}
                  </div>
                </div>
              </div>
            )}
          </div>

          {/* ── PRODUCT INSIGHTS ─────────────────────────────────────────── */}
          <div>
            <h2 className="text-lg font-medium text-white mb-4">PRODUCT INSIGHTS</h2>
            <div className="bg-brand/5 border border-brand/20 rounded-xl p-6">
              <ul className="space-y-3 text-slate-300 text-sm leading-relaxed list-disc list-inside">
                <li>
                  Customer sentiment is predominantly <strong className="text-white">{sentiment.sentiment_score >= 0.5 ? 'positive' : sentiment.sentiment_score > -0.25 ? 'mixed' : 'negative'}</strong> with a score of {sentiment.sentiment_score}.
                </li>
                <li>
                  The product has <strong className="text-white">{sentiment.review_count}</strong> analyzed reviews with {sentiment.agreement_pct}% model agreement.
                </li>
                <li>
                  Historical sales show <strong className="text-white">{overview.active_sales_days}</strong> observed active sales days totaling {overview.total_units_sold} units.
                </li>
                {forecast.forecast_feasible && forecast.sentiment_available && (
                  <li>
                    Sentiment-enhanced forecasting {forecast.improvement_pct > 0 ? (
                      <>improved MAE by <strong className="text-emerald-400">{forecast.improvement_pct}%</strong></>
                    ) : (
                      'did not improve MAE'
                    )} compared to historical sales alone.
                  </li>
                )}
                {forecast.forecast_feasible && forecast.future_predictions.length > 0 && (
                  <li>
                    Forecast expects approximately <strong className="text-white">{Math.round(
                      (forecast.sentiment_available && forecast.future_predictions[0].arimax_pred !== null)
                        ? forecast.future_predictions[0].arimax_pred
                        : forecast.future_predictions[0].arima_pred
                    )}</strong> units in the next period.
                  </li>
                )}
              </ul>
            </div>
          </div>
        </div>
      )}

    </div>
  )
}

function OverviewItem({ label, value, className = '' }) {
  return (
    <div className={className}>
      <p className="text-xs text-slate-500 uppercase tracking-wider mb-1">{label}</p>
      <p className="text-lg font-medium text-white">{value}</p>
    </div>
  )
}

function SentimentBar({ label, pct, color }) {
  return (
    <div>
      <div className="flex justify-between text-xs mb-1">
        <span className="text-slate-400">{label}</span>
        <span className="text-white font-medium">{pct}%</span>
      </div>
      <div className="h-2 w-full bg-slate-800 rounded-full overflow-hidden">
        <div className="h-full rounded-full transition-all duration-1000" style={{ width: `${pct}%`, backgroundColor: color }}></div>
      </div>
    </div>
  )
}
