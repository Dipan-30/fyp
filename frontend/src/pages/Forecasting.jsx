import { TrendingUp, Settings } from 'lucide-react'

export default function Forecasting() {
  return (
    <div className="flex flex-col gap-6">
      <div>
        <h2 className="text-xl font-bold text-white">Sales Forecasting</h2>
        <p className="text-sm text-slate-500 mt-1">
          SARIMA and SARIMAX time-series forecasting using <code className="text-brand-light text-xs font-mono">statsmodels</code>.
        </p>
      </div>

      {/* Model comparison placeholder */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {[
          { name: 'SARIMA',  desc: 'Univariate seasonal ARIMA model trained on purchase time-series.', badge: 'Baseline' },
          { name: 'SARIMAX', desc: 'SARIMA extended with daily sentiment index as exogenous variable.', badge: 'Enhanced' },
        ].map(({ name, desc, badge }) => (
          <div key={name} className="card opacity-50">
            <div className="flex items-center justify-between mb-2">
              <p className="text-sm font-semibold text-white font-mono">{name}</p>
              <span className="badge-brand">{badge}</span>
            </div>
            <p className="text-xs text-slate-500 leading-relaxed">{desc}</p>
            <div className="mt-4 h-20 flex items-center justify-center border border-dashed border-surface-border rounded-lg">
              <p className="text-xs text-slate-600">Forecast chart placeholder</p>
            </div>
          </div>
        ))}
      </div>

      {/* Config placeholder */}
      <div className="card opacity-40 flex items-center gap-3">
        <Settings size={18} className="text-slate-500 shrink-0" />
        <div>
          <p className="text-sm font-semibold text-white">Model Hyperparameters</p>
          <p className="text-xs text-slate-500 mt-0.5">
            SARIMA order (p,d,q) and seasonal order (P,D,Q,s) will be configurable here.
          </p>
        </div>
      </div>

      <div className="flex flex-col items-center justify-center py-8 text-center">
        <TrendingUp size={28} className="text-accent-teal mb-3" />
        <h3 className="text-base font-semibold text-white mb-1">Forecasting engine coming in Phase 4</h3>
        <p className="text-sm text-slate-500 max-w-md">
          After data preprocessing (Phase 2) and sentiment analysis (Phase 3),
          SARIMA and SARIMAX models will be trained here and evaluated on MAE, RMSE, and MAPE.
        </p>
      </div>
    </div>
  )
}
