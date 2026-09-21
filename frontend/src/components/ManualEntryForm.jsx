import { PROBLEM_TYPES, SEVERITIES } from '../utils/constants'

function PillSelect({ options, value, onChange, colorFor }) {
  return (
    <div className="flex flex-wrap gap-1.5">
      {options.map((opt) => {
        const isActive = value === opt.value
        return (
          <button
            key={opt.value}
            type="button"
            onClick={() => onChange(opt.value)}
            aria-pressed={isActive}
            className={`pill-toggle ${isActive ? 'text-white border-transparent' : 'pill-toggle-inactive'}`}
            style={isActive ? { backgroundColor: colorFor ? colorFor(opt.value) : '#031D46' } : undefined}
          >
            {opt.label}
          </button>
        )
      })}
    </div>
  )
}

export default function ManualEntryForm({ problemType, setProblemType, severity, setSeverity }) {
  return (
    <div className="panel p-5 space-y-4">
      <div>
        <div className="label">Problem type</div>
        <PillSelect options={PROBLEM_TYPES} value={problemType} onChange={setProblemType} />
      </div>
      <div>
        <div className="label">Severity</div>
        <PillSelect
          options={SEVERITIES}
          value={severity}
          onChange={setSeverity}
          colorFor={(v) => SEVERITIES.find((s) => s.value === v)?.color}
        />
      </div>
    </div>
  )
}
