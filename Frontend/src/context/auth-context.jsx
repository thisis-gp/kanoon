"use client"

import { createContext, useContext, useState, useEffect } from "react"
import {
  createUserWithEmailAndPassword,
  signInWithEmailAndPassword,
  signOut,
  onAuthStateChanged,
  signInWithPopup,
  updateProfile,
} from "firebase/auth"
import { doc, setDoc, serverTimestamp } from "firebase/firestore"
import { auth, googleProvider, db, firebaseReady } from "../lib/firebase"

const AuthContext = createContext()

const LOGIN_UNAVAILABLE = "Login is not available in this deployment. Search and case pages work without an account."

function requireAuth() {
  if (!firebaseReady) throw new Error(LOGIN_UNAVAILABLE)
}

export function useAuth() {
  return useContext(AuthContext)
}

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null)
  const [loading, setLoading] = useState(true)

  // Sign up with email and password
  const signup = async (name, email, password) => {
    requireAuth()
    try {
      const userCredential = await createUserWithEmailAndPassword(auth, email, password)

      // Update profile with name
      await updateProfile(userCredential.user, {
        displayName: name,
      })

      // Create user document in Firestore
      await setDoc(doc(db, "users", userCredential.user.uid), {
        name,
        email,
        createdAt: serverTimestamp(),
      })

      return userCredential.user
    } catch (error) {
      console.error("Signup error:", error)
      throw error
    }
  }

  // Sign in with email and password
  const login = async (email, password) => {
    requireAuth()
    return signInWithEmailAndPassword(auth, email, password)
  }

  // Sign in with Google
  const loginWithGoogle = async () => {
    requireAuth()
    const result = await signInWithPopup(auth, googleProvider)

    // Create the user document the first time someone signs in
    if (result._tokenResponse?.isNewUser) {
      await setDoc(doc(db, "users", result.user.uid), {
        name: result.user.displayName,
        email: result.user.email,
        createdAt: serverTimestamp(),
      })
    }

    return result.user
  }

  // Sign out
  const logout = async () => {
    if (!auth) return
    return signOut(auth)
  }

  // Listen for auth state changes
  useEffect(() => {
    if (!auth) {
      setLoading(false)
      return undefined
    }
    const unsubscribe = onAuthStateChanged(
      auth,
      (currentUser) => {
        setUser(currentUser)
        setLoading(false)
      },
      () => setLoading(false),
    )

    return unsubscribe
  }, [])

  const value = {
    user,
    loading,
    signup,
    login,
    loginWithGoogle,
    logout,
    loginAvailable: firebaseReady,
  }

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

