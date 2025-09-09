import React from "react"
import ReactDOM from "react-dom/client"
import { BrowserRouter } from "react-router-dom"
import App from "./App.jsx"
import { ThemeProvider } from "./context/theme-context.jsx"
import "./index.css"
import "./fonts.css"
import { AuthProvider } from "./context/auth-context.jsx"
import { SearchProvider } from "./context/search-context.jsx"

ReactDOM.createRoot(document.getElementById("root")).render(
  <React.StrictMode>
    <BrowserRouter>
      <AuthProvider>
      <ThemeProvider>
      <SearchProvider>
        <App />
      </SearchProvider>
      </ThemeProvider>
      </AuthProvider>
    </BrowserRouter>
  </React.StrictMode>,
)
