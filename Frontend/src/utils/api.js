// Empty or unset VITE_API_URL means same origin (the backend serves this build).
// On Vercel, set it to the API origin, for example https://example.ngrok-free.dev
// Optional bucket base for judgment PDFs (e.g. Oracle Object Storage). Unset = same-origin /supreme_court_pdfs.
export const PDF_BASE_URL = (import.meta.env.KANOON_PDF_BASE_URL ?? "").trim().replace(/\/+$/, "")

const API_BASE_URL = (import.meta.env.VITE_API_URL ?? "").trim().replace(/\/+$/, "")

export const ABSTAIN_TEXT = "Not available in the sources."
const DEFAULT_RETRY_SECONDS = 30

/** Error with a status code and a message that is safe to show to users. */
export class ApiError extends Error {
  constructor(kind, message, { status = 0, retryAfter = null } = {}) {
    super(message)
    this.name = "ApiError"
    this.kind = kind // "rate_limit" | "unavailable" | "network" | "bad_request" | "server"
    this.status = status
    this.retryAfter = retryAfter
  }
}

function formatWait(seconds) {
  if (seconds < 90) return `${seconds} seconds`
  if (seconds < 5400) return `${Math.round(seconds / 60)} minutes`
  return `${Math.round(seconds / 3600)} hours`
}

async function toApiError(response) {
  let detail = ""
  try {
    const body = await response.json()
    detail = typeof body?.detail === "string" ? body.detail : ""
  } catch {
    // body is not JSON; fall back to the status text
  }
  const { status } = response

  if (status === 429) {
    const parsed = Number.parseInt(response.headers.get("Retry-After") ?? "", 10)
    const retryAfter = Number.isFinite(parsed) && parsed > 0 ? parsed : DEFAULT_RETRY_SECONDS
    return new ApiError("rate_limit", `Too many requests. Please try again in ${formatWait(retryAfter)}.`, {
      status,
      retryAfter,
    })
  }
  if (status === 503) {
    return new ApiError(
      "unavailable",
      "The answer service is busy or unavailable. Search results still work.",
      { status },
    )
  }
  if (status === 400 || status === 422) {
    return new ApiError("bad_request", detail || "That request could not be processed.", { status })
  }
  return new ApiError("server", detail || "Something went wrong on the server. Please try again.", { status })
}

export async function fetchAPI(endpoint, options = {}) {
  const url = `${API_BASE_URL}${endpoint}`
  let response
  try {
    response = await fetch(url, {
      ...options,
      headers: {
        "Content-Type": "application/json",
        "ngrok-skip-browser-warning": "1",
        ...(options.headers || {}),
      },
    })
  } catch (error) {
    if (error?.name === "AbortError") throw error
    throw new ApiError("network", "Cannot reach the server. Check your connection and try again.")
  }
  if (!response.ok) throw await toApiError(response)
  try {
    return await response.json()
  } catch {
    throw new ApiError("server", "The server sent an unreadable response.", { status: response.status })
  }
}

/** Message to show for any thrown value. */
export function describeError(error) {
  return error instanceof ApiError ? error.message : "Something went wrong. Please try again."
}

/** True when the backend declined to answer because the sources had nothing. */
export function isAbstention(result) {
  return typeof result?.answer === "string" && result.answer.trim() === ABSTAIN_TEXT
}

// Grounded answer across all cases.
// Returns { answer, provider, sources: [{n, case_id, text}], cited: [n...] }
export function askQuestion(query, k = 6) {
  return fetchAPI("/ask", { method: "POST", body: JSON.stringify({ query, k }) })
}

// Per-case chat, scoped to one judgment. Same shape as askQuestion.
export function sendChatMessage(caseId, question) {
  return fetchAPI("/chat_query", { method: "POST", body: JSON.stringify({ case_id: caseId, question }) })
}

// Popular recent queries for home suggestions.
export async function getSuggestions() {
  const res = await fetchAPI("/suggestions")
  return res.suggestions || []
}

// Citation graph
export function getCites(caseId) {
  return fetchAPI(`/cases/${encodeURIComponent(caseId)}/cites`)
}
export function getCitedBy(caseId) {
  return fetchAPI(`/cases/${encodeURIComponent(caseId)}/cited-by`)
}

// Case cards for a query (no LLM, fast)
export async function searchLegalCases(query, topK = 5) {
  const response = await fetchAPI("/query", {
    method: "POST",
    body: JSON.stringify({ query, top_k: topK }),
  })
  return (response.results || []).map((r) => ({
    id: r.id,
    title: r.title,
    judges: r.judges,
    date: r.date,
    summary: r.summary,
    source: r.source,
  }))
}

// Case metadata. The backend sends id, title, judges, date, summary; the PDF path is built here.
export async function getCaseById(id) {
  const response = await fetchAPI(`/cases/${encodeURIComponent(id)}`)
  return {
    id: response.id,
    title: response.title || `Case ${id}`,
    judges: response.judges || "Not available",
    date: response.date || "Not available",
    summary: response.summary || "Legal case summary not available",
    pdfUrl: `${PDF_BASE_URL || "/supreme_court_pdfs"}/${encodeURIComponent(id)}.pdf`,
  }
}
