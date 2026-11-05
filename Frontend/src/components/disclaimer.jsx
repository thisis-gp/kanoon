import { Info } from "lucide-react"
import { DISCLAIMER } from "../lib/site"

export function Disclaimer({ className = "" }) {
  return (
    <p className={`flex items-start gap-2 text-xs leading-relaxed text-muted-foreground ${className}`}>
      <Info className="mt-0.5 h-3.5 w-3.5 shrink-0" aria-hidden="true" />
      <span>{DISCLAIMER}</span>
    </p>
  )
}
