import { FileBarChart, CheckCircle2 } from 'lucide-react'

const METRICS = ['MAE', 'RMSE', 'MAPE']

export default function Results() {
  return (
    <div className="flex flex-col gap-6">
      <div>
        <h2 className="text-xl font-bold text-white">Forecast Results</h2>
        <p className="text-sm text-slate-500 mt-1">
          Model evaluation metrics and forecast vs. actual comparison.
        </p>
      </div>

      {/* Metric placeholder cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {METRICS.map((m) => (
          <div key={m} className="card opacity-40">
            <p className="text-xs text-slate-500 uppercase tracking-wider font-medium">{m}</p>
            <p className="text-2xl font-bold text-white mt-1">—</p>
            <p className="text-xs text-slate-600 mt-0.5">No results yet</p>
          </div>
        ))}
      </div>

      {/* Comparison chart placeholder */}
      <div className="card opacity-40">
        <p className="text-sm font-semibold text-white mb-3">Actual vs. Forecasted Sales</p>
        <div className="h-48 flex items-center justify-center border border-dashed border-surface-border rounded-lg">
          <p className="text-xs text-slate-600">Recharts line chart placeholder</p>
        </div>
      </div>

      <div className="flex flex-col items-center justify-center py-8 text-center">
        <div className="w-14 h-14 rounded-2xl bg-emerald-500/10 border border-emerald-500/20 flex items-center justify-center mb-4">
          <FileBarChart size={24} className="text-emerald-400" />
        </div>
        <h3 className="text-base font-semibold text-white mb-1">Results will populate after forecasting runs</h3>
        <p className="text-sm text-slate-500 max-w-md">
          Evaluation metrics (MAE, RMSE, MAPE) and the forecast vs. actual chart will appear
          here once the SARIMA/SARIMAX models have been trained and evaluated in Phase 4.
        </p>

        <div className="flex flex-col gap-2 mt-6 text-left">
          {['Data loaded into MongoDB', 'Sentiment analysis complete', 'Forecasting models trained'].map((step) => (
            <div key={step} className="flex items-center gap-2 text-xs text-slate-500">
              <CheckCircle2 size={13} className="text-slate-700" />
              {step}
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
