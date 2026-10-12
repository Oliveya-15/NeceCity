import { useRef, useState } from 'react'
import { severityMeta, typeLabel } from '../utils/constants'

const CLICK_BOX_SIZE = 0.14 // a plain click (no drag) marks a box this big (fraction of the image)
const MIN_DRAG_SIZE = 0.02 // drags smaller than this in either direction are ignored
const DRAFT_COLOR = '#E15400'

const clamp01 = (v) => Math.min(1, Math.max(0, v))

/**
 * Shows the uploaded photo with detection boxes. When `drawMode` is on, the
 * user can drag a rectangle (mouse or touch) - or just click - around a
 * problem the model missed; `onDraw` receives a normalized
 * { x_min, y_min, x_max, y_max } box. `draftBox` is the box currently being
 * confirmed (drawn dashed).
 */
export default function BoundingBoxOverlay({
  imageUrl, detections = [], activeDetectionIndex = null, drawMode = false, draftBox = null, onDraw,
}) {
  const containerRef = useRef(null)
  const [dragStart, setDragStart] = useState(null)
  const [dragNow, setDragNow] = useState(null)

  function toNormalized(e) {
    const rect = containerRef.current.getBoundingClientRect()
    return {
      x: clamp01((e.clientX - rect.left) / rect.width),
      y: clamp01((e.clientY - rect.top) / rect.height),
    }
  }

  function handlePointerDown(e) {
    if (!drawMode) return
    e.preventDefault()
    e.currentTarget.setPointerCapture?.(e.pointerId)
    const pt = toNormalized(e)
    setDragStart(pt)
    setDragNow(pt)
  }

  function handlePointerMove(e) {
    if (!dragStart) return
    setDragNow(toNormalized(e))
  }

  function handlePointerUp(e) {
    if (!dragStart) return
    const end = toNormalized(e)
    const w = Math.abs(end.x - dragStart.x)
    const h = Math.abs(end.y - dragStart.y)
    let box
    if (w < MIN_DRAG_SIZE && h < MIN_DRAG_SIZE) {
      // treat as a click: centre a default-size box on the point, kept inside the image
      const half = CLICK_BOX_SIZE / 2
      const cx = Math.min(1 - half, Math.max(half, end.x))
      const cy = Math.min(1 - half, Math.max(half, end.y))
      box = { x_min: cx - half, y_min: cy - half, x_max: cx + half, y_max: cy + half }
    } else if (w < MIN_DRAG_SIZE || h < MIN_DRAG_SIZE) {
      box = null // a thin sliver is almost certainly an accident
    } else {
      box = {
        x_min: Math.min(dragStart.x, end.x), y_min: Math.min(dragStart.y, end.y),
        x_max: Math.max(dragStart.x, end.x), y_max: Math.max(dragStart.y, end.y),
      }
    }
    setDragStart(null)
    setDragNow(null)
    if (box && onDraw) onDraw(box)
  }

  const liveBox = dragStart && dragNow
    ? {
        x_min: Math.min(dragStart.x, dragNow.x), y_min: Math.min(dragStart.y, dragNow.y),
        x_max: Math.max(dragStart.x, dragNow.x), y_max: Math.max(dragStart.y, dragNow.y),
      }
    : null
  const shownDraft = liveBox || draftBox

  return (
    <div ref={containerRef} className="relative inline-block w-full select-none">
      <img
        src={imageUrl}
        alt="Uploaded street scene for analysis"
        className="w-full rounded-md border border-line"
        draggable={false}
      />

      {detections.map((det, i) => {
        const sev = severityMeta(det.severity_suggested)
        const isActive = i === activeDetectionIndex
        const { x_min, y_min, x_max, y_max } = det.bbox
        const byUser = det.source === 'user'
        return (
          <div
            key={det._key || i}
            className="absolute border-2 rounded-sm transition-opacity pointer-events-none"
            style={{
              left: `${x_min * 100}%`,
              top: `${y_min * 100}%`,
              width: `${(x_max - x_min) * 100}%`,
              height: `${(y_max - y_min) * 100}%`,
              borderColor: sev.color,
              borderStyle: det.low_confidence ? 'dashed' : 'solid',
              opacity: isActive || activeDetectionIndex === null ? 1 : 0.35,
              boxShadow: isActive ? `0 0 0 2px ${sev.color}55` : 'none',
            }}
          >
            <span
              className="absolute -top-6 left-0 text-xs font-medium px-1.5 py-0.5 rounded-sm whitespace-nowrap text-white"
              style={{ backgroundColor: sev.color }}
            >
              {typeLabel(det.problem_type)} · {byUser ? 'marked by you' : `${Math.round(det.confidence * 100)}%`}
            </span>
          </div>
        )
      })}

      {shownDraft && (
        <div
          className="absolute border-2 border-dashed rounded-sm pointer-events-none"
          style={{
            left: `${shownDraft.x_min * 100}%`,
            top: `${shownDraft.y_min * 100}%`,
            width: `${(shownDraft.x_max - shownDraft.x_min) * 100}%`,
            height: `${(shownDraft.y_max - shownDraft.y_min) * 100}%`,
            borderColor: DRAFT_COLOR,
            backgroundColor: `${DRAFT_COLOR}22`,
          }}
        />
      )}

      {drawMode && (
        <div
          className="absolute inset-0 rounded-md cursor-crosshair ring-2 ring-orange-500/70"
          style={{ touchAction: 'none' }}
          onPointerDown={handlePointerDown}
          onPointerMove={handlePointerMove}
          onPointerUp={handlePointerUp}
          onPointerCancel={() => { setDragStart(null); setDragNow(null) }}
        />
      )}
    </div>
  )
}
