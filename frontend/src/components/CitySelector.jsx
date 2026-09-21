import { useEffect, useRef, useState } from 'react'
import { Check, ChevronDown, MapPin } from 'lucide-react'
import { useCity } from '../hooks/CityContext'

export default function CitySelector() {
  const { cities, selectedCity, selectedCityId, selectCity, loading } = useCity()
  const [open, setOpen] = useState(false)
  const containerRef = useRef(null)

  useEffect(() => {
    function handleClickOutside(e) {
      if (containerRef.current && !containerRef.current.contains(e.target)) setOpen(false)
    }
    function handleEscape(e) {
      if (e.key === 'Escape') setOpen(false)
    }
    document.addEventListener('mousedown', handleClickOutside)
    document.addEventListener('keydown', handleEscape)
    return () => {
      document.removeEventListener('mousedown', handleClickOutside)
      document.removeEventListener('keydown', handleEscape)
    }
  }, [])

  if (loading) return <div className="h-10 w-40 rounded-full bg-slate-100 animate-pulse" aria-hidden="true" />
  if (cities.length === 0) return null

  return (
    <div className="relative" ref={containerRef}>
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        aria-haspopup="listbox"
        aria-expanded={open}
        className={`flex items-center gap-2 rounded-full border bg-white pl-3.5 pr-3 py-2.5 text-sm font-medium text-ink-900 shadow-card transition-colors ${
          open ? 'border-navy-900' : 'border-slate-200 hover:border-slate-300'
        }`}
      >
        <MapPin className="h-4 w-4 text-orange-500 shrink-0" aria-hidden="true" />
        {selectedCity?.name || 'Select city'}
        <ChevronDown className={`h-4 w-4 text-ink-500 shrink-0 transition-transform ${open ? 'rotate-180' : ''}`} aria-hidden="true" />
      </button>

      {open && (
        <ul
          role="listbox"
          className="absolute right-0 z-30 mt-2 w-56 rounded-md border border-slate-100 bg-white py-1.5 shadow-popover max-h-80 overflow-y-auto"
        >
          {cities.map((c) => {
            const isSelected = c.id === selectedCityId
            return (
              <li key={c.id} role="option" aria-selected={isSelected}>
                <button
                  type="button"
                  onClick={() => { selectCity(c.id); setOpen(false) }}
                  className={`flex w-full items-center justify-between gap-2 px-4 py-2.5 text-sm text-left transition-colors ${
                    isSelected ? 'bg-navy-50 text-navy-900 font-medium' : 'text-ink-700 hover:bg-slate-50'
                  }`}
                >
                  <span>
                    {c.name}
                    <span className="text-ink-300 font-normal"> · {c.state}</span>
                  </span>
                  {isSelected && <Check className="h-4 w-4 text-orange-500 shrink-0" aria-hidden="true" />}
                </button>
              </li>
            )
          })}
        </ul>
      )}
    </div>
  )
}
