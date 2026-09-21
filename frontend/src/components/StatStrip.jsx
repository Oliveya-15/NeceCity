import { formatNumber } from '../utils/format'

/**
 * A grid of individual stat cards (icon + label + big number), each with
 * its own soft shadow and rounded corners - the civic-SaaS card pattern
 * used throughout the dashboard.
 */
export default function StatStrip({ items }) {
  return (
    <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-4">
      {items.map((item) => (
        <div key={item.label} className="panel panel-hover p-5">
          <div className="flex items-center gap-2.5 mb-3">
            {item.icon && (
              <span
                className="flex h-8 w-8 items-center justify-center rounded-full shrink-0"
                style={{ backgroundColor: `${item.color || '#0B2A52'}18`, color: item.color || '#0B2A52' }}
              >
                <item.icon className="h-4 w-4" aria-hidden="true" />
              </span>
            )}
            <div className="text-xs font-semibold text-ink-500 leading-snug">{item.label}</div>
          </div>
          <div className="flex items-baseline gap-1.5">
            <span className="text-2xl font-bold tabular-nums tracking-tight" style={{ color: item.color || '#0F172A' }}>
              {typeof item.value === 'number' ? formatNumber(item.value) : item.value}
            </span>
            {item.suffix && <span className="text-xs text-ink-500">{item.suffix}</span>}
          </div>
        </div>
      ))}
    </div>
  )
}
