# Echoes: Qloo Hackathon Plan

Oct 26, 2026 · @Vansh Rawat

## Deadline check

Confirm the real cutoff and time zone on the Devpost page before relying on any date here. One third-party post lists the hackathon period as 30 September to 30 October 2026, with judging from 2 to 16 November. This plan finishes on Friday, 30 October (IST) and keeps Saturday, 31 October as buffer only.

## The pick: Echoes

Echoes is a reminiscence companion for dementia caregivers that builds culturally grounded sessions from Qloo's taste graph.

A family member enters a person's birth year, hometown and a few things they loved (a singer, a film, a food brand). The agent builds a 20-minute session from their culture and era: songs, films, TV, brands, places and open-ended conversation prompts. After each item the caregiver taps "lit up", "neutral" or "upset", and the agent re-plans the next session.

## Why it should win

- **Cultural blindness is the pitch.** Ask a generic LLM for "music for someone born in 1948" and it defaults to the Western canon. A Punjabi retiree, a Nigerian teacher and a Brazilian farmer need very different sessions, and you can show that gap side by side.
- **Qloo is the differentiator.** The LLM may only use items Qloo returned, each with a Qloo ID, so it can't invent titles.
- **It fits the prompt's hints.** The brief points to age-specific needs and emotional plus practical fit. This is a specific audience with a real problem, and a B2B angle for Jason's investment: memory-care facilities, activity directors and home-care agencies.
- **It avoids crowded lanes.** Other entrants already have a marketing audience-brief tool (Taste-Context Brief), a concert-booking tool (Booker) and an artist-influence matcher (Taste Match), and generic travel, dining and gift recommenders will be everywhere. The senior-nutrition and rare-disease examples were ruled out because they depend on medical data Qloo doesn't have.

## How Qloo powers it

Every step leans on Qloo; the LLM only phrases and sequences what Qloo returns.

| Step | Qloo call | Purpose |
| --- | --- | --- |
| Resolve intake | `/search`, `/v2/tags` | Turn names and genres into Qloo entity and tag IDs |
| Retrieve | `/v2/insights` per domain, favorites as entity signals, hometown as location signal | Taste neighbors in their own culture. Types include artist, book, brand, destination, movie, podcast, tv\_show and place |
| Adapt | Add liked items to the signals; exclude upsetting ones | The agentic loop |
| Explain | Tag insights on the favorites | Writes the conversation prompts ("what ties these together") |
| Guardrail | Score any LLM-added item through Qloo, or drop it | No hallucinated recommendations |

Endpoint names come from public wrappers, because Qloo's own docs blocked my fetch. Verify the exact parameters in the official docs on day 1. One gotcha another entrant reported: Qloo's artist popularity values bunch up near 1, so use a log scale or careful thresholds if you filter on popularity.

## Judging criteria

Echoes has a concrete answer to each of Qloo's four criteria.

| Criterion | How Echoes meets it |
| --- | --- |
| Technological implementation | Multi-domain fan-out, a signal feedback loop, ID-grounded generation, caching and rate limiting |
| Design | A warm, calm, large-type, mobile-first UI with one item at a time and a printable session card, the opposite of a flashy hackathon look |
| Potential impact | Caregivers and care facilities, with a measurable "Qloo vs LLM-only" comparison |
| Quality of idea | Reminiscence therapy built on the taste graph, with safe design choices: open prompts instead of memory quizzes, and an exclude list for trauma-linked eras |

## Roadmap

Four working days to submit, assuming you're solo; Saturday is buffer.

| Day | Focus | Deliverables |
| --- | --- | --- |
| Mon night, Oct 26 | Setup | Get the API key. Create a public repo with an MIT or Apache-2.0 LICENSE. Make 5 test calls. |
| Tue, Oct 27 | Spike and data layer | Morning go/no-go: run 10 seeds across 5 cultures (Hindi film, Nigerian music, Brazilian TV and so on) and proceed if most resolve and the neighbors look plausible for the era. Build the Qloo client with retries and a JSON or SQLite cache. Define the session JSON schema. |
| Wed, Oct 28 | The agent | Intake, then parallel retrieval, then the LLM composer constrained to Qloo IDs. Feedback and re-plan. A deliberately generic LLM-only baseline. 8 test personas across cultures. |
| Thu, Oct 29 | UI and deploy | Intake wizard, session view with feedback taps, and the printable card. A side-by-side "LLM-only vs Qloo" toggle. Deploy by end of day (Vercel, or Render if you go Python) with the key kept server-side, per-IP rate limiting, and one-click pre-cached example personas so the demo works even if the API throttles. |
| Fri, Oct 30 | Proof and submit | Run the persona evaluation and put the results table at the top of the README (a blind score on cultural specificity, era fit and real-entity rate). Write the README (architecture, run instructions, safety note) and the Devpost text. Test the live link in incognito on your phone. Submit by afternoon IST. |

If you fall behind, cut in this order: the printable card, then books, podcasts and brands, then persistent feedback. Don't cut the live URL, the cache fallback or the comparison view.

## Risks and fallback

- **Qloo's coverage of older or regional content may be thin.** The Tuesday spike tests this. If it fails, pivot to "Taste Transplant": someone relocating (say Delhi to Toronto) gets equivalent venues, food and music in the new city. It should reuse an estimated 70% of the same engine.
- **Judges get no demo video.** Make the first screen a one-click example plus the comparison toggle, and lead the description with the with-vs-without-Qloo result.
- **Health-adjacent framing.** Position it as a caregiver aid, not therapy. Use no accounts and keep sessions in the browser only.

## Sources

Found through web search. I read the search excerpts, not the full pages, and Qloo's own docs blocked automated access, so treat endpoint details as unverified.

- [Hackathon dates (LinkedIn post)](https://co.linkedin.com/in/carlamar)
- [Taste-Context Brief](https://glama.ai/mcp/servers/weioai/qloo-audience-brief/tree)
- [Booker](https://glama.ai/mcp/servers/danielhagever/booker/tree)
- [qloo-mcp](https://glama.ai/mcp/servers/NoBanks/qloo-mcp)
- [Qloo insights tool schema](https://app.unpkg.com/@buildwithlayer/qloo-mcp@0.0.4/files/dist/tools.json)
