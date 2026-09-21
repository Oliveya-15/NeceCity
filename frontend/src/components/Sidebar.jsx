import { NavLink } from 'react-router-dom'
import { BarChart3, LayoutGrid, Map, ScanSearch, ShieldCheck, Sparkles, X } from 'lucide-react'
import logo from '../assets/nececity-logo.png'

const NAV_ITEMS = [
  { to: '/', label: 'Command Center', icon: LayoutGrid, end: true },
  { to: '/monitor', label: 'City Monitor', icon: Map },
  { to: '/inspect', label: 'Inspect & Analyze', icon: ScanSearch },
  { to: '/insights', label: 'Insights', icon: BarChart3 },
  { to: '/action-center', label: 'Action Center', icon: ShieldCheck },
  { to: '/advice', label: 'AI Recommendations', icon: Sparkles },
]

export default function Sidebar({ open, onClose }) {
  return (
    <>
      {open && (
        <button
          className="fixed inset-0 z-30 bg-ink-900/40 backdrop-blur-sm lg:hidden"
          aria-label="Close navigation menu"
          onClick={onClose}
        />
      )}
      <aside
        className={`fixed lg:static inset-y-0 left-0 z-40 w-64 shrink-0 bg-white border-r border-slate-100 flex flex-col transition-transform duration-200 ${
          open ? 'translate-x-0' : '-translate-x-full lg:translate-x-0'
        }`}
      >
        <div className="flex items-center justify-between px-5 py-6">
          {/* Logo renders on a WHITE background here, so both the navy
              building mark and the orange pin are visible - the previous
              dark-navy sidebar made the navy portion of the logo blend
              into the background. */}
          <img src={logo} alt="NeceCity" className="h-8 w-auto" />
          <button className="lg:hidden text-ink-500 hover:text-ink-900" onClick={onClose} aria-label="Close menu">
            <X className="h-5 w-5" />
          </button>
        </div>

        <nav className="flex-1 px-3 space-y-1" aria-label="Primary">
          {NAV_ITEMS.map(({ to, label, icon: Icon, end }) => (
            <NavLink
              key={to}
              to={to}
              end={end}
              onClick={onClose}
              className={({ isActive }) =>
                `flex items-center gap-3 px-3.5 py-2.5 rounded-md text-sm transition-colors ${
                  isActive
                    ? 'bg-navy-900 text-white font-medium shadow-card'
                    : 'text-ink-700 hover:bg-slate-50 hover:text-ink-900'
                }`
              }
            >
              <Icon className="h-4 w-4 shrink-0" aria-hidden="true" />
              {label}
            </NavLink>
          ))}
        </nav>

        <div className="mx-3 mb-4 rounded-md bg-slate-50 border border-slate-100 px-4 py-3.5 text-xs text-ink-500 leading-relaxed">
          <span className="font-medium text-ink-700">NeceCity</span> &middot; Urban infrastructure
          monitoring &amp; decision-support
        </div>
      </aside>
    </>
  )
}
