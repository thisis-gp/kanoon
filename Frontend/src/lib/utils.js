/** Join class names, skipping falsy values. */
export function cn(...classes) {
  return classes.filter(Boolean).join(" ")
}

/** Shorten text to max characters, adding an ellipsis only when something was cut. */
export function clip(text, max) {
  const t = (text || "").trim()
  return t.length <= max ? t : `${t.slice(0, max).trimEnd()}…`
}

/** Title to display; the backend sends "Not available" when it could not extract one. */
export function displayTitle(title, id) {
  const t = (title || "").trim()
  return !t || t === "Not available" ? `Untitled judgment (case ${id})` : t
}
