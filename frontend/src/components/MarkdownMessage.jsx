import { Fragment } from 'react'

/**
 * Small, dependency-free Markdown renderer for assistant chat replies.
 * Supports: ### headings, "-"/"*"/"•" bullet lists, "1." numbered lists,
 * pipe tables (rendered as a real, scrollable table), **bold**, *italic*,
 * `code`, and paragraphs. It builds React elements only - never
 * dangerouslySetInnerHTML - so model output can't inject HTML.
 */

// Models sometimes put <br> inside table cells or bullets; treat it as a line break.
function normalizeBreaks(text) {
  return text
    .replace(/<br\s*\/?>/gi, '\n')
    .replace(/\u2011|\u2010/g, '-')
    .replace(/[\u00a0\u202f]/g, ' ')
}

function renderInline(text, keyPrefix = 'i') {
  const tokens = text.split(/(\*\*[^*]+\*\*|`[^`]+`|(?<![*\w])\*[^*\s][^*]*\*(?![*\w]))/g)
  return tokens.map((tok, i) => {
    const key = `${keyPrefix}-${i}`
    if (tok.startsWith('**') && tok.endsWith('**') && tok.length > 4) {
      return <strong key={key} className="font-semibold text-ink-900">{tok.slice(2, -2)}</strong>
    }
    if (tok.startsWith('`') && tok.endsWith('`') && tok.length > 2) {
      return <code key={key} className="rounded bg-slate-100 px-1 py-0.5 text-[12px]">{tok.slice(1, -1)}</code>
    }
    if (tok.startsWith('*') && tok.endsWith('*') && tok.length > 2) {
      return <em key={key}>{tok.slice(1, -1)}</em>
    }
    return <Fragment key={key}>{tok}</Fragment>
  })
}

const isTableRow = (l) => /^\s*\|.*\|\s*$/.test(l)
const isTableSeparator = (l) => /^\s*\|?\s*:?-{2,}:?\s*(\|\s*:?-{2,}:?\s*)*\|?\s*$/.test(l)
const bulletMatch = (l) => l.match(/^\s*(?:[-*•–]\s+)(.*)$/)
const numberMatch = (l) => l.match(/^\s*(\d+)[.)]\s+(.*)$/)
const headingMatch = (l) => l.match(/^\s*(#{1,6})\s+(.*)$/)

function splitCells(line) {
  return line.trim().replace(/^\|/, '').replace(/\|$/, '').split('|').map((c) => c.trim())
}

function parseBlocks(text) {
  const lines = normalizeBreaks(text).split('\n')
  const blocks = []
  let i = 0
  while (i < lines.length) {
    const line = lines[i]
    if (!line.trim()) { i += 1; continue }

    const h = headingMatch(line)
    if (h) { blocks.push({ type: 'heading', text: h[2] }); i += 1; continue }

    if (isTableRow(line)) {
      const rows = []
      while (i < lines.length && isTableRow(lines[i])) { rows.push(lines[i]); i += 1 }
      const sepIdx = rows.findIndex(isTableSeparator)
      const header = sepIdx > 0 ? splitCells(rows[0]) : null
      const body = rows.filter((r, idx) => !isTableSeparator(r) && !(header && idx === 0)).map(splitCells)
      blocks.push({ type: 'table', header, body })
      continue
    }

    if (bulletMatch(line)) {
      const items = []
      while (i < lines.length && bulletMatch(lines[i])) { items.push(bulletMatch(lines[i])[1]); i += 1 }
      blocks.push({ type: 'ul', items })
      continue
    }

    if (numberMatch(line)) {
      const items = []
      while (i < lines.length && numberMatch(lines[i])) { items.push(numberMatch(lines[i])[2]); i += 1 }
      blocks.push({ type: 'ol', items })
      continue
    }

    const para = []
    while (
      i < lines.length && lines[i].trim() && !headingMatch(lines[i]) && !isTableRow(lines[i])
      && !bulletMatch(lines[i]) && !numberMatch(lines[i])
    ) { para.push(lines[i]); i += 1 }
    blocks.push({ type: 'p', text: para.join('\n') })
  }
  return blocks
}

export default function MarkdownMessage({ content }) {
  if (!content) return null
  const blocks = parseBlocks(content)
  return (
    <div className="space-y-2.5">
      {blocks.map((b, idx) => {
        const key = `b-${idx}`
        if (b.type === 'heading') {
          return <p key={key} className="font-semibold text-ink-900 pt-1">{renderInline(b.text, key)}</p>
        }
        if (b.type === 'ul') {
          return (
            <ul key={key} className="list-disc pl-5 space-y-1">
              {b.items.map((it, j) => <li key={j}>{renderInline(it, `${key}-${j}`)}</li>)}
            </ul>
          )
        }
        if (b.type === 'ol') {
          return (
            <ol key={key} className="list-decimal pl-5 space-y-1">
              {b.items.map((it, j) => <li key={j}>{renderInline(it, `${key}-${j}`)}</li>)}
            </ol>
          )
        }
        if (b.type === 'table') {
          return (
            <div key={key} className="overflow-x-auto rounded-md border border-slate-200 bg-white">
              <table className="min-w-full text-xs">
                {b.header && (
                  <thead className="bg-slate-100 text-ink-700">
                    <tr>{b.header.map((c, j) => <th key={j} className="px-2.5 py-1.5 text-left font-semibold">{renderInline(c, `${key}-h${j}`)}</th>)}</tr>
                  </thead>
                )}
                <tbody>
                  {b.body.map((row, r) => (
                    <tr key={r} className="border-t border-slate-100 align-top">
                      {row.map((c, j) => (
                        <td key={j} className="px-2.5 py-1.5 whitespace-pre-line">{renderInline(c, `${key}-${r}-${j}`)}</td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )
        }
        return <p key={key} className="whitespace-pre-line">{renderInline(b.text, key)}</p>
      })}
    </div>
  )
}
