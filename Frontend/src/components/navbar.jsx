"use client"

import { Link, useNavigate, useLocation } from "react-router-dom"
import { useAuth } from "../context/auth-context"
import { useTheme } from "../context/theme-context"
import { Button } from "./ui/button"
import { Avatar, AvatarFallback, AvatarImage } from "./ui/avatar"
import { Sun, Moon, Menu, Search, Clock } from "lucide-react"
import { useState } from "react"
import { Logo } from "./logo"

export function Navbar() {
  const { user, logout } = useAuth()
  const { theme, toggleTheme } = useTheme()
  const navigate = useNavigate()
  const location = useLocation()
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false)

  const handleLogout = async () => {
    try {
      await logout()
      navigate("/")
    } catch (error) {
      console.error("Failed to log out", error)
    }
  }

  // Check if we're on auth pages
  const isAuthPage = location.pathname === "/login" || location.pathname === "/signup"

  // Get user initials for avatar fallback
  const getUserInitials = () => {
    if (user?.displayName) {
      return user.displayName
        .split(" ")
        .map((name) => name[0])
        .join("")
        .toUpperCase()
        .substring(0, 2)
    }

    if (user?.email) {
      return user.email[0].toUpperCase()
    }

    return "U"
  }

  return (
    <nav className="border-b bg-card">
      <div className="container mx-auto flex h-16 items-center justify-between px-4">
        <div className="flex items-center">
          <Link to="/" className="flex items-center">
            <Logo />
          </Link>
        </div>

        {/* Desktop Navigation */}
        <div className="hidden items-center gap-4 md:flex">
          <Button variant="ghost" size="icon" onClick={toggleTheme} aria-label="Toggle theme">
            {theme === "dark" ? <Sun className="h-5 w-5" /> : <Moon className="h-5 w-5" />}
          </Button>

          {user ? (
            <div className="flex items-center gap-4">
              <Link to="/search">
                <Button variant="ghost">Search</Button>
              </Link>
              <Link to="/history">
                <Button variant="ghost" className="flex items-center gap-2">
                  <Clock className="h-4 w-4" />
                  History
                </Button>
              </Link>
              <Avatar>
                {user.photoURL ? (
                  <AvatarImage src={user.photoURL} alt={user.displayName || user.email} />
                ) : (
                  <AvatarFallback className="bg-primary text-primary-foreground">{getUserInitials()}</AvatarFallback>
                )}
              </Avatar>
              <Button variant="outline" onClick={handleLogout}>
                Logout
              </Button>
            </div>
          ) : (
            <div className="flex items-center gap-2">
              {!isAuthPage && (
                <>
                  <Link to="/login">
                    <Button variant="outline">Login</Button>
                  </Link>
                  <Link to="/signup">
                    <Button>Sign Up</Button>
                  </Link>
                </>
              )}
            </div>
          )}
        </div>

        {/* Mobile Menu Button */}
        <div className="flex items-center md:hidden">
          <Button variant="ghost" size="icon" onClick={toggleTheme} aria-label="Toggle theme" className="mr-2">
            {theme === "dark" ? <Sun className="h-5 w-5" /> : <Moon className="h-5 w-5" />}
          </Button>
          <Button
            variant="ghost"
            size="icon"
            onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
            aria-label="Toggle menu"
          >
            <Menu className="h-5 w-5" />
          </Button>
        </div>
      </div>

      {/* Mobile Menu */}
      {mobileMenuOpen && (
        <div className="border-t bg-card px-4 py-2 md:hidden">
          {user ? (
            <div className="flex flex-col gap-2">
              <div className="flex items-center gap-2 py-2">
                <Avatar>
                  {user.photoURL ? (
                    <AvatarImage src={user.photoURL} alt={user.displayName || user.email} />
                  ) : (
                    <AvatarFallback className="bg-primary text-primary-foreground">{getUserInitials()}</AvatarFallback>
                  )}
                </Avatar>
                <span className="text-sm font-medium">{user.displayName || user.email}</span>
              </div>
              <Link to="/search" className="w-full">
                <Button variant="ghost" className="w-full justify-start">
                  Search
                </Button>
              </Link>
              <Link to="/history" className="w-full">
                <Button variant="ghost" className="w-full justify-start flex items-center gap-2">
                  <Clock className="h-4 w-4" />
                  History
                </Button>
              </Link>
              <Button variant="outline" onClick={handleLogout} className="w-full">
                Logout
              </Button>
            </div>
          ) : (
            <div className="flex flex-col gap-2 py-2">
              {!isAuthPage && (
                <>
                  <Link to="/login" className="w-full">
                    <Button variant="outline" className="w-full">
                      Login
                    </Button>
                  </Link>
                  <Link to="/signup" className="w-full">
                    <Button className="w-full">Sign Up</Button>
                  </Link>
                </>
              )}
            </div>
          )}
        </div>
      )}
    </nav>
  )
}

