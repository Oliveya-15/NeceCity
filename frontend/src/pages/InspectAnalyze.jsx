import { useState } from 'react'
import { AlertTriangle, CheckCircle2, PlusCircle, RefreshCw } from 'lucide-react'
import AppLayout from '../layouts/AppLayout'
import UploadDropzone from '../components/UploadDropzone'
import BoundingBoxOverlay from '../components/BoundingBoxOverlay'
import DetectionReviewCard from '../components/DetectionReviewCard'
import LocationForm from '../components/LocationForm'
import ManualEntryForm from '../components/ManualEntryForm'
import { LoadingState } from '../components/StateViews'
import { useCity } from '../hooks/CityContext'
import { useApi } from '../hooks/useApi'
import { api, ApiError } from '../services/api'

function initialLocation() {
  return {
    latitude: '', longitude: '', road_name: '', road_importance: 'local',
    ward_id: null, near_important_infrastructure: false, infrastructure_note: '',
  }
}

export default function InspectAnalyze() {
  const { selectedCityId } = useCity()
  const { data: wards } = useApi(() => api.listWards(selectedCityId), [selectedCityId], { skip: !selectedCityId })

  const [file, setFile] = useState(null)
  const [previewUrl, setPreviewUrl] = useState(null)
  const [analyzing, setAnalyzing] = useState(false)
  const [analyzeError, setAnalyzeError] = useState(null)
  const [result, setResult] = useState(null) // AnalyzeImageResponse
  const [reviewStates, setReviewStates] = useState({}) // key -> {status, severity}
  const [activeIndex, setActiveIndex] = useState(null)
  const [location, setLocation] = useState(initialLocation())
  const [submitting, setSubmitting] = useState({}) // key -> bool
  const [confirmedCount, setConfirmedCount] = useState(0)

  // Manual-entry fallback state (used when no model is configured, when
  // the model found nothing, or when the user wants to log something
  // the model missed).
  const [showManualEntry, setShowManualEntry] = useState(false)
  const [manualType, setManualType] = useState('pothole')
  const [manualSeverity, setManualSeverity] = useState('medium')
  const [manualSubmitting, setManualSubmitting] = useState(false)

  function reset() {
    setFile(null); setPreviewUrl(null); setResult(null); setReviewStates({})
    setActiveIndex(null); setLocation(initialLocation()); setConfirmedCount(0); setAnalyzeError(null)
    setShowManualEntry(false); setManualType('pothole'); setManualSeverity('medium')
  }

  async function handleFileSelected(f) {
    setFile(f)
    setPreviewUrl(URL.createObjectURL(f))
    setResult(null)
    setAnalyzeError(null)
    setAnalyzing(true)
    try {
      const res = await api.analyzeImage(f)
      const withKeys = res.detections.map((d, i) => ({ ...d, _key: `${res.image_id}-${i}` }))
      setResult({ ...res, detections: withKeys })
      const initialStates = {}
      withKeys.forEach((d) => { initialStates[d._key] = { status: 'pending', severity: d.severity_suggested } })
      setReviewStates(initialStates)
      // Open the manual-entry section automatically whenever there's
      // nothing for the model-driven flow to show, or the model's own
      // training data means its output can't be trusted anyway - this is
      // the fix for the page previously dead-ending when no model was
      // configured (and now, when a model exists but was only trained on
      // synthetic placeholder data).
      setShowManualEntry(!res.model_available || res.detections.length === 0 || !!res.training_data_warning)
    } catch (err) {
      setAnalyzeError(err)
    } finally {
      setAnalyzing(false)
    }
  }

  function locationPayload() {
    return {
      latitude: parseFloat(location.latitude),
      longitude: parseFloat(location.longitude),
      city_id: selectedCityId,
      ward_id: location.ward_id ? Number(location.ward_id) : null,
      road_name: location.road_name || null,
      road_importance: location.road_importance,
      near_important_infrastructure: location.near_important_infrastructure,
      infrastructure_note: location.infrastructure_note || null,
    }
  }

  async function handleConfirm(detection) {
    if (!location.latitude || !location.longitude) {
      window.alert('Please enter (or use) a location before confirming a detection.')
      return
    }
    setSubmitting((prev) => ({ ...prev, [detection._key]: true }))
    try {
      await api.verifyDetection(detection.id, {
        action: 'confirm',
        final_severity: reviewStates[detection._key].severity,
        ...locationPayload(),
      })
      setReviewStates((prev) => ({ ...prev, [detection._key]: { ...prev[detection._key], status: 'confirmed' } }))
      setConfirmedCount((c) => c + 1)
    } catch (err) {
      window.alert(err instanceof ApiError ? err.message : 'Failed to confirm detection.')
    } finally {
      setSubmitting((prev) => ({ ...prev, [detection._key]: false }))
    }
  }

  async function handleReject(detection) {
    setSubmitting((prev) => ({ ...prev, [detection._key]: true }))
    try {
      await api.verifyDetection(detection.id, {
        action: 'reject', latitude: 0, longitude: 0, city_id: selectedCityId,
      })
      setReviewStates((prev) => ({ ...prev, [detection._key]: { ...prev[detection._key], status: 'rejected' } }))
    } catch (err) {
      window.alert(err instanceof ApiError ? err.message : 'Failed to reject detection.')
    } finally {
      setSubmitting((prev) => ({ ...prev, [detection._key]: false }))
    }
  }

  async function handleManualSubmit() {
    if (!location.latitude || !location.longitude) {
      window.alert('Please enter (or use) a location before logging a problem.')
      return
    }
    setManualSubmitting(true)
    try {
      await api.createManualProblem({
        problem_type: manualType,
        severity: manualSeverity,
        image_id: result?.image_id ?? null,
        ...locationPayload(),
      })
      setConfirmedCount((c) => c + 1)
      setShowManualEntry(false)
    } catch (err) {
      window.alert(err instanceof ApiError ? err.message : 'Failed to log problem.')
    } finally {
      setManualSubmitting(false)
    }
  }

  const hasDetections = result && result.detections.length > 0

  return (
    <AppLayout title="Inspect & Analyze" description="Upload a street photo for automatic problem detection">
      <div className="max-w-5xl space-y-6">
        {!file && <UploadDropzone onFileSelected={handleFileSelected} />}

        {file && (
          <div className="flex justify-end">
            <button className="btn-secondary" onClick={reset}>
              <RefreshCw className="h-4 w-4" /> Analyze a different photo
            </button>
          </div>
        )}

        {analyzing && <LoadingState label="Running detection model" />}

        {analyzeError && (
          <div className="panel p-5 flex items-start gap-2.5 border-danger/20 bg-danger/[0.04] text-danger text-sm">
            <AlertTriangle className="h-4 w-4 shrink-0 mt-0.5" />
            {analyzeError.message}
          </div>
        )}

        {result && !result.model_available && (
          <div className="panel p-5 flex items-start gap-2.5 border-warning/20 bg-warning-bg text-warning text-sm">
            <AlertTriangle className="h-4 w-4 shrink-0 mt-0.5" />
            <div>
              <p className="font-medium">ML model not configured yet.</p>
              <p className="text-ink-500 mt-1">
                {result.message} The photo was saved — use manual entry below to log the problem yourself in the
                meantime; nothing is lost. See <code className="text-xs bg-white px-1 py-0.5 rounded border border-slate-100">ml/weights/README.md</code> to train and install a model.
              </p>
            </div>
          </div>
        )}

        {result && result.model_available && result.training_data_warning && (
          <div className="panel p-5 flex items-start gap-2.5 border-warning/20 bg-warning-bg text-warning text-sm">
            <AlertTriangle className="h-4 w-4 shrink-0 mt-0.5" />
            <div>
              <p className="font-medium">Model trained on placeholder data — real-world accuracy will be poor.</p>
              <p className="text-ink-500 mt-1">{result.training_data_warning}</p>
            </div>
          </div>
        )}

        {result && result.model_available && result.detections.length === 0 && (
          <div className="panel p-5 flex items-start gap-2.5 text-sm text-ink-700">
            <CheckCircle2 className="h-4 w-4 shrink-0 mt-0.5 text-success" />
            No infrastructure problems were detected in this image with sufficient confidence. You can still log one manually below if you can see a problem the model missed.
          </div>
        )}

        {previewUrl && hasDetections && (
          <div className="grid lg:grid-cols-[1fr_360px] gap-6 items-start">
            <BoundingBoxOverlay imageUrl={previewUrl} detections={result.detections} activeDetectionIndex={activeIndex} />

            <div className="space-y-4">
              <LocationForm location={location} setLocation={setLocation} wards={wards} />
              <div className="space-y-3">
                {result.detections.map((det, i) => (
                  <DetectionReviewCard
                    key={det._key}
                    detection={det}
                    reviewState={reviewStates[det._key]}
                    isActive={activeIndex === i}
                    onHover={() => setActiveIndex(i)}
                    onSeverityChange={(sev) => setReviewStates((prev) => ({ ...prev, [det._key]: { ...prev[det._key], severity: sev } }))}
                    onConfirm={() => handleConfirm(det)}
                    onReject={() => handleReject(det)}
                    disabled={submitting[det._key]}
                  />
                ))}
              </div>
            </div>
          </div>
        )}

        {previewUrl && !hasDetections && !analyzing && !analyzeError && (
          <img src={previewUrl} alt="Uploaded street scene" className="max-w-md rounded-lg border border-slate-100 shadow-card" />
        )}

        {/* Manual-entry fallback: the fix for this page previously
            dead-ending with no way to proceed when no model is trained. */}
        {result && !showManualEntry && (
          <button className="btn-secondary" onClick={() => setShowManualEntry(true)}>
            <PlusCircle className="h-4 w-4" /> Log a problem manually
          </button>
        )}

        {result && showManualEntry && (
          <div className="grid lg:grid-cols-2 gap-4 items-start">
            <ManualEntryForm
              problemType={manualType} setProblemType={setManualType}
              severity={manualSeverity} setSeverity={setManualSeverity}
            />
            <div className="space-y-4">
              <LocationForm location={location} setLocation={setLocation} wards={wards} />
              <button className="btn-accent w-full" onClick={handleManualSubmit} disabled={manualSubmitting}>
                <PlusCircle className="h-4 w-4" /> Log this problem
              </button>
            </div>
          </div>
        )}

        {confirmedCount > 0 && (
          <div className="panel p-5 flex items-center gap-2.5 text-sm text-success bg-success-bg border-success/20">
            <CheckCircle2 className="h-4 w-4 shrink-0" />
            {confirmedCount} problem{confirmedCount > 1 ? 's' : ''} added — visible now on City Monitor and Action Center.
          </div>
        )}
      </div>
    </AppLayout>
  )
}
