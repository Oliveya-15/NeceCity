import { severityMeta, typeLabel } from '../utils/constants'

export default function BoundingBoxOverlay({ imageUrl, detections, activeDetectionIndex }) {
  return (
    <div className="relative inline-block w-full">
      <img src={imageUrl} alt="Uploaded street scene for analysis" className="w-full rounded-md border border-line" />
      {detections.map((det, i) => {
        const sev = severityMeta(det.severity)
        const isActive = i === activeDetectionIndex
        const { x_min, y_min, x_max, y_max } = det.bbox
        return (
          <div
            key={i}
            className="absolute border-2 rounded-sm transition-opacity"
            style={{
              left: `${x_min * 100}%`,
              top: `${y_min * 100}%`,
              width: `${(x_max - x_min) * 100}%`,
              height: `${(y_max - y_min) * 100}%`,
              borderColor: sev.color,
              opacity: isActive || activeDetectionIndex === null ? 1 : 0.35,
              boxShadow: isActive ? `0 0 0 2px ${sev.color}55` : 'none',
            }}
          >
            <span
              className="absolute -top-6 left-0 text-xs font-medium px-1.5 py-0.5 rounded-sm whitespace-nowrap text-white"
              style={{ backgroundColor: sev.color }}
            >
              {typeLabel(det.problem_type)} · {Math.round(det.confidence * 100)}%
            </span>
          </div>
        )
      })}
    </div>
  )
}
