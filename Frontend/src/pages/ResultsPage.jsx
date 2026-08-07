"use client"

import { useState, useEffect, useCallback } from "react"
import { Link, useSearchParams } from "react-router-dom"
import { Navbar } from "../components/navbar"
import { askQuestion, searchLegalCases } from "../utils/api"

const EXAMPLES = [
  "Murder cases",
  "Cases under Section 302 IPC",
  "What are the conditions for anticipatory bail?",
  "Difference between culpable homicide and murder",
]

// answer text -> [n] chips that link to the cited case
function renderAnswer(text, sources) {
  return text.split(/(\[\d+\])/g).map((part, i) => {
    const m = part.match(/^\[(\d+)\]$/)
    if (m) {
      const n = Number(m[1])
      const src = sources?.[n - 1]
      return (
        <sup key={i}>
          <Link
            to={src ? `/case/${src.case_id}` : "#"}
            className="mx-0.5 inline-flex h-4 min-w-4 items-center justify-center rounded bg-indigo-500/20 px-1 text-[10px] font-semibold text-indigo-300 hover:bg-indigo-500/40"
          >
            {n}
          </Link>
        </sup>
      )
    }
    return <span key={i}>{part}</span>
  })
}

export default function ResultsPage() {
  const [params, setParams] = useSearchParams()
  const [query, setQuery] = useState(params.get("q") || "")
  const [cases, setCases] = useState(null)      // instant list
  const [answer, setAnswer] = useState(null)    // AI overview
  const [loadingCases, setLoadingCases] = useState(false)
  const [loadingAnswer, setLoadingAnswer] = useState(false)
  const [err, setErr] = useState(null)

  const run = useCallback(async (text) => {
    const t = text.trim()
    if (!t) return
    setErr(null); setCases(null); setAnswer(null)
    setLoadingCases(true); setLoadingAnswer(true)
    // instant case list
    searchLegalCases(t, 6)
      .then(setCases).catch(() => setCases([]))
      .finally(() => setLoadingCases(false))
    // AI overview (slower)
    askQuestion(t)
      .then(setAnswer)
      .catch((e) => setErr(e.message || "AI overview unavailable"))
      .finally(() => setLoadingAnswer(false))
  }, [])

  useEffect(() => {
    const q = params.get("q")
    if (q) { setQuery(q); run(q) }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const submit = (e) => { e.preventDefault(); if (query.trim()) { setParams({ q: query.trim() }); run(query) } }

  return (
    <div className="min-h-screen bg-background text-foreground">
      <Navbar />
      <div className="mx-auto max-w-3xl px-4 py-8">
        <form
          onSubmit={submit}
          className="flex items-center gap-2 rounded-xl border border-white/10 bg-white/5 p-2 transition focus-within:border-indigo-500"
        >
          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search cases or ask a question…"
            autoFocus
            className="flex-1 bg-transparent px-3 py-2 text-base outline-none placeholder:text-muted-foreground"
          />
          <button className="rounded-lg bg-indigo-600 px-6 py-2 font-semibold text-white transition hover:bg-indigo-700">
            Search
          </button>
        </form>

        {/* empty state */}
        {!cases && !answer && !loadingCases && !loadingAnswer && (
          <div className="mt-10 flex flex-wrap justify-center gap-2">
            {EXAMPLES.map((x) => (
              <button key={x} onClick={() => { setQuery(x); setParams({ q: x }); run(x) }}
                className="rounded-full border border-white/10 bg-white/[0.03] px-3 py-1.5 text-sm text-muted-foreground transition hover:border-indigo-500/50 hover:text-foreground">
                {x}
              </button>
            ))}
          </div>
        )}

        {/* AI overview */}
        {(loadingAnswer || answer) && (
          <section className="mt-8 rounded-xl border border-indigo-500/20 bg-indigo-500/[0.04] p-5">
            <div className="mb-2 flex items-center gap-2 text-xs font-semibold uppercase tracking-wide text-indigo-300">
              ✦ AI overview
              {answer?.provider && <span className="text-muted-foreground normal-case">· {answer.provider}</span>}
            </div>
            {loadingAnswer ? (
              <div className="animate-pulse space-y-2">
                <div className="h-3 w-3/4 rounded bg-white/10" />
                <div className="h-3 w-full rounded bg-white/10" />
                <div className="h-3 w-5/6 rounded bg-white/10" />
              </div>
            ) : (
              <div className="whitespace-pre-wrap text-[15px] leading-relaxed text-foreground/90">
                {renderAnswer(answer.answer, answer.sources)}
              </div>
            )}
          </section>
        )}

        {/* case list */}
        <section className="mt-8">
          <h2 className="mb-3 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
            Cases{cases ? ` (${cases.length})` : ""}
          </h2>
          {loadingCases && (
            <div className="space-y-3">
              {[0, 1, 2].map((i) => <div key={i} className="h-24 animate-pulse rounded-xl bg-white/5" />)}
            </div>
          )}
          <div className="space-y-3">
            {cases?.map((c) => (
              <Link
                key={c.id}
                to={`/case/${c.id}`}
                className="block rounded-xl border border-white/10 bg-white/[0.02] p-4 transition hover:border-indigo-500/40"
              >
                <h3 className="font-semibold text-indigo-400">{c.title}</h3>
                <p className="mt-1 text-sm text-muted-foreground">{(c.summary || "").slice(0, 220)}…</p>
                <div className="mt-2 flex flex-wrap gap-2 text-xs text-muted-foreground">
                  {c.judges && c.judges !== "Not available" && (
                    <span className="rounded bg-white/5 px-2 py-0.5">Judges: {c.judges}</span>
                  )}
                  {c.date && c.date !== "Not available" && (
                    <span className="rounded bg-white/5 px-2 py-0.5">{c.date}</span>
                  )}
                  <span className="rounded bg-white/5 px-2 py-0.5">Case {c.id}</span>
                </div>
              </Link>
            ))}
          </div>
          {err && !answer && <p className="mt-4 text-sm text-muted-foreground">{err}</p>}
        </section>
      </div>
    </div>
  )
}
