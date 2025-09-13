"use client"

import { useState, useEffect } from "react"
import { RefreshCw } from "lucide-react"
import { Button } from "./ui/button"

export function PDFViewerComponent({ pdfUrl }) {
  const [pageNumber, setPageNumber] = useState(1)
  const [scale] = useState(1)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [fullUrl, setFullUrl] = useState("")

  useEffect(() => {
    // Reset state when PDF URL changes
    setPageNumber(1)
    setLoading(true)
    setError(null)

    if (!pdfUrl) {
      setError("No PDF URL provided")
      setLoading(false)
      return
    }

    // Construct the full URL
    // If pdfUrl starts with http, use it directly, otherwise prepend the base URL
    const url = pdfUrl.startsWith("http") ? pdfUrl : `${window.location.origin}${pdfUrl}`

    console.log("PDF URL:", pdfUrl)
    console.log("Full URL:", url)
    setFullUrl(url)

    // Check if the PDF exists
    fetch(url, { method: "HEAD" })
      .then((response) => {
        console.log("PDF fetch response:", response.status, response.statusText)
        if (!response.ok) {
          throw new Error(`PDF not found: ${response.status}`)
        }
        setLoading(false)
      })
      .catch((err) => {
        console.error("Error loading PDF:", err)
        setError(`Failed to load PDF: ${err.message}`)
        setLoading(false)
      })
  }, [pdfUrl])

  const retryLoading = () => {
    setLoading(true)
    setError(null)

    // Small delay to ensure state updates before retrying
    setTimeout(() => {
      setLoading(false)
    }, 500)
  }

  return (
    <div className="flex flex-col h-full">

      <div className="flex-1 overflow-auto p-4">
        {loading ? (
          <div className="flex items-center justify-center h-full">
            <div className="animate-spin rounded-full h-12 w-12 border-t-2 border-b-2 border-primary"></div>
          </div>
        ) : error ? (
          <div className="flex flex-col items-center justify-center h-full text-center">
            <p className="text-destructive mb-4">{error}</p>
            <Button onClick={retryLoading} variant="outline" size="sm">
              <RefreshCw className="h-4 w-4 mr-2" />
              Retry
            </Button>
            <p className="text-xs text-muted-foreground mt-4">PDF URL: {fullUrl}</p>
          </div>
        ) : (
          <iframe
            src={`${fullUrl}#view=FitH&page=${pageNumber}`}
            className="w-full h-full border rounded"
            style={{
              transform: `scale(${scale})`,
              transformOrigin: "top left",
              height: `calc(100% / ${scale})`,
              width: `calc(100% / ${scale})`,
            }}
            title="PDF Viewer"
            onLoad={() => setLoading(false)}
            onError={() => {
              setError("Failed to load PDF document")
              setLoading(false)
            }}
          />
        )}
      </div>
    </div>
  )
}

