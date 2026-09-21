import { AlertTriangle, Inbox, Loader2, ServerCrash } from 'lucide-react'

export function LoadingState({ label = 'Loading' }) {
  return (
    <div className="flex items-center justify-center gap-2.5 py-16 text-ink-500">
      <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />
      <span className="text-sm">{label}...</span>
    </div>
  )
}

export function EmptyState({ title, description, icon: Icon = Inbox }) {
  return (
    <div className="flex flex-col items-center justify-center gap-2 py-16 text-center px-6">
      <Icon className="h-8 w-8 text-ink-300" aria-hidden="true" />
      <p className="text-sm font-medium text-ink-700">{title}</p>
      {description && <p className="text-sm text-ink-500 max-w-sm">{description}</p>}
    </div>
  )
}

export function ErrorState({ error, onRetry }) {
  const isConnectionError = error?.message?.includes('fetch') || error?.status === undefined
  return (
    <div className="flex flex-col items-center justify-center gap-3 py-16 text-center px-6">
      {isConnectionError ? (
        <ServerCrash className="h-8 w-8 text-danger" aria-hidden="true" />
      ) : (
        <AlertTriangle className="h-8 w-8 text-danger" aria-hidden="true" />
      )}
      <p className="text-sm font-medium text-ink-900">
        {isConnectionError ? "Can't reach the NeceCity backend." : 'Something went wrong loading this data.'}
      </p>
      <p className="text-sm text-ink-500 max-w-sm">
        {isConnectionError
          ? 'Check that the backend API is running and reachable at the configured URL.'
          : error?.message || 'Please try again.'}
      </p>
      {onRetry && (
        <button className="btn-secondary mt-1" onClick={onRetry}>
          Retry
        </button>
      )}
    </div>
  )
}
