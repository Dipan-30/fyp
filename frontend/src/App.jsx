import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import Layout from './components/Layout.jsx'
import Dashboard from './pages/Dashboard.jsx'
import Sentiment from './pages/Sentiment.jsx'
import Products from './pages/Products.jsx'
import ProductAnalysis from './pages/ProductAnalysis.jsx'

export default function App() {
  return (
    <BrowserRouter future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
      <Routes>

        {/* All pages share the Layout shell (sidebar + header) */}
        <Route path="/" element={<Layout />}>
          <Route index element={<Dashboard />} />
          <Route path="sentiment" element={<Sentiment />} />
          <Route path="products" element={<Products />} />
          <Route path="product-analysis/:productId?" element={<ProductAnalysis />} />
          {/* Catch-all — redirect unknown routes to dashboard */}
          <Route path="*" element={<Navigate to="/" replace />} />
        </Route>
      </Routes>
    </BrowserRouter>
  )
}
