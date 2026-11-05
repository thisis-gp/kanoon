import { Link } from "react-router-dom"
import { Disclaimer } from "./disclaimer"
import { REPO_URL } from "../lib/site"

export function Footer() {
  return (
    <footer className="border-t border-white/10 px-4 py-8">
      <div className="mx-auto flex max-w-3xl flex-col gap-4">
        <Disclaimer />
        <nav aria-label="Footer" className="flex flex-wrap gap-x-5 gap-y-2 text-sm">
          <Link to="/about" className="text-indigo-300 hover:underline">About and data</Link>
          <a href={REPO_URL} target="_blank" rel="noopener noreferrer" className="text-indigo-300 hover:underline">
            Source on GitHub
          </a>
        </nav>
      </div>
    </footer>
  )
}
