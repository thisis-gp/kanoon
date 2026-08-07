"use client"

import { useState, useEffect } from "react"
import { Link, useNavigate } from "react-router-dom"
import { useAuth } from "../context/auth-context"
import { Navbar } from "../components/navbar"

export default function LoginPage() {
  const [error, setError] = useState("")
  const [loading, setLoading] = useState(false)
  const { loginWithGoogle, user } = useAuth()
  const navigate = useNavigate()

  useEffect(() => {
    if (user) {
      navigate("/")
    }
  }, [user, navigate])

  const handleGoogleLogin = async () => {
    setError("")
    try {
      setLoading(true)
      await loginWithGoogle()
      navigate("/")
    } catch (err) {
      console.error("Google login error:", err)
      setError("Failed to sign in with Google. Please try again.")
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen bg-background text-foreground">
      <Navbar />

      <main className="max-w-sm mx-auto mt-24 px-4">
        <div className="border border-white/10 bg-white/5 rounded-2xl p-8 text-center">
          <h1 className="text-2xl font-bold">Kanoon</h1>
          <p className="mt-2 text-sm text-muted-foreground">Sign in to save history</p>

          {error && <p className="mt-4 text-sm text-red-500">{error}</p>}

          <button
            type="button"
            onClick={handleGoogleLogin}
            disabled={loading}
            className="w-full rounded-lg bg-white text-gray-900 font-semibold py-3 hover:bg-gray-100 flex items-center justify-center gap-2 mt-6 disabled:opacity-70"
          >
            <svg width="18" height="18" viewBox="0 0 48 48">
              <path fill="#EA4335" d="M24 9.5c3.5 0 6.6 1.2 9 3.6l6.7-6.7C35.6 2.7 30.1 0 24 0 14.6 0 6.5 5.4 2.6 13.3l7.8 6C12.3 13.2 17.7 9.5 24 9.5z" />
              <path fill="#4285F4" d="M46.1 24.5c0-1.6-.1-3.1-.4-4.5H24v9h12.4c-.5 2.9-2.1 5.3-4.6 6.9l7.1 5.5C43.2 37.3 46.1 31.5 46.1 24.5z" />
              <path fill="#FBBC05" d="M10.4 28.3c-.5-1.4-.7-2.9-.7-4.3s.3-2.9.7-4.3l-7.8-6C.9 16.9 0 20.3 0 24s.9 7.1 2.6 10.3l7.8-6z" />
              <path fill="#34A853" d="M24 48c6.1 0 11.3-2 15-5.5l-7.1-5.5c-2 1.3-4.6 2.1-7.9 2.1-6.3 0-11.7-3.7-13.6-9.1l-7.8 6C6.5 42.6 14.6 48 24 48z" />
            </svg>
            {loading ? "Signing in…" : "Continue with Google"}
          </button>

          <p className="mt-6 text-sm text-muted-foreground">
            New here?{" "}
            <Link to="/signup" className="text-primary hover:underline">
              Sign up
            </Link>
          </p>
        </div>
      </main>
    </div>
  )
}
