import { useState } from 'react'
import { MapContainer, Marker, TileLayer, useMapEvents } from 'react-leaflet'
import { ChevronDown, LocateFixed, MapPin } from 'lucide-react'

const ROAD_IMPORTANCE_OPTIONS = [
  { value: 'local', label: 'Local / residential street' },
  { value: 'arterial', label: 'Arterial / main city road' },
  { value: 'highway', label: 'Highway' },
]

// Free, no-API-key reverse geocoding via OpenStreetMap's Nominatim - used
// only to *suggest* a road/landmark name after the user picks a point, so
// they aren't forced to type coordinates or a name by hand. It's a
// best-effort convenience: if it fails or is slow, the user can still
// type a name themselves, and submission is never blocked on it.
async function reverseGeocode(lat, lng) {
  try {
    const res = await fetch(
      `https://nominatim.openstreetmap.org/reverse?format=jsonv2&lat=${lat}&lon=${lng}&zoom=17`
    )
    if (!res.ok) return null
    const data = await res.json()
    const addr = data.address || {}
    return addr.road || addr.suburb || addr.neighbourhood || data.display_name?.split(',')[0] || null
  } catch {
    return null // best-effort only - never block on this
  }
}

function ClickToPlaceMarker({ onPick }) {
  useMapEvents({
    click(e) {
      onPick(e.latlng.lat, e.latlng.lng)
    },
  })
  return null
}

export default function LocationPicker({ location, setLocation, wards, cityCenter, cityZoom }) {
  const [mapMode, setMapMode] = useState(false)
  const [locating, setLocating] = useState(false)
  const [geoError, setGeoError] = useState(false)
  const [detailsOpen, setDetailsOpen] = useState(false)

  const hasCoords = location.latitude && location.longitude

  async function applyCoords(lat, lng) {
    setLocation((prev) => ({ ...prev, latitude: lat.toFixed(6), longitude: lng.toFixed(6) }))
    if (!location.road_name) {
      const suggested = await reverseGeocode(lat, lng)
      if (suggested) setLocation((prev) => ({ ...prev, road_name: prev.road_name || suggested }))
    }
  }

  function useMyLocation() {
    if (!navigator.geolocation) {
      setGeoError(true)
      setMapMode(true)
      return
    }
    setLocating(true)
    setGeoError(false)
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        setLocating(false)
        applyCoords(pos.coords.latitude, pos.coords.longitude)
      },
      () => {
        setLocating(false)
        setGeoError(true)
        setMapMode(true) // geolocation denied/unavailable - fall back to map click, never raw lat/lng typing
      }
    )
  }

  return (
    <div className="panel p-5 space-y-4">
      <h3 className="text-sm font-semibold text-ink-900">Where is this?</h3>

      {!mapMode && (
        <button type="button" className="btn-accent w-full" onClick={useMyLocation} disabled={locating}>
          <LocateFixed className="h-4 w-4" />
          {locating ? 'Getting your location...' : 'Use my location'}
        </button>
      )}

      {geoError && (
        <p className="text-xs text-warning">Couldn't access your location - tap the map below to set it instead.</p>
      )}

      {!mapMode && !geoError && (
        <button type="button" className="text-xs text-ink-500 hover:text-ink-900 underline underline-offset-2" onClick={() => setMapMode(true)}>
          Or pick the location on a map
        </button>
      )}

      {mapMode && (
        <div className="h-56 rounded-md overflow-hidden border border-slate-100">
          <MapContainer
            center={hasCoords ? [Number(location.latitude), Number(location.longitude)] : cityCenter}
            zoom={hasCoords ? 16 : cityZoom}
            className="h-full w-full"
          >
            <TileLayer
              url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
              attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
            />
            <ClickToPlaceMarker onPick={applyCoords} />
            {hasCoords && <Marker position={[Number(location.latitude), Number(location.longitude)]} />}
          </MapContainer>
        </div>
      )}

      {hasCoords ? (
        <div className="flex items-center gap-2 text-sm text-ink-700 bg-slate-50 rounded-md px-3 py-2.5">
          <MapPin className="h-4 w-4 text-orange-500 shrink-0" />
          <span className="tabular-nums">{Number(location.latitude).toFixed(5)}, {Number(location.longitude).toFixed(5)}</span>
        </div>
      ) : (
        <p className="text-xs text-ink-500">No location set yet.</p>
      )}

      <div>
        <label className="label" htmlFor="road-name">Landmark or road name (optional)</label>
        <input
          id="road-name"
          type="text"
          className="input"
          placeholder="e.g. Sevoke Road, near City Bus Terminus"
          value={location.road_name}
          onChange={(e) => setLocation((prev) => ({ ...prev, road_name: e.target.value }))}
        />
      </div>

      <button
        type="button"
        className="flex items-center gap-1.5 text-xs text-ink-500 hover:text-ink-900"
        onClick={() => setDetailsOpen((o) => !o)}
        aria-expanded={detailsOpen}
      >
        <ChevronDown className={`h-3.5 w-3.5 transition-transform ${detailsOpen ? 'rotate-180' : ''}`} />
        More details (optional)
      </button>

      {detailsOpen && (
        <div className="space-y-3 pt-1 border-t border-slate-100">
          <div className="grid grid-cols-2 gap-3 pt-3">
            <div>
              <label className="label" htmlFor="road-importance">Road type</label>
              <select id="road-importance" className="input" value={location.road_importance}
                onChange={(e) => setLocation((prev) => ({ ...prev, road_importance: e.target.value }))}>
                {ROAD_IMPORTANCE_OPTIONS.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
              </select>
            </div>
            {wards && wards.length > 0 && (
              <div>
                <label className="label" htmlFor="ward">Ward / area</label>
                <select id="ward" className="input" value={location.ward_id || ''}
                  onChange={(e) => setLocation((prev) => ({ ...prev, ward_id: e.target.value || null }))}>
                  <option value="">Not specified</option>
                  {wards.map((w) => <option key={w.id} value={w.id}>{w.name}</option>)}
                </select>
              </div>
            )}
          </div>

          <label className="flex items-center gap-2 text-sm text-ink-700">
            <input type="checkbox" checked={location.near_important_infrastructure}
              onChange={(e) => setLocation((prev) => ({ ...prev, near_important_infrastructure: e.target.checked }))} />
            Near critical infrastructure (hospital, school, transit hub, ...)
          </label>

          {location.near_important_infrastructure && (
            <input type="text" className="input" placeholder="e.g. Siliguri District Hospital"
              value={location.infrastructure_note} onChange={(e) => setLocation((prev) => ({ ...prev, infrastructure_note: e.target.value }))} />
          )}
        </div>
      )}
    </div>
  )
}