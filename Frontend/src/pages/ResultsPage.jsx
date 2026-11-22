import { useState, useEffect, useCallback, useRef } from "react"
import { Link, useSearchParams } from "react-router-dom"
import { AlertCircle, Loader2, Search } from "lucide-react"
import { Navbar } from "../components/navbar"
import { Footer } from "../components/footer"
import { Disclaimer } from "../components/disclaimer"
import { useAuth } from "../context/auth-context"
import { askQuestion, searchLegalCases, describeError, isAbstention, ApiError, ABSTAIN_TEXT } from "../utils/api"
import { clip, displayTitle } from "../lib/utils"
import { saveSearchHistory } from "../utils/firebase-helpers"

const EXAMPLES = [
  "Murder cases",
  "Cases under Section 302 IPC",
  "What are the conditions for anticipatory bail?",
  "Difference between culpable homicide and murder",
]
const CASE_RESULT_COUNT = 6
const SOURCE_EXCERPT_CHARS = 280

const WORD_JOINER = "\u2060" // keeps a chip on the same line as the word before it

// text with [n] markers -> text + chips that link to the cited case
function renderCitations(text, sources, keyBase) {
  const tight = text.replace(/\s+(\[\d+\])/g, "$1").replace(/(\[\d+\])\s+([.,;:])/g, "$1$2")
  return tight.split(/(\[\d+\])/g).map((part, i) => {
    const key = `${keyBase}-${i}`
    const m = part.match(/^\[(\d+)\]$/)
    if (!m) return part
    const n = Number(m[1])
    const src = sources?.find((s) => s.n === n) ?? sources?.[n - 1]
    if (!src) return part
    return (
      <sup key={key}>
        {WORD_JOINER}
        <Link
          to={`/case/${src.case_id}`}
          aria-label={`Source ${n}: case ${src.case_id}`}
          className="ml-px mr-px inline-flex h-4 min-w-4 items-center justify-center rounded bg-indigo-500/25 px-[3px] align-baseline text-[11px] font-semibold text-indigo-200 hover:bg-indigo-500/45"
        >
          {n}
        </Link>
      </sup>
    )
  })
}

// inline markdown: **bold** (citations work inside it)
function renderInline(text, sources, keyBase) {
  return text.split(/(\*\*.+?\*\*)/g).map((part, i) => {
    const key = `${keyBase}-${i}`
    const bold = part.match(/^\*\*(.+)\*\*$/)
    if (bold) return <strong key={key} className="font-semibold text-foreground">{renderCitations(bold[1], sources, key)}</strong>
    return <span key={key}>{renderCitations(part, sources, key)}</span>
  })
}

const BULLET_RE = /^\s*[*-]\s+(.*)$/
const NUMBER_RE = /^\s*\d+[.)]\s+(.*)$/

// shortcut: paragraphs, bold, bullet and numbered lists only; no nesting, italics or headings
function renderAnswer(text, sources) {
  const blocks = []
  let para = []
  let list = null
  const flushPara = () => {
    if (para.length) blocks.push({ type: "p", text: para.join(" ") })
    para = []
  }
  const flushList = () => {
    if (list) blocks.push(list)
    list = null
  }
  for (const line of text.split(/\r?\n/)) {
    const bullet = line.match(BULLET_RE)
    const number = bullet ? null : line.match(NUMBER_RE)
    const item = bullet || number
    if (item) {
      flushPara()
      const type = bullet ? "ul" : "ol"
      if (list?.type !== type) { flushList(); list = { type, items: [] } }
      list.items.push(item[1])
    } else if (!line.trim()) {
      flushPara(); flushList()
    } else if (list && /^\s+/.test(line)) {
      list.items[list.items.length - 1] += " " + line.trim() // wrapped list item
    } else {
      flushList()
      para.push(line.trim())
    }
  }
  flushPara(); flushList()

  return blocks.map((b, i) => {
    if (b.type === "p") return <p key={i}>{renderInline(b.text, sources, `p${i}`)}</p>
    const Tag = b.type
    const marker = b.type === "ul" ? "list-disc" : "list-decimal"
    return (
      <Tag key={i} className={`${marker} space-y-1.5 pl-5 marker:text-indigo-300/70`}>
        {b.items.map((t, j) => <li key={j}>{renderInline(t, sources, `l${i}-${j}`)}</li>)}
      </Tag>
    )
  })
}

// "Case 109" unless a usable title exists
function sourceLabel(title, id) {
  const t = (title || "").trim()
  return !t || t === "Not available" || t.startsWith("...") || t.startsWith("…") ? `Case ${id}` : displayTitle(t, id)
}

function ErrorNote({ error, onRetry, subject }) {
  const kind = error instanceof ApiError ? error.kind : "server"
  const tone =
    kind === "rate_limit"
      ? "border-amber-500/30 bg-amber-500/10 text-amber-100"
      : "border-red-500/30 bg-red-500/10 text-red-100"
  return (
    <div role="alert" className={`flex flex-col gap-3 rounded-xl border p-4 text-sm sm:flex-row sm:items-center sm:justify-between ${tone}`}>
      <p className="flex items-start gap-2">
        <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" aria-hidden="true" />
        <span>
          <span className="font-semibold">{subject}: </span>
          {describeError(error)}
        </span>
      </p>
      {onRetry && (
        <button type="button" onClick={onRetry} className="self-start rounded-lg border border-white/20 px-3 py-1.5 font-medium hover:bg-white/10 sm:self-auto">
          Try again
        </button>
      )}
    </div>
  )
}

function AnswerSkeleton() {
  return (
    <div role="status" aria-live="polite">
      <p className="mb-3 flex items-center gap-2 text-sm text-muted-foreground">
        <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />
        Reading the judgments and writing an answer. New searches can take about 5 seconds.
      </p>
      <div className="animate-pulse space-y-2" aria-hidden="true">
        <div className="h-3 w-3/4 rounded bg-white/10" />
        <div className="h-3 w-full rounded bg-white/10" />
        <div className="h-3 w-5/6 rounded bg-white/10" />
        <div className="h-3 w-2/3 rounded bg-white/10" />
      </div>
    </div>
  )
}

export default function ResultsPage() {
  const { user } = useAuth()
  const [params, setParams] = useSearchParams()
  const [query, setQuery] = useState(params.get("q") || "")
  const [cases, setCases] = useState(null)
  const [caseErr, setCaseErr] = useState(null)
  const [answer, setAnswer] = useState(null)
  const [answerErr, setAnswerErr] = useState(null)
  const [loadingCases, setLoadingCases] = useState(false)
  const [loadingAnswer, setLoadingAnswer] = useState(false)
  const runId = useRef(0)
  const busy = loadingCases || loadingAnswer

  const run = useCallback((text) => {
    const t = text.trim()
    if (!t) return
    const id = ++runId.current
    const current = () => id === runId.current // ignore results of superseded searches
    setCases(null); setCaseErr(null); setAnswer(null); setAnswerErr(null)
    setLoadingCases(true); setLoadingAnswer(true)

    searchLegalCases(t, CASE_RESULT_COUNT)
      .then((r) => {
        if (!current()) return
        setCases(r)
        if (user) saveSearchHistory(user.uid, t, r.length).catch(() => {})
      })
      .catch((e) => current() && setCaseErr(e))
      .finally(() => current() && setLoadingCases(false))

    askQuestion(t)
      .then((r) => current() && setAnswer(r))
      .catch((e) => current() && setAnswerErr(e))
      .finally(() => current() && setLoadingAnswer(false))
  }, [user])

  useEffect(() => {
    const q = params.get("q")
    if (q) { setQuery(q); run(q) }
    // run once for the initial URL; later searches go through start()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const start = (text) => {
    const t = text.trim()
    if (!t || busy) return
    setQuery(t)
    setParams({ q: t })
    run(t)
  }
  const submit = (e) => { e.preventDefault(); start(query) }
  const retry = () => start(params.get("q") || query)

  const abstained = isAbstention(answer)
  const citedSources = answer && !abstained
    ? (answer.sources || []).filter((s) => !answer.cited?.length || answer.cited.includes(s.n))
    : []
  const titles = Object.fromEntries((cases || []).map((c) => [String(c.id), c.title]))
  const searched = Boolean(params.get("q"))

  return (
    <div className="flex min-h-screen flex-col bg-background text-foreground">
      <Navbar />
      <main id="main" className="mx-auto w-full max-w-3xl flex-1 px-4 py-8">
        <form
          onSubmit={submit}
          role="search"
          className="flex items-center gap-2 rounded-xl border border-white/15 bg-white/5 p-2 transition focus-within:border-indigo-400 focus-within:ring-2 focus-within:ring-indigo-400/40"
        >
          <label htmlFor="results-q" className="sr-only">Search cases or ask a question</label>
          <input
            id="results-q"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search cases or ask a question…"
            autoComplete="off"
            className="min-w-0 flex-1 bg-transparent px-3 py-2 text-base outline-none placeholder:text-muted-foreground"
          />
          <button
            type="submit"
            disabled={busy || !query.trim()}
            className="inline-flex shrink-0 items-center gap-2 rounded-lg bg-indigo-600 px-4 py-2 font-semibold text-white transition hover:bg-indigo-500 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-white disabled:cursor-not-allowed disabled:opacity-60 sm:px-6"
          >
            {busy ? <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" /> : <Search className="h-4 w-4" aria-hidden="true" />}
            {busy ? "Searching" : "Search"}
          </button>
        </form>
        <Disclaimer className="mt-3" />

        {!searched && !busy && (
          <div className="mt-10 flex flex-wrap justify-center gap-2">
            {EXAMPLES.map((x) => (
              <button key={x} type="button" onClick={() => start(x)}
                className="rounded-full border border-white/15 bg-white/[0.03] px-3 py-1.5 text-sm text-muted-foreground transition hover:border-indigo-400/60 hover:text-foreground">
                {x}
              </button>
            ))}
          </div>
        )}

        {(loadingAnswer || answer || answerErr) && (
          <section aria-labelledby="answer-h" className="mt-8 rounded-xl border border-indigo-400/25 bg-indigo-500/[0.05] p-5">
            <h2 id="answer-h" className="mb-3 flex items-center gap-2 text-xs font-semibold uppercase tracking-wide text-indigo-200">
              AI answer
            </h2>
            {loadingAnswer && <AnswerSkeleton />}
            {answerErr && !loadingAnswer && (
              <ErrorNote error={answerErr} subject="Answer unavailable" onRetry={retry} />
            )}
            {answer && abstained && (
              <div>
                <p className="text-base font-medium">{ABSTAIN_TEXT}</p>
                <p className="mt-2 text-sm text-muted-foreground">
                  The indexed judgments do not contain enough to answer this. Try rephrasing, or open the related cases below.
                </p>
              </div>
            )}
            {answer && !abstained && (
              <>
                <div className="space-y-3 break-words text-[15px] leading-relaxed text-foreground/90">
                  {renderAnswer(answer.answer, answer.sources)}
                </div>
                {citedSources.length > 0 && (
                  <div className="mt-4 border-t border-white/10 pt-3">
                    <h3 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Sources</h3>
                    <ul className="mt-2 space-y-2">
                      {citedSources.map((s) => (
                        <li key={s.n} className="text-sm">
                          <Link to={`/case/${s.case_id}`} className="font-medium text-indigo-300 hover:underline">
                            [{s.n}] {sourceLabel(s.title ?? titles[s.case_id], s.case_id)}
                          </Link>
                          <p className="mt-0.5 text-muted-foreground">{clip(s.text, SOURCE_EXCERPT_CHARS)}</p>
                        </li>
                      ))}
                    </ul>
                  </div>
                )}
              </>
            )}
          </section>
        )}

        {(loadingCases || cases || caseErr) && (
          <section aria-labelledby="cases-h" className="mt-8">
            <h2 id="cases-h" className="mb-3 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
              Cases{cases ? ` (${cases.length})` : ""}
            </h2>
            {loadingCases && (
              <div role="status" aria-label="Loading cases" className="space-y-3">
                {[0, 1, 2].map((i) => <div key={i} className="h-24 animate-pulse rounded-xl bg-white/5" />)}
              </div>
            )}
            {caseErr && !loadingCases && (
              <ErrorNote error={caseErr} subject="Case search failed" onRetry={retry} />
            )}
            {cases?.length === 0 && <p className="text-sm text-muted-foreground">No matching cases found.</p>}
            <ul className="space-y-3">
              {cases?.map((c) => (
                <li key={c.id}>
                  <Link
                    to={`/case/${c.id}`}
                    className="block rounded-xl border border-white/10 bg-white/[0.02] p-4 transition hover:border-indigo-400/50"
                  >
                    <h3 className="font-semibold text-indigo-300">{displayTitle(c.title, c.id)}</h3>
                    <p className="mt-1 text-sm text-muted-foreground">{clip(c.summary, 220)}</p>
                    <div className="mt-2 flex flex-wrap gap-2 text-xs text-muted-foreground">
                      {c.judges && c.judges !== "Not available" && (
                        <span className="rounded bg-white/10 px-2 py-0.5">Judges: {c.judges}</span>
                      )}
                      {c.date && c.date !== "Not available" && (
                        <span className="rounded bg-white/10 px-2 py-0.5">{c.date}</span>
                      )}
                      <span className="rounded bg-white/10 px-2 py-0.5">Case {c.id}</span>
                    </div>
                  </Link>
                </li>
              ))}
            </ul>
          </section>
        )}
      </main>
      <Footer />
    </div>
  )
}
