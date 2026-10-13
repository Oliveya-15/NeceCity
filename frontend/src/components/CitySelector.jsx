import { useEffect, useRef, useState } from 'react'
import { Check, ChevronDown, MapPin } from 'lucide-react'
import { useCity } from '../hooks/CityContext'

// Cities that actually have data. They are shown first; every other city is
// listed below them with a "Demo" tag. To show ONLY these cities (hide the
// rest completely), set SHOW_DEMO_CITIES to false.
const DATA_CITY_SLUGS = ['siliguri', 'kolkata']
const SHOW_DEMO_CITIES = true

const STORAGE_KEY = 'nececity.selectedCitySlug'

export default function CitySelector() {
  const { cities, selectedCity, selectedCityId, selectCity, loading } = useCity()
  const [open, setOpen] = useState(false)
  const containerRef = useRef(null)
  const defaultApplied = useRef(false)

  // Data cities first (in the order above), then the rest alphabetically.
  const dataCities = DATA_CITY_SLUGS
    .map((slug) => cities.find((c) => c.slug === slug))
    .filter(Boolean)
  const demoCities = SHOW_DEMO_CITIES
    ? cities.filter((c) => !DATA_CITY_SLUGS.includes(c.slug))
    : []

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

  // First visit only: the app picks the first city alphabetically, which is a
  // demo city with no data. Start on Siliguri instead (unless the visitor has
  // already chosen a city before).
  useEffect(() => {
    if (defaultApplied.current || loading || cities.length === 0) return
    defaultApplied.current = true
    let saved = null
    try {
      saved = localStorage.getItem(STORAGE_KEY)
    } catch {
      /* storage unavailable */
    }
    if (saved) return
    if (dataCities.length > 0 && selectedCity && !DATA_CITY_SLUGS.includes(selectedCity.slug)) {
      selectCity(dataCities[0].id)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [loading, cities])

  if (loading) return <div className="h-10 w-40 rounded-full bg-slate-100 animate-pulse" aria-hidden="true" />
  if (cities.length === 0) return null

  function renderCity(c, isDemo) {
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
          <span className="flex items-center gap-2 min-w-0">
            <span className="truncate">
              {c.name}
              <span className="text-ink-300 font-normal"> · {c.state}</span>
            </span>
            {isDemo && (
              <span
                title="Demo only - no real data for this city yet"
                className="shrink-0 rounded-full bg-slate-100 px-2 py-0.5 text-[10px] font-medium uppercase tracking-wide text-ink-500"
              >
                Demo
              </span>
            )}
          </span>
          {isSelected && <Check className="h-4 w-4 text-orange-500 shrink-0" aria-hidden="true" />}
        </button>
      </li>
    )
  }

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
          className="absolute right-0 z-30 mt-2 w-64 rounded-md border border-slate-100 bg-white py-1.5 shadow-popover max-h-80 overflow-y-auto"
        >
          {dataCities.map((c) => renderCity(c, false))}

          {demoCities.length > 0 && (
            <>
              <li role="presentation" className="mt-1.5 border-t border-slate-100 px-4 pt-2 pb-1 text-[11px] font-medium uppercase tracking-wide text-ink-300">
                Demo cities (no data yet)
              </li>
              {demoCities.map((c) => renderCity(c, true))}
            </>
          )}
        </ul>
      )}
    </div>
  )
}