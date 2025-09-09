"use client"

import { useState, useEffect } from "react"
import { Link } from "react-router-dom"
import { Button } from "./ui/button"
import { useTheme } from "./theme-provider"
import { Moon, Sun } from "lucide-react"

function Header() {
  const { theme, setTheme } = useTheme()
  const [mounted, setMounted] = useState(false)

  // Avoid hydration mismatch
  useEffect(() => {
    setMounted(true)
  }, [])

  const toggleTheme = () => {
    setTheme(theme === "dark" ? "light" : "dark")
  }

  return (
    <header className="container">
      <div className="flex justify-between items-center py-5 px-3">
        <div className="flex items-center pt-3">
          <Link to="/">
            <div className="text-2xl font-bold text-white">Kanoon</div>
          </Link>
        </div>

        <div className="hidden items-center gap-4 md:flex">
          {mounted && (
            <Button variant="ghost" size="icon" onClick={toggleTheme} className="text-white hover:bg-gray-800">
              {theme === "dark" ? <Sun className="h-5 w-5" /> : <Moon className="h-5 w-5" />}
              <span className="sr-only">Toggle theme</span>
            </Button>
          )}

          <Link to="/login">
            <Button variant="outline" className="border-gray-700 bg-transparent text-white hover:bg-gray-800">
              Log in
            </Button>
          </Link>

          <Link to="/signup">
            <Button className="bg-[#8844ee] hover:bg-[#7733dd] text-white">Sign up</Button>
          </Link>
        </div>

        {/* Mobile menu */}
        <div className="flex items-center gap-2 md:hidden">
          {mounted && (
            <Button variant="ghost" size="icon" onClick={toggleTheme} className="text-white hover:bg-gray-800">
              {theme === "dark" ? <Sun className="h-5 w-5" /> : <Moon className="h-5 w-5" />}
              <span className="sr-only">Toggle theme</span>
            </Button>
          )}

          <Link to="/login">
            <Button variant="outline" size="sm" className="border-gray-700 bg-transparent text-white hover:bg-gray-800">
              Log in
            </Button>
          </Link>
        </div>
      </div>
    </header>
  )
}

export default Header

