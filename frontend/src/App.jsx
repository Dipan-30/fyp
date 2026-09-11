import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import Layout from './components/Layout.jsx'
import Dashboard from './pages/Dashboard.jsx'
import Reviews from './pages/Reviews.jsx'
import Products from './pages/Products.jsx'
import Sentiment from './pages/Sentiment.jsx'
import Forecasting from './pages/Forecasting.jsx'
import Results from './pages/Results.jsx'
import Sales from './pages/Sales.jsx'

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        {/* All pages share the Layout shell (sidebar + header) */}
        <Route path="/" element={<Layout />}>
          <Route index element={<Dashboard />} />
          <Route path="reviews" element={<Reviews />} />
          <Route path="products" element={<Products />} />
          <Route path="sentiment" element={<Sentiment />} />
          <Route path="forecasting" element={<Forecasting />} />
          <Route path="results" element={<Results />} />
          <Route path="sales" element={<Sales />} />
          {/* Catch-all — redirect unknown routes to dashboard */}
          <Route path="*" element={<Navigate to="/" replace />} />
        </Route>
      </Routes>
    </BrowserRouter>
  )
}
