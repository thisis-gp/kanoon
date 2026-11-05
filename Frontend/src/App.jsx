"use client"

import { Routes, Route, Navigate } from "react-router-dom"
import { useAuth } from "./context/auth-context"

// Pages
import HomePage from "./pages/HomePage"
import ResultsPage from "./pages/ResultsPage"
import LoginPage from "./pages/LoginPage"
import SignupPage from "./pages/SignupPage"
import CasePage from "./pages/CasePage"
import HistoryPage from "./pages/HistoryPage"
import AboutPage from "./pages/AboutPage"

// Protected route component
const ProtectedRoute = ({ children }) => {
  const { user, loading } = useAuth()

  if (loading) {
    return <div role="status" className="flex items-center justify-center h-screen">Loading...</div>
  }

  if (!user) {
    return <Navigate to="/login" replace />
  }

  return children
}

function NotFound() {
  return (
    <div className="flex h-screen flex-col items-center justify-center gap-3 text-center">
      <h1 className="text-2xl font-semibold">Page not found</h1>
      <a href="/" className="text-indigo-300 underline">Back to search</a>
    </div>
  )
}

function App() {
  return (
    <>
    <a
      href="#main"
      className="sr-only focus:not-sr-only focus:fixed focus:left-2 focus:top-2 focus:z-50 focus:rounded focus:bg-indigo-600 focus:px-3 focus:py-2 focus:text-white"
    >
      Skip to content
    </a>
    <Routes>
      <Route path="/" element={<HomePage />} />
      <Route path="/results" element={<ResultsPage />} />
      <Route path="/ask" element={<Navigate to="/results" replace />} />
      <Route path="/login" element={<LoginPage />} />
      <Route path="/signup" element={<SignupPage />} />
      <Route path="/search" element={<Navigate to="/results" replace />} />
      <Route path="/about" element={<AboutPage />} />
      <Route path="/case/:id" element={<CasePage />} />
      <Route
        path="/history"
        element={
          <ProtectedRoute>
            <HistoryPage />
          </ProtectedRoute>
        }
      />
      <Route path="*" element={<NotFound />} />
    </Routes>
    </>
  )
}

export default App
