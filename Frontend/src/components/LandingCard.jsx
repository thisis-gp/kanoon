import { Link } from "react-router-dom"

function LandingCard({ href, title, body }) {
  return (
    <li className="list-none flex p-[1px] bg-[#23262d] rounded-lg transition-all duration-600 ease-[cubic-bezier(0.22,1,0.36,1)] shadow-[inset_0_0_0_1px_rgba(255,255,255,0.1)] hover:bg-gradient-to-r hover:from-[#8844ee] hover:via-[#e0ccfa] hover:to-white">
      <Link
        to={href}
        className="w-full no-underline leading-[1.4] p-[calc(1.5rem-1px)] rounded-lg text-white bg-[#23262d] opacity-80"
      >
        <h2 className="m-0 text-xl transition-colors duration-600 ease-[cubic-bezier(0.22,1,0.36,1)] group-hover:text-[rgb(224,204,250)]">
          {title}
          <span>&rarr;</span>
        </h2>
        <p className="mt-2 mb-0">{body}</p>
      </Link>
    </li>
  )
}

export default LandingCard

