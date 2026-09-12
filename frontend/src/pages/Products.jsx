import { useState, useEffect, useMemo } from 'react'
import { Link } from 'react-router-dom'
import {
  Package, ShoppingCart, TrendingUp, MessageSquare, Search, Filter,
  ChevronDown, ChevronLeft, ChevronRight, AlertTriangle
} from 'lucide-react'
import { getProducts } from '../services/api'

export default function Products() {
  const [products, setProducts] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  // Filters & State
  const [searchQuery, setSearchQuery] = useState('')
  const [filterCategory, setFilterCategory] = useState('All')
  const [filterSentiment, setFilterSentiment] = useState('All')
  const [filterRecommendation, setFilterRecommendation] = useState('All')
  
  // Sort State
  const [sortKey, setSortKey] = useState('units_sold')
  const [sortDirection, setSortDirection] = useState('desc')
  
  // Pagination State
  const [currentPage, setCurrentPage] = useState(1)
  const itemsPerPage = 20

  useEffect(() => {
    fetchProducts()
  }, [])

  const fetchProducts = async () => {
    try {
      setLoading(true)
      const data = await getProducts()
      setProducts(data.products || [])
      setError(null)
    } catch (err) {
      console.error(err)
      setError('Unable to load product data.')
    } finally {
      setLoading(false)
    }
  }

  // Derived KPIs
  const totalProducts = products.length
  const totalTransactions = products.reduce((acc, p) => acc + (p.transactions || 0), 0)
  const totalUnits = products.reduce((acc, p) => acc + (p.units_sold || 0), 0)
  const totalReviews = products.reduce((acc, p) => acc + (p.reviews || 0), 0)

  // Unique lists for dropdowns
  const categories = ['All', ...new Set(products.map(p => p.category).filter(Boolean))]

  // Filtering & Sorting Logic
  const filteredProducts = useMemo(() => {
    let result = products

    if (searchQuery) {
      const lowerQ = searchQuery.toLowerCase()
      result = result.filter(p => 
        String(p.product_id).toLowerCase().includes(lowerQ) ||
        String(p.product_name).toLowerCase().includes(lowerQ) ||
        String(p.category).toLowerCase().includes(lowerQ)
      )
    }

    if (filterCategory !== 'All') {
      result = result.filter(p => p.category === filterCategory)
    }

    if (filterSentiment !== 'All') {
      result = result.filter(p => p.sentiment && p.sentiment.toLowerCase() === filterSentiment.toLowerCase())
    }

    if (filterRecommendation !== 'All') {
      result = result.filter(p => p.recommendation && p.recommendation.toLowerCase() === filterRecommendation.toLowerCase())
    }

    result = [...result].sort((a, b) => {
      let valA = a[sortKey]
      let valB = b[sortKey]
      
      // Handle string sorting (like name) vs numeric sorting
      if (typeof valA === 'string' && typeof valB === 'string') {
        return sortDirection === 'asc' ? valA.localeCompare(valB) : valB.localeCompare(valA)
      } else {
        // Fallback for nulls
        valA = valA ?? 0
        valB = valB ?? 0
        return sortDirection === 'asc' ? valA - valB : valB - valA
      }
    })

    return result
  }, [products, searchQuery, filterCategory, filterSentiment, filterRecommendation, sortKey, sortDirection])

  // Pagination Logic
  const totalPages = Math.ceil(filteredProducts.length / itemsPerPage)
  
  // If search changes, reset page to 1
  useEffect(() => {
    setCurrentPage(1)
  }, [searchQuery, filterCategory, filterSentiment, filterRecommendation, sortKey, sortDirection])

  const currentProducts = filteredProducts.slice(
    (currentPage - 1) * itemsPerPage,
    currentPage * itemsPerPage
  )

  const handleSort = (key) => {
    if (sortKey === key) {
      setSortDirection(sortDirection === 'asc' ? 'desc' : 'asc')
    } else {
      setSortKey(key)
      setSortDirection('desc') // Default to highest first for new sort
    }
  }

  // UI Helpers
  const getSentimentBadge = (sentiment) => {
    switch(sentiment?.toLowerCase()) {
      case 'positive': return <span className="px-2.5 py-0.5 rounded-full bg-emerald-500/20 text-emerald-400 text-xs font-medium border border-emerald-500/20">🟢 Positive</span>
      case 'neutral': return <span className="px-2.5 py-0.5 rounded-full bg-slate-500/20 text-slate-300 text-xs font-medium border border-slate-500/20">🟡 Neutral</span>
      case 'negative': return <span className="px-2.5 py-0.5 rounded-full bg-rose-500/20 text-rose-400 text-xs font-medium border border-rose-500/20">🔴 Negative</span>
      default: return <span className="text-slate-500 text-xs font-medium">No reviews</span>
    }
  }

  const getRecommendationBadge = (rec) => {
    switch(rec?.toLowerCase()) {
      case 'recommended': return <span className="px-2.5 py-0.5 rounded-full bg-emerald-500/10 text-emerald-400 text-xs font-medium border border-emerald-500/20">🟢 Recommended</span>
      case 'consider': return <span className="px-2.5 py-0.5 rounded-full bg-amber-500/10 text-amber-400 text-xs font-medium border border-amber-500/20">🟡 Consider</span>
      case 'not recommended': return <span className="px-2.5 py-0.5 rounded-full bg-rose-500/10 text-rose-400 text-xs font-medium border border-rose-500/20">🔴 Not Recommended</span>
      default: return <span className="text-slate-500 text-xs font-medium">Not Available</span>
    }
  }

  return (
    <div className="flex-1 overflow-auto bg-surface flex flex-col">
      <div className="max-w-7xl mx-auto p-8 w-full">
        
        {/* Header */}
        <div className="mb-8">
          <h1 className="text-2xl font-bold text-white mb-2 tracking-tight">PRODUCT DETAILS</h1>
          <p className="text-slate-400">Explore sales performance, customer sentiment, and purchase recommendations for all products.</p>
        </div>

        {/* Loading / Error States */}
        {loading && (
          <div className="flex items-center justify-center h-64 text-slate-400">
            <div className="flex flex-col items-center">
              <div className="w-8 h-8 border-4 border-brand border-t-transparent rounded-full animate-spin mb-4"></div>
              <p>Loading products...</p>
            </div>
          </div>
        )}

        {error && (
          <div className="bg-surface-card border border-rose-500/20 rounded-xl p-8 text-center text-rose-400 mb-8">
            <AlertTriangle className="mx-auto mb-4" size={32} />
            <p className="mb-4">{error}</p>
            <button onClick={fetchProducts} className="px-4 py-2 bg-rose-500/10 hover:bg-rose-500/20 rounded-lg font-medium transition-colors border border-rose-500/20">
              Retry
            </button>
          </div>
        )}

        {!loading && !error && (
          <>
            {/* KPI Cards */}
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-8">
              <div className="bg-surface-card border border-surface-border rounded-xl p-6">
                <div className="flex items-center gap-4 mb-2">
                  <div className="w-10 h-10 rounded-lg bg-brand/10 flex items-center justify-center">
                    <Package className="text-brand-light" size={20} />
                  </div>
                  <h3 className="text-sm font-medium text-slate-400">Total Products</h3>
                </div>
                <p className="text-3xl font-bold text-white">{totalProducts}</p>
              </div>

              <div className="bg-surface-card border border-surface-border rounded-xl p-6">
                <div className="flex items-center gap-4 mb-2">
                  <div className="w-10 h-10 rounded-lg bg-emerald-500/10 flex items-center justify-center">
                    <ShoppingCart className="text-emerald-400" size={20} />
                  </div>
                  <h3 className="text-sm font-medium text-slate-400">Transactions</h3>
                </div>
                <p className="text-3xl font-bold text-white">{totalTransactions.toLocaleString()}</p>
              </div>

              <div className="bg-surface-card border border-surface-border rounded-xl p-6">
                <div className="flex items-center gap-4 mb-2">
                  <div className="w-10 h-10 rounded-lg bg-teal-500/10 flex items-center justify-center">
                    <TrendingUp className="text-teal-400" size={20} />
                  </div>
                  <h3 className="text-sm font-medium text-slate-400">Units Sold</h3>
                </div>
                <p className="text-3xl font-bold text-white">{totalUnits.toLocaleString()}</p>
              </div>

              <div className="bg-surface-card border border-surface-border rounded-xl p-6">
                <div className="flex items-center gap-4 mb-2">
                  <div className="w-10 h-10 rounded-lg bg-purple-500/10 flex items-center justify-center">
                    <MessageSquare className="text-purple-400" size={20} />
                  </div>
                  <h3 className="text-sm font-medium text-slate-400">Reviews</h3>
                </div>
                <p className="text-3xl font-bold text-white">{totalReviews.toLocaleString()}</p>
              </div>
            </div>

            {/* Controls (Search, Filters, Sort) */}
            <div className="bg-surface-card border border-surface-border rounded-xl p-3 mb-6 flex items-center justify-between gap-3">
              
              <div className="relative w-48 shrink-0">
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" size={16} />
                <input 
                  type="text" 
                  placeholder="Search..." 
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  className="w-full bg-surface border border-surface-border rounded-lg pl-9 pr-3 py-1.5 text-sm text-white focus:outline-none focus:border-brand-light transition-colors"
                />
              </div>

              <div className="flex items-center gap-2 shrink-0 ml-auto">
                <div className="relative">
                  <select 
                    value={filterCategory} 
                    onChange={(e) => setFilterCategory(e.target.value)}
                    className="appearance-none bg-surface border border-surface-border rounded-lg pl-3 pr-8 py-1.5 text-sm text-white focus:outline-none focus:border-brand-light cursor-pointer"
                  >
                    {categories.map(c => <option key={c} value={c}>{c === 'All' ? 'All Categories' : c}</option>)}
                  </select>
                  <ChevronDown className="absolute right-2.5 top-1/2 -translate-y-1/2 text-slate-400 pointer-events-none" size={14} />
                </div>

                <div className="relative">
                  <select 
                    value={filterSentiment} 
                    onChange={(e) => setFilterSentiment(e.target.value)}
                    className="appearance-none bg-surface border border-surface-border rounded-lg pl-3 pr-8 py-1.5 text-sm text-white focus:outline-none focus:border-brand-light cursor-pointer"
                  >
                    <option value="All">All Sentiments</option>
                    <option value="positive">Positive</option>
                    <option value="neutral">Neutral</option>
                    <option value="negative">Negative</option>
                  </select>
                  <ChevronDown className="absolute right-2.5 top-1/2 -translate-y-1/2 text-slate-400 pointer-events-none" size={14} />
                </div>

                <div className="relative">
                  <select 
                    value={filterRecommendation} 
                    onChange={(e) => setFilterRecommendation(e.target.value)}
                    className="appearance-none bg-surface border border-surface-border rounded-lg pl-3 pr-8 py-1.5 text-sm text-white focus:outline-none focus:border-brand-light cursor-pointer"
                  >
                    <option value="All">All Recommendations</option>
                    <option value="recommended">Recommended</option>
                    <option value="consider">Consider</option>
                    <option value="not recommended">Not Recommended</option>
                  </select>
                  <ChevronDown className="absolute right-2.5 top-1/2 -translate-y-1/2 text-slate-400 pointer-events-none" size={14} />
                </div>

                <div className="relative flex items-center gap-2">
                  <span className="text-slate-400 text-sm whitespace-nowrap">Sort By:</span>
                  <div className="relative">
                    <select 
                      value={sortKey} 
                      onChange={(e) => {
                        setSortKey(e.target.value);
                        setSortDirection(e.target.value === 'product_id' || e.target.value === 'product_name' || e.target.value === 'category' ? 'asc' : 'desc')
                      }}
                    className="appearance-none bg-surface border border-surface-border rounded-lg pl-3 pr-8 py-1.5 text-sm text-white focus:outline-none focus:border-brand-light cursor-pointer min-w-[125px]"
                    >
                      <option value="product_id">Product ID</option>
                      <option value="product_name">Product Name</option>
                      <option value="units_sold">Units Sold</option>
                      <option value="transactions">Transactions</option>
                      <option value="reviews">Reviews</option>
                      <option value="sentiment_score">Sentiment Score</option>
                    </select>
                    <ChevronDown className="absolute right-2.5 top-1/2 -translate-y-1/2 text-slate-400 pointer-events-none" size={14} />
                  </div>
                </div>
              </div>
            </div>

            {/* Table */}
            <div className="bg-surface-card border border-surface-border rounded-xl overflow-hidden shadow-sm">
              <div className="overflow-x-auto">
                <table className="w-full text-sm text-slate-300">
                  <thead className="text-xs uppercase bg-surface text-slate-400 border-b border-surface-border">
                    <tr>
                      <th className="px-4 py-4 font-medium text-left sticky top-0 bg-surface">Product</th>
                      <th className="px-4 py-4 font-medium text-left sticky top-0 bg-surface">Category</th>
                      <th className="px-4 py-4 font-medium text-right sticky top-0 bg-surface">Units Sold</th>
                      <th className="px-4 py-4 font-medium text-right sticky top-0 bg-surface">Txns</th>
                      <th className="px-4 py-4 font-medium text-right sticky top-0 bg-surface">Reviews</th>
                      <th className="px-4 py-4 font-medium text-center sticky top-0 bg-surface">Sentiment</th>
                      <th className="px-4 py-4 font-medium text-center sticky top-0 bg-surface">Score</th>
                      <th className="px-4 py-4 font-medium text-center sticky top-0 bg-surface">Recommendation</th>
                      <th className="px-4 py-4 font-medium text-center sticky top-0 bg-surface">Action</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-surface-border">
                    {currentProducts.length === 0 ? (
                      <tr>
                        <td colSpan="9" className="px-4 py-12 text-center">
                          <p className="text-slate-400 mb-4">No products found matching your filters.</p>
                          <button 
                            onClick={() => {
                              setSearchQuery('')
                              setFilterCategory('All')
                              setFilterSentiment('All')
                              setFilterRecommendation('All')
                            }}
                            className="px-4 py-2 bg-surface hover:bg-slate-800 rounded-lg text-white border border-surface-border transition-colors text-sm font-medium"
                          >
                            Clear Filters
                          </button>
                        </td>
                      </tr>
                    ) : (
                      currentProducts.map((p) => (
                        <tr key={p.product_id} className="hover:bg-surface/50 transition-colors group">
                          <td className="px-4 py-4 text-left">
                            <div className="flex flex-col">
                              <span className="text-white font-medium whitespace-nowrap">{p.product_name}</span>
                              <span className="text-xs text-slate-500 whitespace-nowrap">ID: {p.product_id}</span>
                            </div>
                          </td>
                          <td className="px-4 py-4 text-slate-400 text-left whitespace-nowrap">{p.category}</td>
                          <td className="px-4 py-4 text-right font-medium text-white">{p.units_sold}</td>
                          <td className="px-4 py-4 text-right">{p.transactions}</td>
                          <td className="px-4 py-4 text-right">{p.reviews}</td>
                          <td className="px-4 py-4 text-center whitespace-nowrap">
                            {getSentimentBadge(p.sentiment)}
                          </td>
                          <td className="px-4 py-4 text-center">
                            {p.sentiment_score !== null ? (
                              <span className={`font-medium ${p.sentiment_score >= 0.5 ? 'text-emerald-400' : p.sentiment_score > -0.25 ? 'text-slate-300' : 'text-rose-400'}`}>
                                {p.sentiment_score > 0 ? `+${p.sentiment_score.toFixed(2)}` : p.sentiment_score.toFixed(2)}
                              </span>
                            ) : (
                              <span className="text-slate-500">—</span>
                            )}
                          </td>
                          <td className="px-4 py-4 text-center whitespace-nowrap">
                            {getRecommendationBadge(p.recommendation)}
                          </td>
                          <td className="px-4 py-4 text-center whitespace-nowrap">
                            <Link 
                              to={`/product-analysis/${p.product_id}`}
                              className="inline-flex items-center justify-center px-4 py-1.5 bg-brand hover:bg-brand-light text-white text-xs font-medium rounded-lg transition-colors"
                            >
                              View Product &rarr;
                            </Link>
                          </td>
                        </tr>
                      ))
                    )}
                  </tbody>
                </table>
              </div>
              
              {/* Pagination */}
              {filteredProducts.length > 0 && (
                <div className="bg-surface border-t border-surface-border px-6 py-4 flex flex-col sm:flex-row gap-4 items-center justify-between">
                  <span className="text-sm text-slate-400">
                    Showing <strong className="text-white">{(currentPage - 1) * itemsPerPage + 1}</strong> to <strong className="text-white">{Math.min(currentPage * itemsPerPage, filteredProducts.length)}</strong> of <strong className="text-white">{filteredProducts.length}</strong> products
                  </span>
                  <div className="flex items-center gap-2">
                    <button
                      onClick={() => setCurrentPage(p => Math.max(1, p - 1))}
                      disabled={currentPage === 1}
                      className="p-2 rounded-lg border border-surface-border text-slate-400 hover:bg-slate-800 hover:text-white disabled:opacity-50 disabled:hover:bg-transparent transition-colors"
                    >
                      <ChevronLeft size={16} />
                    </button>
                    
                    <div className="flex items-center gap-1">
                      {Array.from({ length: totalPages }).map((_, i) => {
                        const pageNum = i + 1;
                        if (totalPages > 7) {
                          if (pageNum !== 1 && pageNum !== totalPages && Math.abs(currentPage - pageNum) > 1) {
                            if (Math.abs(currentPage - pageNum) === 2) return <span key={i} className="px-1 text-slate-500">...</span>;
                            return null;
                          }
                        }
                        
                        return (
                          <button
                            key={i}
                            onClick={() => setCurrentPage(pageNum)}
                            className={`w-8 h-8 rounded-lg text-sm font-medium transition-colors flex items-center justify-center ${
                              currentPage === pageNum 
                                ? 'bg-brand text-white border border-brand' 
                                : 'text-slate-400 hover:bg-slate-800 hover:text-white border border-transparent'
                            }`}
                          >
                            {pageNum}
                          </button>
                        )
                      })}
                    </div>

                    <button
                      onClick={() => setCurrentPage(p => Math.min(totalPages, p + 1))}
                      disabled={currentPage === totalPages}
                      className="p-2 rounded-lg border border-surface-border text-slate-400 hover:bg-slate-800 hover:text-white disabled:opacity-50 disabled:hover:bg-transparent transition-colors"
                    >
                      <ChevronRight size={16} />
                    </button>
                  </div>
                </div>
              )}
            </div>
          </>
        )}
      </div>
    </div>
  )
}
