import { Outlet } from 'react-router-dom'
import Sidebar from './Sidebar.jsx'
import Header from './Header.jsx'

/**
 * Layout — persistent shell wrapping all pages.
 * <Outlet /> is replaced by the matched child route component.
 */
export default function Layout() {
  return (
    <div className="flex h-screen overflow-hidden bg-surface">
      {/* Sidebar (fixed width, full height) */}
      <Sidebar />

      {/* Main content area */}
      <div className="flex flex-col flex-1 overflow-hidden">
        <Header />
        <main className="flex-1 overflow-y-auto px-6 py-6">
          <Outlet />
        </main>
      </div>
    </div>
  )
}
