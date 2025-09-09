import { clsx } from "clsx"
import { twMerge } from "tailwind-merge"


export function host() {
    return new URL(import.meta.url).origin
}

/**
 * Combines multiple class names into a single string
 * @param {string[]} classes - Class names to combine
 * @returns {string} - Combined class names
 */
export function cn(...classes) {
    return classes.filter(Boolean).join(" ")
  }
  
  /**
   * Format a date to a readable string
   * @param {Date} date - Date to format
   * @returns {string} - Formatted date
   */
  export function formatDate(date) {
    return new Intl.DateTimeFormat("en-US", {
      year: "numeric",
      month: "long",
      day: "numeric",
    }).format(new Date(date))
  }
  
  /**
   * Truncate a string to a specified length
   * @param {string} str - String to truncate
   * @param {number} length - Maximum length
   * @returns {string} - Truncated string
   */
  export function truncateText(str, length = 100) {
    if (!str || str.length <= length) return str
    return str.slice(0, length) + "..."
  }
  
  
