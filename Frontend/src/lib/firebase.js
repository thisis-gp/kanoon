import { initializeApp } from "firebase/app"
import { getAuth, GoogleAuthProvider } from "firebase/auth"
import { getFirestore } from "firebase/firestore"

const env = import.meta.env

const firebaseConfig = {
  apiKey: env.VITE_FIREBASE_API_KEY,
  authDomain: env.VITE_FIREBASE_AUTH_DOMAIN,
  projectId: env.VITE_FIREBASE_PROJECT_ID,
  storageBucket: env.VITE_FIREBASE_STORAGE_BUCKET,
  messagingSenderId: env.VITE_FIREBASE_MESSAGING_SENDER_ID,
  appId: env.VITE_FIREBASE_APP_ID,
}

const REQUIRED_KEYS = ["apiKey", "authDomain", "projectId", "appId"]

// Login is optional. Search and the case page work without Firebase, so a missing
// or broken config must never crash the app: the exports below are null instead.
export const firebaseEnabled = REQUIRED_KEYS.every((key) => Boolean(firebaseConfig[key]))

let app = null
let auth = null
let db = null
let googleProvider = null

if (firebaseEnabled) {
  try {
    app = initializeApp(firebaseConfig)
    auth = getAuth(app)
    db = getFirestore(app)
    googleProvider = new GoogleAuthProvider()
  } catch (error) {
    console.warn("Firebase failed to initialise; login is disabled.", error?.code || "")
    app = auth = db = googleProvider = null
  }
}

export const firebaseReady = Boolean(auth)
export { auth, db, googleProvider }
export default app
