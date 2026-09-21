import { useRef, useState } from 'react'
import { UploadCloud } from 'lucide-react'

const ACCEPTED_TYPES = ['image/jpeg', 'image/png', 'image/webp']
const MAX_SIZE_MB = 8

export default function UploadDropzone({ onFileSelected, disabled }) {
  const inputRef = useRef(null)
  const [dragActive, setDragActive] = useState(false)
  const [validationError, setValidationError] = useState(null)

  function validateAndEmit(file) {
    if (!file) return
    if (!ACCEPTED_TYPES.includes(file.type)) {
      setValidationError('Please upload a JPEG, PNG, or WebP image.')
      return
    }
    if (file.size > MAX_SIZE_MB * 1024 * 1024) {
      setValidationError(`File is larger than the ${MAX_SIZE_MB}MB limit.`)
      return
    }
    setValidationError(null)
    onFileSelected(file)
  }

  return (
    <div>
      <div
        role="button"
        tabIndex={0}
        onClick={() => !disabled && inputRef.current?.click()}
        onKeyDown={(e) => e.key === 'Enter' && !disabled && inputRef.current?.click()}
        onDragOver={(e) => { e.preventDefault(); if (!disabled) setDragActive(true) }}
        onDragLeave={() => setDragActive(false)}
        onDrop={(e) => {
          e.preventDefault()
          setDragActive(false)
          if (!disabled) validateAndEmit(e.dataTransfer.files?.[0])
        }}
        aria-disabled={disabled}
        className={`flex flex-col items-center justify-center gap-2 rounded-md border-2 border-dashed px-6 py-12 text-center cursor-pointer transition-colors ${
          dragActive ? 'border-orange-500 bg-orange-50' : 'border-line hover:border-ink-300'
        } ${disabled ? 'opacity-50 pointer-events-none' : ''}`}
      >
        <UploadCloud className="h-8 w-8 text-ink-500" aria-hidden="true" />
        <p className="text-sm font-medium text-ink-900">Click to upload or drag a street photo here</p>
        <p className="text-xs text-ink-500">JPEG, PNG or WebP — up to {MAX_SIZE_MB}MB</p>
        <input
          ref={inputRef}
          type="file"
          accept={ACCEPTED_TYPES.join(',')}
          className="sr-only"
          onChange={(e) => validateAndEmit(e.target.files?.[0])}
          disabled={disabled}
          aria-label="Upload street image"
        />
      </div>
      {validationError && <p className="text-sm text-danger mt-2" role="alert">{validationError}</p>}
    </div>
  )
}
