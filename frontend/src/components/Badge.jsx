import { AlertCircle, CheckCircle2, CircleDot, Eye, OctagonAlert, TriangleAlert, Wrench } from 'lucide-react'
import { severityMeta, statusMeta } from '../utils/constants'

const SEVERITY_ICON = {
  low: CircleDot,
  medium: AlertCircle,
  high: TriangleAlert,
  critical: OctagonAlert,
}

const STATUS_ICON = {
  detected: Eye,
  verified: CheckCircle2,
  in_progress: Wrench,
  resolved: CheckCircle2,
}

function Badge({ label, color, bg, Icon }) {
  return (
    <span className="pill" style={{ color, backgroundColor: bg }}>
      <Icon className="h-3 w-3" aria-hidden="true" />
      {label}
    </span>
  )
}

export function SeverityBadge({ severity }) {
  const meta = severityMeta(severity)
  return <Badge label={meta.label} color={meta.color} bg={meta.bg} Icon={SEVERITY_ICON[severity] || CircleDot} />
}

export function StatusBadge({ status }) {
  const meta = statusMeta(status)
  return <Badge label={meta.label} color={meta.color} bg={meta.bg} Icon={STATUS_ICON[status] || Eye} />
}
