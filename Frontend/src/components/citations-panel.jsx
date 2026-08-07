"use client"

import { useState, useEffect } from "react"
import { Link } from "react-router-dom"
import { getCites, getCitedBy } from "../utils/api"

export default function CitationsPanel({ caseId }) {
  const [cites, setCites] = useState([])
  const [citedBy, setCitedBy] = useState([])
  const [isLoading, setIsLoading] = useState(true)

  useEffect(() => {
    let active = true
    const load = async () => {
      setIsLoading(true)
      let citesData = []
      let citedByData = []
      try {
        const res = await getCites(caseId)
        citesData = res?.cites || []
      } catch (error) {
        console.error("Error fetching cites:", error)
      }
      try {
        const res = await getCitedBy(caseId)
        citedByData = res?.cited_by || []
      } catch (error) {
        console.error("Error fetching cited-by:", error)
      }
      if (active) {
        setCites(citesData)
        setCitedBy(citedByData)
        setIsLoading(false)
      }
    }
    load()
    return () => {
      active = false
    }
  }, [caseId])

  return (
    <div className="rounded-xl border border-white/10 bg-white/[0.02] p-4 space-y-5">
      {isLoading ? (
        <p className="text-sm text-muted-foreground">Loading citations…</p>
      ) : (
        <>
          <section className="space-y-2">
            <h3 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Cites</h3>
            {cites.length === 0 ? (
              <p className="text-sm text-muted-foreground">No outbound citations found.</p>
            ) : (
              <ul className="space-y-1.5">
                {cites.map((c, i) => (
                  <li key={i} className="flex items-center gap-2 text-sm text-foreground">
                    <span>{c.ref}</span>
                    {c.type && (
                      <span className="bg-white/10 text-[10px] rounded px-1 uppercase text-muted-foreground">
                        {c.type}
                      </span>
                    )}
                  </li>
                ))}
              </ul>
            )}
          </section>

          <section className="space-y-2">
            <h3 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Cited by</h3>
            {citedBy.length === 0 ? (
              <p className="text-sm text-muted-foreground">Not cited by other cases in the corpus.</p>
            ) : (
              <ul className="flex flex-wrap gap-x-4 gap-y-1.5">
                {citedBy.map((id) => (
                  <li key={id}>
                    <Link to={`/case/${id}`} className="text-sm text-indigo-400 hover:underline">
                      Case {id}
                    </Link>
                  </li>
                ))}
              </ul>
            )}
          </section>
        </>
      )}
    </div>
  )
}
