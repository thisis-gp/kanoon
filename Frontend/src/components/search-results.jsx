import { Link } from "react-router-dom"
import { Card, CardContent } from "./ui/card"
import { Skeleton } from "./ui/skeleton"
import { Badge } from "./ui/badge"
import { History } from "lucide-react"

export function SearchResults({ 
  results = [], 
  isLoading = false,
  query = "",
  resultCount = 0
}) {
  if (isLoading) {
    return (
      <div className="space-y-6">
        {[1, 2, 3].map((i) => (
          <Card key={i} className="overflow-hidden">
            <CardContent className="p-6">
              <Skeleton className="h-8 w-2/3 mb-4" />
              <Skeleton className="h-4 w-full mb-2" />
              <Skeleton className="h-4 w-full mb-2" />
              <Skeleton className="h-4 w-3/4" />
              <div className="flex gap-2 mt-4">
                <Skeleton className="h-6 w-24" />
                <Skeleton className="h-6 w-32" />
              </div>
            </CardContent>
          </Card>
        ))}
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center mb-4">
        {query && (
          <h2 className="text-2xl font-semibold">
            Results for "{query}"{" "}
            <span className="text-muted-foreground text-lg">({resultCount} cases found)</span>
          </h2>
        )}
        <Link to="/history" className="flex items-center gap-2 text-primary">
          <History className="h-4 w-4" />
          <span>View History</span>
        </Link>
      </div>

      {results.length === 0 ? (
        <div className="text-center py-12 border rounded-lg">
          <h3 className="text-xl font-semibold mb-2">No results found</h3>
          <p className="text-muted-foreground">Try adjusting your search terms or browse our categories</p>
        </div>
      ) : (
        results.map((result) => (
          <Card key={result.id} className="overflow-hidden hover:shadow-md transition-shadow">
            <CardContent className="p-6">
              <h3 className="text-2xl font-semibold mb-2">
                <Link to={`/case/${result.id}`} className="text-primary hover:underline">
                  {result.title}
                </Link>
              </h3>
              <p className="text-lg mb-4">{result.summary}</p>
              <div className="flex flex-wrap gap-3 text-sm text-muted-foreground">
                {result.judges && <Badge variant="outline">Judges: {result.judges}</Badge>}
                {result.date && <Badge variant="outline">Date: {result.date}</Badge>}
                <Badge variant="secondary">ID: {result.id}</Badge>
              </div>
            </CardContent>
          </Card>
        ))
      )}
    </div>
  )
}