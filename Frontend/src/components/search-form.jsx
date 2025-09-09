"use client"

import { useState } from "react"
import { Button } from "./ui/button"
import { Input } from "./ui/input"
import { Search, SlidersHorizontal } from "lucide-react"
import {Label} from "./ui/label"
import { Slider } from "./ui/slider"

export function SearchForm({ onSearch, initialQuery = "", initialTopK = 5 }) {
  const [query, setQuery] = useState(initialQuery)
  const [topK, setTopK] = useState(initialTopK)

  const handleSubmit = (e) => {
    e.preventDefault()
    if (query.trim()) {
      onSearch(query.trim(), topK)
    }
  }

  return (
    <form onSubmit={handleSubmit} className="relative mb-8">
      <div className="fex flex-col gap-4">
      <div className="flex items-center">
        <Input
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          className="pl-12 py-7 text-xl rounded-full"
          placeholder="Search legal cases..."
        />
        <Search className="absolute left-4 top-1/4 h-6 w-6 -translate-y-1/2 text-muted-foreground" />
        <Button type="submit" className="ml-2 rounded-full h-14 px-6">
          Search
        </Button>
      </div>
      <div className="flex items-center gap-4 px-4">
          <SlidersHorizontal className="h-5 w-5 text-muted-foreground" />
          <div className="flex-1">
            <Label htmlFor="results-count" className="text-sm font-medium mb-1 block">
              Number of results: {topK}
            </Label>
            <Slider
              id="results-count"
              min={1}
              max={10}
              step={1}
              value={[topK]}
              onValueChange={(value) => {
                setTopK(value[0])
                onTopKChange(value[0])
              }}
              className="w-full"
            />
          </div>
          <div className="w-16">
            <Input
              type="number"
              min={1}
              max={10}
              value={topK}
              onChange={(e) => {
                const newValue = Number.parseInt(e.target.value) || 5
                setTopK(newValue)
                onTopKChange(newValue)
              }}
              className="w-full text-center"
            />
          </div>
        </div>
      </div>
    </form>
  )
}