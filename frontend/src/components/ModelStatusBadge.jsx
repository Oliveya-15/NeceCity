import { useEffect, useRef, useState } from 'react'
import { AlertTriangle, Brain, CircleDot } from 'lucide-react'
import { api } from '../services/api'

export default function ModelStatusBadge() {
  const [status, setStatus] = useState(null)
  const [open, setOpen] = useState(false)
  const ref = useRef(null)

  useEffect(() => {
    api.getMlStatus().then(setStatus).catch(() => setStatus(null))
  }, [])

  useEffect(() => {
    function onClickOutside(e) {
      if (ref.current && !ref.current.contains(e.target)) setOpen(false)
    }
    document.addEventListener('mousedown', onClickOutside)
    return () => document.removeEventListener('mousedown', onClickOutside)
  }, [])

  if (!status) return null

  const hasWarning = status.model_available && status.training_data_warning
  const dotColor = !status.model_available ? '#94A3B8' : hasWarning ? '#B4680A' : '#1E8E5A'
  const label = !status.model_available ? 'Model not trained' : hasWarning ? 'Model needs real data' : 'Model active'

  return (
    <div className="relative hidden md:block" ref={ref}>
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        className="flex items-center gap-2 rounded-full border border-slate-200 bg-white pl-3 pr-3.5 py-2.5 text-xs font-medium text-ink-700 shadow-card hover:border-slate-300 transition-colors"
      >
        <Brain className="h-3.5 w-3.5 text-navy-900" aria-hidden="true" />
        <CircleDot className="h-2.5 w-2.5" style={{ color: dotColor }} aria-hidden="true" />
        {label}
      </button>

      {open && (
        <div className="absolute right-0 z-30 mt-2 w-72 rounded-md border border-slate-100 bg-white p-4 shadow-popover text-xs text-ink-700 leading-relaxed">
          {status.model_available ? (
            <>
              <p className="font-medium text-ink-900 mb-1">YOLO model loaded: {status.model_version}</p>
              {hasWarning ? (
                <p className="flex items-start gap-1.5 text-warning">
                  <AlertTriangle className="h-3.5 w-3.5 shrink-0 mt-0.5" />
                  {status.training_data_warning}
                </p>
              ) : (
                <p>Running local inference for Inspect &amp; Analyze - no external API involved.</p>
              )}
            </>
          ) : (
            <>
              <p className="font-medium text-ink-900 mb-1">No model configured</p>
              <p>{status.unavailable_reason || 'Train a model and set MODEL_PATH - see ml/weights/README.md.'} The rest of the app works normally without it.</p>
            </>
          )}
        </div>
      )}
    </div>
  )
}
