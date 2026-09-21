import { CircleMarker, MapContainer, Popup, TileLayer, useMap } from 'react-leaflet'
import { useEffect } from 'react'
import { severityMeta, typeLabel } from '../utils/constants'
import { formatRelative } from '../utils/format'

function RecenterOnCityChange({ center, zoom }) {
  const map = useMap()
  useEffect(() => {
    map.setView(center, zoom)
  }, [center[0], center[1], zoom]) // eslint-disable-line react-hooks/exhaustive-deps
  return null
}

export default function MapView({ center, zoom, problems, onSelect }) {
  return (
    <MapContainer center={center} zoom={zoom} className="h-full w-full rounded-md" scrollWheelZoom>
      <TileLayer
        url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
        attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
      />
      <RecenterOnCityChange center={center} zoom={zoom} />
      {problems.map((p) => {
        const sev = severityMeta(p.severity)
        return (
          <CircleMarker
            key={p.id}
            center={[p.latitude, p.longitude]}
            radius={p.status === 'resolved' ? 5 : 7}
            pathOptions={{
              color: sev.color,
              fillColor: sev.color,
              fillOpacity: p.status === 'resolved' ? 0.25 : 0.75,
              opacity: p.status === 'resolved' ? 0.5 : 1,
              weight: 2,
            }}
            eventHandlers={{ click: () => onSelect?.(p) }}
          >
            <Popup>
              <div className="text-sm space-y-1 min-w-[180px]">
                <div className="font-semibold text-ink-900">{typeLabel(p.problem_type)}</div>
                <div className="text-ink-500">{p.road_name || 'Unnamed location'}</div>
                <div className="flex items-center justify-between pt-1">
                  <span style={{ color: sev.color }} className="font-medium capitalize">{p.severity}</span>
                  {p.risk_score !== null && <span className="text-ink-700">Risk: {Math.round(p.risk_score)}</span>}
                </div>
                <div className="text-xs text-ink-500">Last seen {formatRelative(p.last_detected_at)}</div>
              </div>
            </Popup>
          </CircleMarker>
        )
      })}
    </MapContainer>
  )
}
