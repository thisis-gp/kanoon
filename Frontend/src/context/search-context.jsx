"use client"

import { createContext, useContext, useState } from "react"

const SearchContext = createContext({})

export function SearchProvider({ children }) {
  const [searchResults, setSearchResults] = useState([])
  const [searchQuery, setSearchQuery] = useState("")
  const [hasSearched, setHasSearched] = useState(false)
  const [isLoading, setIsLoading] = useState(false)

  const updateSearchResults = (results, query) => {
    setSearchResults(results)
    setSearchQuery(query)
    setHasSearched(true)
  }

  const clearSearch = () => {
    setSearchResults([])
    setSearchQuery("")
    setHasSearched(false)
  }

  return (
    <SearchContext.Provider
      value={{
        searchResults,
        searchQuery,
        hasSearched,
        isLoading,
        setIsLoading,
        updateSearchResults,
        clearSearch,
      }}
    >
      {children}
    </SearchContext.Provider>
  )
}

export const useSearch = () => {
  const context = useContext(SearchContext)
  if (context === undefined) {
    throw new Error("useSearch must be used within a SearchProvider")
  }
  return context
}
