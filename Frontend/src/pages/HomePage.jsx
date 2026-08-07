"use client"

import { useState, useEffect } from "react"
import { useNavigate } from "react-router-dom"
import { Navbar } from "../components/navbar"
import { getSuggestions } from "../utils/api"

// mix of search-style topics and answerable questions
const EXAMPLES = [
  "Murder cases",
  "Cases under Section 302 IPC",
  "What are the conditions for anticipatory bail?",
  "Difference between culpable homicide and murder",
]

// A question → grounded answer (/ask); a topic/section → case list (/search).
export function isQuestion(text) {
  const s = text.trim().toLowerCase()
  return s.endsWith("?") ||
    /^(what|when|how|why|can|could|is|are|do|does|did|which|whether|should|who|explain|difference|define)\b/.test(s)
}

const FEATURES = [
  ["Grounded answers", "Every answer is built only from real judgments, with inline [n] citations you can click — no hallucinations."],
  ["Hybrid search", "Semantic + keyword search with reranking finds the right case, not just keyword matches."],
  ["Case explorer", "Open any judgment, read the PDF, chat with it, and see which cases it cites."],
]

export default function HomePage() {
  const [q, setQ] = useState("")
  const [chips, setChips] = useState(EXAMPLES)   // popular history, falls back to defaults
  const navigate = useNavigate()

  useEffect(() => {
    getSuggestions().then((s) => { if (s?.length) setChips(s) }).catch(() => {})
  }, [])
  const go = (text) => navigate(`/results?q=${encodeURIComponent(text.trim())}`)
  const submit = (e) => { e.preventDefault(); if (q.trim()) go(q.trim()) }

  return (
    <div className="min-h-screen bg-background text-foreground">
      <Navbar />

      <main className="mx-auto max-w-3xl px-4 pt-16 pb-24 text-center md:pt-24">
        <span className="inline-flex items-center gap-2 rounded-full border border-white/10 bg-white/5 px-3 py-1 text-xs font-medium text-indigo-300">
          ⚖️ 900+ Supreme Court judgments · answers with sources
        </span>

        <h1 className="mt-6 text-4xl font-bold tracking-tight md:text-6xl">
          Research Indian law,
          <br />
          <span className="text-indigo-400">answered with citations</span>
        </h1>

        <p className="mx-auto mt-5 max-w-xl text-lg text-muted-foreground">
          Ask a question in plain English. Kanoon reads Supreme Court judgments and
          answers with sources you can open — grounded, never made up.
        </p>

        <form
          onSubmit={submit}
          className="mx-auto mt-8 flex max-w-2xl items-center gap-2 rounded-xl border border-white/10 bg-white/5 p-2 transition focus-within:border-indigo-500"
        >
          <input
            value={q}
            onChange={(e) => setQ(e.target.value)}
            placeholder="Ask anything about Indian case law…"
            className="flex-1 bg-transparent px-3 py-2 text-base outline-none placeholder:text-muted-foreground"
          />
          <button className="rounded-lg bg-indigo-600 px-6 py-2 font-semibold text-white transition hover:bg-indigo-700">
            Ask
          </button>
        </form>

        <div className="mx-auto mt-4 flex max-w-2xl flex-wrap justify-center gap-2">
          {chips.map((x) => (
            <button
              key={x}
              onClick={() => go(x)}
              className="rounded-full border border-white/10 bg-white/[0.03] px-3 py-1.5 text-sm text-muted-foreground transition hover:border-indigo-500/50 hover:text-foreground"
            >
              {x}
            </button>
          ))}
        </div>

        <div className="mt-20 grid grid-cols-1 gap-4 text-left sm:grid-cols-3">
          {FEATURES.map(([title, body]) => (
            <div key={title} className="rounded-xl border border-white/10 bg-white/[0.02] p-5">
              <h3 className="font-semibold">{title}</h3>
              <p className="mt-2 text-sm text-muted-foreground">{body}</p>
            </div>
          ))}
        </div>
      </main>
    </div>
  )
}
