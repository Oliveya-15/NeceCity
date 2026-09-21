import { ExternalLink, Lightbulb, Megaphone, ShieldCheck, Sparkles, Trash2 } from 'lucide-react'
import AppLayout from '../layouts/AppLayout'
import ChatPanel from '../components/ChatPanel'
import { LoadingState, ErrorState } from '../components/StateViews'
import { useCity } from '../hooks/CityContext'
import { useApi } from '../hooks/useApi'
import { api } from '../services/api'

const CATEGORY_META = {
  governance: { label: 'Governance', icon: Megaphone, color: '#2563A8' },
  road_safety: { label: 'Road Safety', icon: ShieldCheck, color: '#E15400' },
  sanitation: { label: 'Sanitation', icon: Trash2, color: '#1E8E5A' },
}

function CompactOrgCard({ org }) {
  const meta = CATEGORY_META[org.category] || CATEGORY_META.governance
  const Icon = meta.icon
  return (
    <a
      href={org.website}
      target="_blank"
      rel="noopener noreferrer"
      className="flex items-start gap-3 rounded-md p-3 hover:bg-slate-50 transition-colors group"
    >
      <span
        className="flex h-8 w-8 items-center justify-center rounded-full shrink-0"
        style={{ backgroundColor: `${meta.color}15`, color: meta.color }}
      >
        <Icon className="h-3.5 w-3.5" aria-hidden="true" />
      </span>
      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-1.5">
          <h3 className="text-sm font-medium text-ink-900 leading-snug truncate">{org.name}</h3>
          <ExternalLink className="h-3 w-3 text-ink-300 group-hover:text-orange-500 transition-colors shrink-0" aria-hidden="true" />
        </div>
        <p className="text-xs text-ink-500 mt-0.5 line-clamp-2 leading-relaxed">{org.description}</p>
      </div>
    </a>
  )
}

export default function AdviceCenter() {
  const { selectedCityId, selectedCity } = useCity()

  const { data, loading, error, reload } = useApi(
    () => api.getRecommendations(selectedCityId), [selectedCityId], { skip: !selectedCityId }
  )

  return (
    <AppLayout
      title="AI Recommendations"
      description={selectedCity ? `Chat and civic resources for ${selectedCity.name}` : undefined}
    >
      {loading && <LoadingState label="Loading" />}
      {error && <ErrorState error={error} onRetry={reload} />}

      {data && selectedCity && (
        <div className="grid lg:grid-cols-[1fr_340px] gap-6 items-start">
          <ChatPanel cityId={selectedCityId} cityName={selectedCity.name} />

          <div className="space-y-4">
            {data.city_insights.length > 0 && (
              <section className="panel p-5 bg-gradient-to-br from-navy-900 to-navy-700 border-0">
                <div className="flex items-center gap-2 mb-3">
                  <Sparkles className="h-3.5 w-3.5 text-orange-500" />
                  <h2 className="text-xs font-semibold text-white uppercase tracking-wide">
                    {selectedCity.name} — Live insights
                  </h2>
                </div>
                <ul className="space-y-2">
                  {data.city_insights.map((text, i) => (
                    <li key={i} className="text-xs text-white/90 leading-relaxed flex gap-2">
                      <span className="text-orange-400 shrink-0">&bull;</span>
                      {text}
                    </li>
                  ))}
                </ul>
              </section>
            )}

            <section className="panel p-2">
              <h2 className="text-xs font-semibold text-ink-500 uppercase tracking-wide px-3 pt-2.5 pb-1">
                Recommended organizations
              </h2>
              <div className="divide-y divide-slate-100">
                {data.recommended_organizations.map((org) => (
                  <CompactOrgCard key={org.name} org={org} />
                ))}
              </div>
            </section>

            <section className="panel p-5">
              <div className="flex items-center gap-2 mb-3">
                <Lightbulb className="h-3.5 w-3.5 text-orange-500" />
                <h2 className="text-xs font-semibold text-ink-500 uppercase tracking-wide">Civic tips</h2>
              </div>
              <div className="space-y-3.5">
                {data.tips.slice(0, 4).map((tip) => (
                  <div key={tip.title}>
                    <h3 className="text-xs font-semibold text-ink-900">{tip.title}</h3>
                    <p className="text-xs text-ink-500 mt-0.5 leading-relaxed">{tip.body}</p>
                  </div>
                ))}
              </div>
            </section>

            <p className="text-[11px] text-ink-300 px-1 leading-relaxed">
              Organizations are a starter directory of independently verifiable national platforms — verify current
              contact details on each site, and check your municipal corporation for hyperlocal support.
            </p>
          </div>
        </div>
      )}
    </AppLayout>
  )
}
