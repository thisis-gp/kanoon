import { Skeleton } from "./ui/skeleton"
import { Card, CardContent, CardHeader, CardTitle } from "./ui/card"
import { Badge } from "./ui/badge"
import { CalendarIcon, GavelIcon } from "lucide-react"

export function CaseSummary({ caseData, isLoading }) {
  if (isLoading) {
    return (
      <div className="p-6 space-y-6">
        <Skeleton className="h-10 w-3/4 mb-4" />
        <Skeleton className="h-6 w-1/2 mb-2" />
        <Skeleton className="h-6 w-1/3 mb-6" />
        <Skeleton className="h-32 w-full mb-6" />
        <Skeleton className="h-6 w-full mb-2" />
        <Skeleton className="h-6 w-full mb-2" />
        <Skeleton className="h-6 w-3/4" />
      </div>
    )
  }

  if (!caseData) {
    return (
      <div className="p-6 text-center">
        <p className="text-muted-foreground">No case data available</p>
      </div>
    )
  }

  return (
    <div className="p-6 space-y-6">
      <h1 className="text-3xl font-bold">{caseData.title}</h1>

      <div className="flex flex-wrap gap-4">
        {caseData.date && (
          <div className="flex items-center gap-2">
            <CalendarIcon className="h-5 w-5 text-muted-foreground" />
            <span>{caseData.date}</span>
          </div>
        )}

        {caseData.judges && (
          <div className="flex items-center gap-2">
            <GavelIcon className="h-5 w-5 text-muted-foreground" />
            <span>{caseData.judges}</span>
          </div>
        )}
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Summary</CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-lg leading-relaxed">{caseData.summary}</p>
        </CardContent>
      </Card>

      {caseData.keyFindings && (
        <Card>
          <CardHeader>
            <CardTitle>Key Findings</CardTitle>
          </CardHeader>
          <CardContent>
            <ul className="list-disc pl-5 space-y-2">
              {caseData.keyFindings.map((finding, index) => (
                <li key={index}>{finding}</li>
              ))}
            </ul>
          </CardContent>
        </Card>
      )}

      {caseData.precedents && (
        <Card>
          <CardHeader>
            <CardTitle>Precedents</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="flex flex-wrap gap-2">
              {caseData.precedents.map((precedent, index) => (
                <Badge key={index} variant="outline">
                  {precedent}
                </Badge>
              ))}
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  )
}
