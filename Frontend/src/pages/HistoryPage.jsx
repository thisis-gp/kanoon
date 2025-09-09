"use client"

import { useState, useEffect } from "react"
import { useNavigate } from "react-router-dom"
import { Navbar } from "../components/navbar"
import { useAuth } from "../context/auth-context"
import { getSearchHistory, clearSearchHistory, deleteSearchHistoryItem } from "../utils/firebase-helpers"
import { Button } from "../components/ui/button"
import { Card, CardContent } from "../components/ui/card"
import { Separator } from "../components/ui/separator"
import { Clock, Search, Trash, Trash2, AlertCircle } from "lucide-react"
import { formatDistanceToNow } from "date-fns"

export default function HistoryPage() {
  const { user } = useAuth()
  const navigate = useNavigate()
  const [history, setHistory] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  useEffect(() => {
    if (!user) {
      navigate("/login")
      return
    }

    const loadHistory = async () => {
      try {
        setLoading(true)
        const data = await getSearchHistory(user.uid)
        setHistory(data)
      } catch (err) {
        console.error("Failed to load history:", err)
        setError("Failed to load search history. Please try again.")
      } finally {
        setLoading(false)
      }
    }

    loadHistory()
  }, [user, navigate])

  const handleDeleteItem = async (id) => {
    try {
      await deleteSearchHistoryItem(user.uid, id)
      setHistory(history.filter((item) => item.id !== id))
    } catch (err) {
      console.error("Failed to delete history item:", err)
      setError("Failed to delete history item. Please try again.")
    }
  }

  const handleClearHistory = async () => {
    if (!window.confirm("Are you sure you want to clear all search history?")) {
      return
    }

    try {
      await clearSearchHistory(user.uid)
      setHistory([])
    } catch (err) {
      console.error("Failed to clear history:", err)
      setError("Failed to clear history. Please try again.")
    }
  }

  // const handleSearchAgain = (query) => {
  //   navigate(`/search?q=${encodeURIComponent(query)}`)
  // }

  return (
    <div className="min-h-screen bg-background">
      <Navbar />

      <main className="container mx-auto px-4 py-8">
        <div className="flex items-center justify-between mb-6">
          <h1 className="text-3xl font-bold">Search History</h1>
          {history.length > 0 && (
            <Button variant="outline" onClick={handleClearHistory} className="flex items-center gap-2">
              <Trash2 className="h-4 w-4" />
              Clear All
            </Button>
          )}
        </div>

        <Separator className="mb-6" />

        {loading ? (
          <div className="flex justify-center py-12">
            <div className="animate-spin rounded-full h-12 w-12 border-t-2 border-b-2 border-primary"></div>
          </div>
        ) : error ? (
          <div className="flex flex-col items-center justify-center py-12">
            <AlertCircle className="h-12 w-12 text-destructive mb-4" />
            <p className="text-destructive text-lg">{error}</p>
          </div>
        ) : history.length === 0 ? (
          <div className="text-center py-12">
            <Clock className="h-16 w-16 mx-auto text-muted-foreground mb-4" />
            <h2 className="text-xl font-semibold mb-2">No search history yet</h2>
            <p className="text-muted-foreground">
              Your search history will appear here once you start searching for legal precedents.
            </p>
            <Button className="mt-6" onClick={() => navigate("/search")}>
              Go to Search
            </Button>
          </div>
        ) : (
          <div className="space-y-4">
            {history.map((item) => (
              <Card key={item.id} className="hover:bg-accent/50 transition-colors">
                <CardContent className="p-4">
                  <div className="flex items-center justify-between">
                    <div className="flex-1">
                      <div className="flex items-center gap-2">
                        <Search className="h-4 w-4 text-muted-foreground" />
                        <h3 className="text-lg font-medium">{item.query}</h3>
                      </div>
                      <div className="flex items-center gap-4 mt-2 text-sm text-muted-foreground">
                        <span>
                          {item.timestamp
                            ? formatDistanceToNow(new Date(item.timestamp.toDate()), { addSuffix: true })
                            : "Recently"}
                        </span>
                        <span>{item.resultCount} results</span>
                      </div>
                    </div>
                    <div className="flex items-center gap-2">
                      {/* <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => handleSearchAgain(item.query)}
                        className="text-primary"
                      >
                        Search Again
                      </Button> */}
                      <Button
                        variant="ghost"
                        size="icon"
                        onClick={() => handleDeleteItem(item.id)}
                        className="text-muted-foreground hover:text-destructive"
                      >
                        <Trash className="h-4 w-4" />
                      </Button>
                    </div>
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
        )}
      </main>
    </div>
  )
}
