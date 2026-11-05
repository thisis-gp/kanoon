import { Navbar } from "../components/navbar"
import { Footer } from "../components/footer"
import { Disclaimer } from "../components/disclaimer"
import { CASE_COUNT, LII_URL, REPO_URL } from "../lib/site"

const STEPS = [
  ["Retrieval", "Your question is matched against passages of the judgments with two methods at once: semantic similarity and keyword (BM25) search. A reranking model then orders the best candidates."],
  ["Grounding", "The language model sees only the retrieved passages and is told to answer from them alone, not from its own knowledge."],
  ["Citations", "Each claim in an answer carries a numbered marker such as [1]. The marker links to the judgment the passage came from, so you can open it and check."],
  ["Abstention", "If nothing relevant is found, the system says \"Not available in the sources.\" instead of guessing."],
]

const LIMITS = [
  "No evaluation with real users has been done. Retrieval was only checked on a small proxy test, which is not a benchmark.",
  "AI answers can be wrong, incomplete or out of date, even with citations. Always read the cited passage in the judgment.",
  "Only judgments from 2024 are included. Older and newer decisions, High Court and tribunal decisions are not covered.",
  "Some case titles, dates and judges are missing because metadata was extracted automatically.",
  "The \"cited by\" list can be empty because citation links between cases are only partly extracted.",
  "The service runs on a small server. Searches that are new to the system take about 5 seconds, and heavy use is rate limited.",
]

function Section({ title, children }) {
  return (
    <section className="mt-10">
      <h2 className="text-xl font-semibold">{title}</h2>
      <div className="mt-3 space-y-3 text-[15px] leading-relaxed text-foreground/90">{children}</div>
    </section>
  )
}

export default function AboutPage() {
  return (
    <div className="min-h-screen bg-background text-foreground">
      <Navbar />
      <main id="main" className="mx-auto max-w-3xl px-4 py-10">
        <h1 className="text-3xl font-bold tracking-tight">About Kanoon and its data</h1>
        <p className="mt-3 text-muted-foreground">
          Kanoon (AILSE) is a search and question answering tool for Indian Supreme Court judgments. It is a
          student project built to explore retrieval-grounded answers with citations.
        </p>
        <Disclaimer className="mt-4 rounded-lg border border-white/10 bg-white/[0.03] p-3 text-sm" />

        <Section title="Data source">
          <p>
            The collection holds {CASE_COUNT} Supreme Court of India judgments from 2024. The texts were scraped from{" "}
            <a href={LII_URL} target="_blank" rel="noopener noreferrer" className="text-indigo-300 underline">
              the Legal Information Institute of India
            </a>
            . Each judgment is split into passages of about 1,000 characters (46,281 in total) for search.
          </p>
          <p>
            The PDF on each case page is the stored copy of the judgment. It may differ from the official
            version, so check the Supreme Court website before relying on it.
          </p>
        </Section>

        <Section title="How an answer is produced">
          <ol className="space-y-3">
            {STEPS.map(([name, body], i) => (
              <li key={name} className="flex gap-3">
                <span className="mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-indigo-500/20 text-xs font-semibold text-indigo-200">
                  {i + 1}
                </span>
                <p><strong>{name}.</strong> {body}</p>
              </li>
            ))}
          </ol>
        </Section>

        <Section title="Limitations">
          <ul className="list-disc space-y-2 pl-5">
            {LIMITS.map((x) => <li key={x}>{x}</li>)}
          </ul>
        </Section>

        <Section title="Source code">
          <p>
            The code is open on{" "}
            <a href={REPO_URL} target="_blank" rel="noopener noreferrer" className="text-indigo-300 underline">
              GitHub
            </a>
            .
          </p>
        </Section>
      </main>
      <Footer />
    </div>
  )
}
