import { useEffect, useRef, useState } from 'react'
import { Bot, Loader2, Send, Sparkles, User } from 'lucide-react'
import { api, ApiError } from '../services/api'
import MarkdownMessage from './MarkdownMessage'

const SUGGESTIONS = [
  'What are the critical issues right now?',
  "What's the biggest problem in my city?",
  'Which problems should be fixed first?',
  'Who can help with garbage collection?',
]

function Bubble({ role, content, mode }) {
  const isUser = role === 'user'
  return (
    <div className={`flex gap-3 ${isUser ? 'flex-row-reverse' : ''}`}>
      <span
        className={`flex h-8 w-8 items-center justify-center rounded-full shrink-0 ${
          isUser ? 'bg-navy-900 text-white' : 'bg-orange-50 text-orange-500'
        }`}
      >
        {isUser ? <User className="h-4 w-4" /> : <Bot className="h-4 w-4" />}
      </span>
      <div className={`${isUser ? 'max-w-[80%] items-end' : 'max-w-[92%] min-w-0 items-start'} flex flex-col gap-1`}>
        <div
          className={`rounded-lg px-4 py-2.5 text-sm leading-relaxed ${isUser ? 'whitespace-pre-wrap' : ''} ${
            isUser ? 'bg-navy-900 text-white' : 'bg-slate-50 text-ink-900 border border-slate-100'
          }`}
        >
          {isUser ? content : <MarkdownMessage content={content} />}
        </div>
        {!isUser && mode && (
          <span className="text-[10px] text-ink-300 px-1">
            {mode === 'llm' ? 'AI-generated' : 'Smart Assistant (data-grounded)'}
          </span>
        )}
      </div>
    </div>
  )
}

export default function ChatPanel({ cityId, cityName }) {
  const [messages, setMessages] = useState([
    {
      role: 'assistant',
      content: `Hi! I'm the NeceCity assistant${cityName ? ` for ${cityName}` : ''}. Ask me about critical issues, a specific road or ward, how risk scores work, or which organizations can help.`,
      mode: 'rule_based',
    },
  ])
  const [input, setInput] = useState('')
  const [sending, setSending] = useState(false)
  const [error, setError] = useState(null)
  const scrollRef = useRef(null)

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: 'smooth' })
  }, [messages, sending])

  async function send(text) {
    const trimmed = text.trim()
    if (!trimmed || sending) return

    const history = messages.map((m) => ({ role: m.role, content: m.content }))
    setMessages((prev) => [...prev, { role: 'user', content: trimmed }])
    setInput('')
    setSending(true)
    setError(null)

    try {
      const res = await api.sendChatMessage({ city_id: cityId, message: trimmed, history })
      setMessages((prev) => [...prev, { role: 'assistant', content: res.reply, mode: res.mode }])
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Failed to reach the assistant.')
    } finally {
      setSending(false)
    }
  }

  return (
    <div className="panel flex flex-col h-[600px]">
      <div className="flex items-center gap-2 px-5 py-4 border-b border-slate-100">
        <Sparkles className="h-4 w-4 text-orange-500" />
        <h2 className="text-sm font-semibold text-ink-900">Chat with the NeceCity Assistant</h2>
      </div>

      <div ref={scrollRef} className="flex-1 overflow-y-auto px-5 py-5 space-y-5">
        {messages.map((m, i) => (
          <Bubble key={i} role={m.role} content={m.content} mode={m.mode} />
        ))}
        {sending && (
          <div className="flex gap-3">
            <span className="flex h-8 w-8 items-center justify-center rounded-full bg-orange-50 text-orange-500 shrink-0">
              <Bot className="h-4 w-4" />
            </span>
            <div className="flex items-center gap-2 rounded-lg px-4 py-2.5 bg-slate-50 border border-slate-100 text-sm text-ink-500">
              <Loader2 className="h-3.5 w-3.5 animate-spin" /> Thinking...
            </div>
          </div>
        )}
        {error && <p className="text-sm text-danger px-1">{error}</p>}
      </div>

      {messages.length <= 1 && (
        <div className="flex flex-wrap gap-1.5 px-5 pb-3">
          {SUGGESTIONS.map((s) => (
            <button
              key={s}
              onClick={() => send(s)}
              className="pill-toggle pill-toggle-inactive text-xs"
              type="button"
            >
              {s}
            </button>
          ))}
        </div>
      )}

      <form
        className="flex items-center gap-2 border-t border-slate-100 px-4 py-3"
        onSubmit={(e) => { e.preventDefault(); send(input) }}
      >
        <input
          type="text"
          className="input"
          placeholder="Ask about your city's problems, risk scores, or who to contact..."
          value={input}
          onChange={(e) => setInput(e.target.value)}
          disabled={sending}
        />
        <button type="submit" className="btn-accent shrink-0" disabled={sending || !input.trim()} aria-label="Send message">
          <Send className="h-4 w-4" />
        </button>
      </form>
    </div>
  )
}