"use client"

import { useState, useEffect } from "react"
import { useNavigate, useSearchParams } from "react-router-dom"
import { useAuth } from "../context/auth-context"
import { Navbar } from "../components/navbar"
import { SearchForm } from "../components/search-form"
import { SearchResults } from "../components/search-results"
import { searchLegalCases } from "../utils/api"
import { saveSearchHistory } from "../utils/firebase-helpers"
import { Logo } from "../components/logo"

export default function SearchPage() {
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const queryParam = searchParams.get("q") || ""
  const topKParam = searchParams.get("count") ? Number(searchParams.get("count")) : 5
  const { user } = useAuth()

  const [results, setResults] = useState([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  useEffect(() => {
    if (queryParam) {
      performSearch(queryParam, topKParam)
    }
  }, [queryParam, topKParam])

  const performSearch = async (searchTerm, resultCount = 5) => {
    setLoading(true)
    setError(null)

    try {
      const data = await searchLegalCases(searchTerm, resultCount)
      setResults(data)

      if (user) {
        await saveSearchHistory(user.uid, searchTerm, data.length)
      }
    } catch (error) {
      console.error("Search error:", error)
      setError("Failed to perform search. Please try again.")
    } finally {
      setLoading(false)
    }
  }

  const handleSearch = (query, count) => {
    navigate(`/search?q=${encodeURIComponent(query)}&count=${count}`)
  }

  return (
    <div className="min-h-screen bg-background">
      <Navbar />

      <main className="container mx-auto px-4 py-8 max-w-4xl">
        {!queryParam && (
          <div className="text-center mb-16 mt-8">
            <div className="flex justify-center mb-6">
              <Logo size="large" />
            </div>
            <h1 className="text-5xl font-bold mb-6">Kanoon Legal Search</h1>
            <p className="text-xl text-muted-foreground max-w-2xl mx-auto">
              Search for legal cases by keywords, case names, or legal concepts.
            </p>
          </div>
        )}

        <SearchForm 
          onSearch={handleSearch}
          initialQuery={queryParam}
          initialTopK={topKParam}
        />

        {error && (
          <div className="text-center my-8 p-4 border border-destructive rounded-lg">
            <p className="text-destructive">{error}</p>
          </div>
        )}

        {(queryParam || loading) && (
          <SearchResults
            results={results}
            isLoading={loading}
            query={queryParam}
            resultCount={results.length}
          />
        )}
      </main>
    </div>
  )
}