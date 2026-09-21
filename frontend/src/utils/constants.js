/**
 * Shared vocabulary for problem types, severities and statuses. Keeping
 * labels/colors here (rather than inline in components) means the
 * severity/status vocabulary defined in the backend
 * (app/models/enums.py) has exactly one frontend counterpart to update.
 */
export const PROBLEM_TYPES = [
  { value: 'pothole', label: 'Pothole' },
  { value: 'road_damage', label: 'Road Damage' },
  { value: 'garbage', label: 'Garbage' },
  { value: 'waterlogging', label: 'Waterlogging' },
  { value: 'damaged_road_sign', label: 'Damaged Road Sign' },
  { value: 'open_drain', label: 'Open Drain' },
]

export const SEVERITIES = [
  { value: 'low', label: 'Low', color: '#2563A8', bg: '#E9F1FA' },
  { value: 'medium', label: 'Medium', color: '#B4680A', bg: '#FDF1E2' },
  { value: 'high', label: 'High', color: '#E15400', bg: '#FFE8D9' },
  { value: 'critical', label: 'Critical', color: '#C6303E', bg: '#FBEAEC' },
]

export const STATUSES = [
  { value: 'detected', label: 'Detected', color: '#5B6472', bg: '#EEF1F4' },
  { value: 'verified', label: 'Verified', color: '#2563A8', bg: '#E9F1FA' },
  { value: 'in_progress', label: 'In Progress', color: '#B4680A', bg: '#FDF1E2' },
  { value: 'resolved', label: 'Resolved', color: '#1E8E5A', bg: '#E8F5EE' },
]

export const STATUS_ORDER = ['detected', 'verified', 'in_progress', 'resolved']

export function typeLabel(value) {
  return PROBLEM_TYPES.find((t) => t.value === value)?.label || value
}

export function severityMeta(value) {
  return SEVERITIES.find((s) => s.value === value) || SEVERITIES[0]
}

export function statusMeta(value) {
  return STATUSES.find((s) => s.value === value) || STATUSES[0]
}
