import { useState } from 'react'
import { Link } from 'react-router-dom'
import { AlertTriangle, CheckCircle2, Info, MapPinned, PenLine, PlusCircle, RefreshCw } from 'lucide-react'
import AppLayout from '../layouts/AppLayout'
import UploadDropzone from '../components/UploadDropzone'
import BoundingBoxOverlay from '../components/BoundingBoxOverlay'
import DetectionReviewCard from '../components/DetectionReviewCard'
import LocationPicker from '../components/LocationPicker'
import ManualEntryForm from '../components/ManualEntryForm'
import RegionDraftPanel from '../components/RegionDraftPanel'
import ReportReviewSummary from '../components/ReportReviewSummary'
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

export default function ReportProblem() {
  const { selectedCityId, selectedCity } = useCity()
  const { data: wards } = useApi(() => api.listWards(selectedCityId), [selectedCityId], { skip: !selectedCityId })

  // 'upload' (covers the upload + analyzing moment) -> 'review' -> 'confirm' -> 'success'
  const [stage, setStage] = useState('upload')

  const [file, setFile] = useState(null)
  const [previewUrl, setPreviewUrl] = useState(null)
  const [analyzing, setAnalyzing] = useState(false)
  const [analyzeError, setAnalyzeError] = useState(null)
  const [result, setResult] = useState(null)
  const [reviewStates, setReviewStates] = useState({})
  const [activeIndex, setActiveIndex] = useState(null)

  const [location, setLocation] = useState(initialLocation())

  const [showManualEntry, setShowManualEntry] = useState(false)
  const [manualType, setManualType] = useState('pothole')
  const [manualSeverity, setManualSeverity] = useState('medium')
  const [manualItems, setManualItems] = useState([]) // [{key, problemType, severity}]

  // "Mark the problem on the photo" flow (for problems the model missed)
  const [drawMode, setDrawMode] = useState(false)
  const [draftBox, setDraftBox] = useState(null)
  const [draftType, setDraftType] = useState('pothole')
  const [draftSeverity, setDraftSeverity] = useState('medium')
  const [savingRegion, setSavingRegion] = useState(false)
  const [regionError, setRegionError] = useState(null)

  const [submitting, setSubmitting] = useState(false)
  const [submitError, setSubmitError] = useState(null)
  const [submittedReports, setSubmittedReports] = useState([]) // [{problemId, problemType, summary}]

  function resetAll() {
    setStage('upload')
    setFile(null); setPreviewUrl(null); setResult(null); setReviewStates({})
    setActiveIndex(null); setLocation(initialLocation())
    setShowManualEntry(false); setManualType('pothole'); setManualSeverity('medium'); setManualItems([])
    setDrawMode(false); setDraftBox(null); setDraftType('pothole'); setDraftSeverity('medium'); setRegionError(null)
    setSubmitError(null); setSubmittedReports([])
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
      // Marking the problem on the photo is the primary fallback now; if the
      // model found nothing, switch drawing on straight away.
      setShowManualEntry(false)
      setDrawMode(withKeys.length === 0)
    } catch (err) {
      setAnalyzeError(err)
    } finally {
      setAnalyzing(false)
      setStage('review')
    }
  }

  function handleRegionDrawn(box) {
    setDraftBox(box)
    setDrawMode(false)
    setRegionError(null)
  }

  function cancelRegion() {
    setDraftBox(null)
    setDrawMode(false)
    setRegionError(null)
  }

  async function saveRegion() {
    if (!draftBox || !result) return
    setSavingRegion(true)
    setRegionError(null)
    try {
      const det = await api.createUserRegion({
        image_id: result.image_id,
        problem_type: draftType,
        severity: draftSeverity,
        ...draftBox,
      })
      const withKey = { ...det, _key: `user-${det.id}` }
      setResult((prev) => ({ ...prev, detections: [...prev.detections, withKey] }))
      // The user drew it and chose the type, so it is confirmed straight away.
      setReviewStates((prev) => ({ ...prev, [withKey._key]: { status: 'confirmed', severity: draftSeverity } }))
      setDraftBox(null)
    } catch (err) {
      setRegionError(err instanceof ApiError ? err.message : 'Could not save the marked area. Please try again.')
    } finally {
      setSavingRegion(false)
    }
  }

  function addManualItem() {
    setManualItems((prev) => [...prev, { key: `manual-${Date.now()}`, problemType: manualType, severity: manualSeverity }])
  }

  function removeManualItem(key) {
    setManualItems((prev) => prev.filter((m) => m.key !== key))
  }

  // Items the user has actually decided to report - only these get
  // submitted. Nothing is sent to the backend until "Submit report(s)".
  const confirmedDetections = result
    ? result.detections.filter((d) => reviewStates[d._key]?.status === 'confirmed')
    : []
  const reportItems = [
    ...confirmedDetections.map((d) => ({
      key: d._key, source: 'detection', detection: d,
      problemType: d.problem_type, severity: reviewStates[d._key].severity,
      confidence: d.source === 'user' ? null : d.confidence,
    })),
    ...manualItems.map((m) => ({ key: m.key, source: 'manual', problemType: m.problemType, severity: m.severity, confidence: null })),
  ]

  const canContinue = location.latitude && location.longitude && reportItems.length > 0

  async function handleSubmit() {
    setSubmitting(true)
    setSubmitError(null)

    const locationPayload = {
      latitude: parseFloat(location.latitude),
      longitude: parseFloat(location.longitude),
      city_id: selectedCityId,
      ward_id: location.ward_id ? Number(location.ward_id) : null,
      road_name: location.road_name || null,
      road_importance: location.road_importance,
      near_important_infrastructure: location.near_important_infrastructure,
      infrastructure_note: location.infrastructure_note || null,
    }

    try {
      const problemIds = []

      for (const item of reportItems) {
        if (item.source === 'detection') {
          const res = await api.verifyDetection(item.detection.id, {
            action: 'confirm', final_severity: item.severity, ...locationPayload,
          })
          if (res.problem_id) problemIds.push(res.problem_id)
        } else {
          const res = await api.createManualProblem({
            problem_type: item.problemType, severity: item.severity,
            image_id: result?.image_id ?? null, ...locationPayload,
          })
          problemIds.push(res.problem_id)
        }
      }

      // Also close out any detections the user explicitly rejected, so
      // they don't linger as pending_review forever.
      const rejected = result ? result.detections.filter((d) => reviewStates[d._key]?.status === 'rejected') : []
      for (const d of rejected) {
        await api.verifyDetection(d.id, { action: 'reject', latitude: 0, longitude: 0, city_id: selectedCityId })
      }

      const details = await Promise.all(problemIds.map((id) => api.getProblem(id)))
      setSubmittedReports(details.map((d) => ({ problemId: d.id, problemType: d.problem_type, summary: d.description })))
      setStage('success')
    } catch (err) {
      setSubmitError(err instanceof ApiError ? err.message : 'Failed to submit report. Please try again.')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <AppLayout
      title="Report Problem"
      description="Found an infrastructure problem? Upload a photo and NeceCity will analyze and record it."
    >
      <div className="max-w-5xl space-y-6">

        {stage === 'upload' && !analyzing && <UploadDropzone onFileSelected={handleFileSelected} />}
        {analyzing && <LoadingState label="Analyzing photo" />}

        {stage !== 'upload' && (
          <div className="flex justify-end">
            <button className="btn-secondary" onClick={resetAll}>
              <RefreshCw className="h-4 w-4" /> Start a new report
            </button>
          </div>
        )}

        {analyzeError && (
          <div className="panel p-5 flex items-start gap-2.5 border-danger/20 bg-danger/[0.04] text-danger text-sm">
            <AlertTriangle className="h-4 w-4 shrink-0 mt-0.5" />
            {analyzeError.message}
          </div>
        )}

        {stage === 'review' && result && (
          <>
            {!result.model_available && (
              <div className="panel p-5 flex items-start gap-2.5 border-warning/20 bg-warning-bg text-warning text-sm">
                <AlertTriangle className="h-4 w-4 shrink-0 mt-0.5" />
                <div>
                  <p className="font-medium">ML model not configured yet.</p>
                  <p className="text-ink-500 mt-1">{result.message} Your photo was saved — add the problem manually below; nothing is lost.</p>
                </div>
              </div>
            )}

            {result.model_available && result.training_data_warning && (
              <div className="panel p-5 flex items-start gap-2.5 border-warning/20 bg-warning-bg text-warning text-sm">
                <AlertTriangle className="h-4 w-4 shrink-0 mt-0.5" />
                <div>
                  <p className="font-medium">Model trained on placeholder data — real-world accuracy will be poor.</p>
                  <p className="text-ink-500 mt-1">{result.training_data_warning}</p>
                </div>
              </div>
            )}

            {result.model_available && result.detections.length === 0 && (
              <div className="panel p-5 flex items-start gap-2.5 text-sm text-ink-700">
                <Info className="h-4 w-4 shrink-0 mt-0.5 text-info" />
                <div>
                  <p>The model did not recognise a problem in this photo — it may look different from the photos it was trained on.</p>
                  <p className="text-ink-500 mt-1">Mark the problem yourself: drag a box around it on the photo (or just click it), then choose what it is.</p>
                </div>
              </div>
            )}

            {result.detections.some((d) => d.low_confidence) && (
              <div className="panel p-5 flex items-start gap-2.5 text-sm text-ink-700">
                <Info className="h-4 w-4 shrink-0 mt-0.5 text-info" />
                <p>Some detections below are low-confidence (dashed boxes). Confirm only the ones that match what you can see, and reject the rest.</p>
              </div>
            )}

            <div className="grid lg:grid-cols-[1fr_360px] gap-6 items-start">
              <div className="space-y-4">
                {previewUrl && (
                  <BoundingBoxOverlay
                    imageUrl={previewUrl}
                    detections={result.detections}
                    activeDetectionIndex={activeIndex}
                    drawMode={drawMode}
                    draftBox={draftBox}
                    onDraw={handleRegionDrawn}
                  />
                )}

                {draftBox ? (
                  <RegionDraftPanel
                    problemType={draftType} setProblemType={setDraftType}
                    severity={draftSeverity} setSeverity={setDraftSeverity}
                    saving={savingRegion} error={regionError}
                    onAdd={saveRegion}
                    onRedraw={() => { setDraftBox(null); setDrawMode(true) }}
                    onCancel={cancelRegion}
                  />
                ) : drawMode ? (
                  <div className="flex items-center justify-between gap-3 rounded-lg border border-orange-500/40 bg-orange-50/40 px-4 py-3 text-sm text-ink-700">
                    <span>Drag a box around the problem on the photo (or click it).</span>
                    <button className="btn-secondary" onClick={() => setDrawMode(false)}>Cancel</button>
                  </div>
                ) : (
                  <button className="btn-secondary" onClick={() => setDrawMode(true)}>
                    <PenLine className="h-4 w-4" /> Mark a problem on the photo
                  </button>
                )}

                {result.detections.length > 0 && (
                  <div className="space-y-3">
                    <h2 className="text-xs font-semibold text-ink-500 uppercase tracking-wide">Detected problems — review each one</h2>
                    {result.detections.map((det, i) => (
                      <DetectionReviewCard
                        key={det._key}
                        detection={det}
                        reviewState={reviewStates[det._key]}
                        isActive={activeIndex === i}
                        onHover={() => setActiveIndex(i)}
                        onSeverityChange={(sev) => setReviewStates((prev) => ({ ...prev, [det._key]: { ...prev[det._key], severity: sev } }))}
                        onConfirm={() => setReviewStates((prev) => ({ ...prev, [det._key]: { ...prev[det._key], status: 'confirmed' } }))}
                        onReject={() => setReviewStates((prev) => ({ ...prev, [det._key]: { ...prev[det._key], status: 'rejected' } }))}
                      />
                    ))}
                  </div>
                )}

                {manualItems.length > 0 && (
                  <div className="space-y-2">
                    <h2 className="text-xs font-semibold text-ink-500 uppercase tracking-wide">Manually added</h2>
                    {manualItems.map((m) => (
                      <div key={m.key} className="panel p-3 flex items-center justify-between text-sm">
                        <span className="text-ink-900 font-medium capitalize">{m.problemType.replace('_', ' ')} · {m.severity}</span>
                        <button className="text-xs text-danger hover:underline" onClick={() => removeManualItem(m.key)}>Remove</button>
                      </div>
                    ))}
                  </div>
                )}

                {!showManualEntry ? (
                  <button className="btn-secondary" onClick={() => setShowManualEntry(true)}>
                    <PlusCircle className="h-4 w-4" /> Add without marking the area
                  </button>
                ) : (
                  <div className="space-y-3">
                    <ManualEntryForm problemType={manualType} setProblemType={setManualType} severity={manualSeverity} setSeverity={setManualSeverity} />
                    <button className="btn-secondary w-full" onClick={addManualItem}>
                      <PlusCircle className="h-4 w-4" /> Add to this report
                    </button>
                  </div>
                )}
              </div>

              <div className="space-y-4">
                <LocationPicker
                  location={location}
                  setLocation={setLocation}
                  wards={wards}
                  cityCenter={selectedCity ? [selectedCity.center_latitude, selectedCity.center_longitude] : [22.5726, 88.3639]}
                  cityZoom={selectedCity?.default_zoom || 12}
                />
                <button className="btn-accent w-full" disabled={!canContinue} onClick={() => setStage('confirm')}>
                  Continue to review
                </button>
                {!canContinue && (
                  <p className="text-xs text-ink-500 text-center">
                    {reportItems.length === 0 ? 'Confirm or add at least one problem to continue.' : 'Set a location to continue.'}
                  </p>
                )}
              </div>
            </div>
          </>
        )}

        {stage === 'confirm' && (
          <>
            {submitError && (
              <div className="panel p-4 flex items-start gap-2.5 border-danger/20 bg-danger/[0.04] text-danger text-sm">
                <AlertTriangle className="h-4 w-4 shrink-0 mt-0.5" /> {submitError}
              </div>
            )}
            <ReportReviewSummary
              items={reportItems}
              cityName={selectedCity?.name}
              location={location}
              imageUrl={previewUrl}
              submitting={submitting}
              onSubmit={handleSubmit}
              onBack={() => setStage('review')}
            />
          </>
        )}

        {stage === 'success' && (
          <div className="space-y-4">
            <div className="panel p-6 text-center space-y-2">
              <CheckCircle2 className="h-8 w-8 text-success mx-auto" />
              <h2 className="text-base font-semibold text-ink-900">
                Report{submittedReports.length > 1 ? 's' : ''} successfully added to City Monitor
              </h2>
            </div>

            {submittedReports.map((r) => (
              <div key={r.problemId} className="panel p-5">
                <p className="text-sm text-ink-700 leading-relaxed">{r.summary}</p>
              </div>
            ))}

            <div className="flex gap-2">
              <Link to="/monitor" className="btn-secondary flex-1 justify-center">
                <MapPinned className="h-4 w-4" /> View on City Monitor
              </Link>
              <button className="btn-accent flex-1" onClick={resetAll}>
                <PlusCircle className="h-4 w-4" /> Report another problem
              </button>
            </div>
          </div>
        )}
      </div>
    </AppLayout>
  )
}