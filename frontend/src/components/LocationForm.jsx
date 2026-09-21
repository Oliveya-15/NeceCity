import { LocateFixed } from 'lucide-react'

const ROAD_IMPORTANCE_OPTIONS = [
  { value: 'local', label: 'Local / residential street' },
  { value: 'arterial', label: 'Arterial / main city road' },
  { value: 'highway', label: 'Highway' },
]

export default function LocationForm({ location, setLocation, wards }) {
  function useMyLocation() {
    if (!navigator.geolocation) return
    navigator.geolocation.getCurrentPosition(
      (pos) => setLocation((prev) => ({ ...prev, latitude: pos.coords.latitude.toFixed(6), longitude: pos.coords.longitude.toFixed(6) })),
      () => { /* user denied or unavailable - they can still enter coordinates manually */ }
    )
  }

  return (
    <div className="panel p-4 space-y-3">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-semibold text-ink-900">Where was this photo taken?</h3>
        <button type="button" className="text-xs text-orange-500 hover:text-orange-600 font-medium inline-flex items-center gap-1" onClick={useMyLocation}>
          <LocateFixed className="h-3.5 w-3.5" /> Use my location
        </button>
      </div>

      <div className="grid grid-cols-2 gap-3">
        <div>
          <label className="label" htmlFor="lat">Latitude</label>
          <input id="lat" type="number" step="any" className="input" value={location.latitude}
            onChange={(e) => setLocation((prev) => ({ ...prev, latitude: e.target.value }))} required />
        </div>
        <div>
          <label className="label" htmlFor="lng">Longitude</label>
          <input id="lng" type="number" step="any" className="input" value={location.longitude}
            onChange={(e) => setLocation((prev) => ({ ...prev, longitude: e.target.value }))} required />
        </div>
      </div>

      <div>
        <label className="label" htmlFor="road-name">Road / landmark name</label>
        <input id="road-name" type="text" className="input" placeholder="e.g. Sevoke Road, near City Bus Terminus"
          value={location.road_name} onChange={(e) => setLocation((prev) => ({ ...prev, road_name: e.target.value }))} />
      </div>

      <div className="grid grid-cols-2 gap-3">
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
  )
}
