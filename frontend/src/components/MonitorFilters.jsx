import { PROBLEM_TYPES, SEVERITIES, STATUSES } from '../utils/constants'

function CheckboxGroup({ label, options, selected, onToggle }) {
  return (
    <div>
      <div className="label mb-2.5">{label}</div>
      <div className="flex flex-wrap gap-1.5">
        {options.map((opt) => {
          const isActive = selected.includes(opt.value)
          return (
            <button
              key={opt.value}
              type="button"
              onClick={() => onToggle(opt.value)}
              aria-pressed={isActive}
              className={`pill-toggle ${isActive ? 'pill-toggle-active' : 'pill-toggle-inactive'}`}
            >
              {opt.label}
            </button>
          )
        })}
      </div>
    </div>
  )
}

export default function MonitorFilters({ filters, setFilters, wards }) {
  function toggle(field, value) {
    setFilters((prev) => {
      const current = prev[field]
      const next = current.includes(value) ? current.filter((v) => v !== value) : [...current, value]
      return { ...prev, [field]: next }
    })
  }

  return (
    <div className="panel p-4 space-y-4">
      <CheckboxGroup
        label="Problem type"
        options={PROBLEM_TYPES}
        selected={filters.problem_type}
        onToggle={(v) => toggle('problem_type', v)}
      />
      <CheckboxGroup
        label="Severity"
        options={SEVERITIES}
        selected={filters.severity}
        onToggle={(v) => toggle('severity', v)}
      />
      <CheckboxGroup
        label="Status"
        options={STATUSES}
        selected={filters.status}
        onToggle={(v) => toggle('status', v)}
      />

      {wards && wards.length > 0 && (
        <div>
          <label className="label" htmlFor="ward-filter">Ward / area</label>
          <select
            id="ward-filter"
            className="input"
            value={filters.ward_id || ''}
            onChange={(e) => setFilters((prev) => ({ ...prev, ward_id: e.target.value || null }))}
          >
            <option value="">All wards</option>
            {wards.map((w) => (
              <option key={w.id} value={w.id}>{w.name}</option>
            ))}
          </select>
        </div>
      )}

      <div className="grid grid-cols-2 gap-2">
        <div>
          <label className="label" htmlFor="date-from">From</label>
          <input
            id="date-from"
            type="date"
            className="input"
            value={filters.date_from || ''}
            onChange={(e) => setFilters((prev) => ({ ...prev, date_from: e.target.value || null }))}
          />
        </div>
        <div>
          <label className="label" htmlFor="date-to">To</label>
          <input
            id="date-to"
            type="date"
            className="input"
            value={filters.date_to || ''}
            onChange={(e) => setFilters((prev) => ({ ...prev, date_to: e.target.value || null }))}
          />
        </div>
      </div>

      <button
        type="button"
        className="btn-secondary w-full"
        onClick={() => setFilters({ problem_type: [], severity: [], status: [], ward_id: null, date_from: null, date_to: null })}
      >
        Clear filters
      </button>
    </div>
  )
}
