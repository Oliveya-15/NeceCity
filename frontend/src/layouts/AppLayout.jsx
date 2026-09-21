import { useState } from 'react'
import { Menu } from 'lucide-react'
import Sidebar from '../components/Sidebar'
import CitySelector from '../components/CitySelector'
import ModelStatusBadge from '../components/ModelStatusBadge'
import { useCity } from '../hooks/CityContext'

export default function AppLayout({ title, description, actions, children }) {
  const [sidebarOpen, setSidebarOpen] = useState(false)
  const { cities, loading } = useCity()

  return (
    <div className="min-h-screen flex bg-canvas">
      <Sidebar open={sidebarOpen} onClose={() => setSidebarOpen(false)} />

      <div className="flex-1 min-w-0 flex flex-col">
        <header className="sticky top-0 z-20 bg-white/90 backdrop-blur border-b border-slate-100">
          <div className="flex items-center justify-between gap-4 px-4 sm:px-8 py-4">
            <div className="flex items-center gap-3 min-w-0">
              <button
                className="lg:hidden text-ink-700 hover:text-ink-900 shrink-0"
                onClick={() => setSidebarOpen(true)}
                aria-label="Open navigation menu"
              >
                <Menu className="h-5 w-5" />
              </button>
              <div className="min-w-0">
                <h1 className="text-xl font-bold text-ink-900 tracking-tight truncate">{title}</h1>
                {description && <p className="text-sm text-ink-500 hidden sm:block truncate mt-0.5">{description}</p>}
              </div>
            </div>
            <div className="flex items-center gap-3 shrink-0">
              {actions}
              <ModelStatusBadge />
              <CitySelector />
            </div>
          </div>
        </header>

        <main className="flex-1 px-4 sm:px-8 py-7 min-w-0">
          {!loading && cities.length === 0 ? (
            <div className="panel p-10 text-center max-w-lg mx-auto">
              <p className="text-sm font-medium text-ink-900">No cities configured yet.</p>
              <p className="text-sm text-ink-500 mt-1.5">
                Run the demo data seed script (<code className="text-xs bg-slate-50 px-1.5 py-0.5 rounded border border-slate-100">python -m app.seed.seed_data</code>) to populate cities and sample problems.
              </p>
            </div>
          ) : (
            children
          )}
        </main>
      </div>
    </div>
  )
}
