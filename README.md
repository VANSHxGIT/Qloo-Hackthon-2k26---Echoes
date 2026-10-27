# Echoes

A reminiscence companion for people who care for someone with memory loss. Give it a
birth year, a hometown and a few things the person loved, and it builds a short
session of songs, films, TV, brands and places from *their* culture and era, then
adapts the next session from what the caregiver says lit them up.

Built for the [Qloo Agentic Hackathon](https://qloo.devpost.com/).

> **Status: scaffold.** Working today: the Qloo client, an offline mock server, the
> day-1 coverage spike and tests. Not built yet: the agent, the UI, the deployment.
> Nothing below under "How it will work" exists yet.

> **Qloo calls are unverified.** Endpoint and parameter names were written from public
> documentation seen through community wrappers, not tested against the live API. Run
> the spike (below) as soon as you have a key and fix anything that returns 4xx.

## Why Qloo

A generic LLM asked for "music for someone born in 1948" defaults to the Western
canon. A retiree in Delhi, a teacher in Lagos and a farmer in Brazil need very
different sessions. Echoes only recommends entities that Qloo's taste graph returns
for the person's seeds and hometown, each with a Qloo ID, so the LLM can phrase and
sequence items but cannot invent them. The comparison view (LLM-only versus
Qloo-grounded) is the core demo.

## How it will work (planned)

1. **Intake.** Birth year, hometown, a few favourites. `/search` and `/v2/tags` turn
   names and genres into Qloo entity and tag IDs.
2. **Retrieve.** `/v2/insights` per domain (artist, movie, tv_show, brand, place) with
   the favourites as entity signals and the hometown as the location signal.
3. **Compose.** The LLM writes a 20-minute session from Qloo items only; any item it
   adds is checked against Qloo or dropped.
4. **Adapt.** The caregiver taps "lit up", "neutral" or "upset" per item. Liked items
   join the signals; upsetting ones go into `filter.exclude.entities`.

## Quickstart

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env          # then put your key in QLOO_API_KEY
python scripts/spike.py       # day-1 coverage check against the real API
```

`QLOO_API_KEY` is the secret from Qloo's hackathon developer guide
("Getting your API key"). `https://hackathon.api.qloo.com` is the base URL, already
the default in `QLOO_BASE_URL`; it is not a key.

No key yet? `python scripts/spike.py --mock` runs the whole pipeline against a local
server that returns fabricated `[MOCK]` data, and labels its report accordingly.

```bash
python -m pytest              # 34 tests, no network or key needed
```

## The day-1 spike

`scripts/spike.py` runs 10 older, regional seeds (2 each for Hindi/North Indian,
Nigerian, Brazilian, Mexican and Japanese culture) through `/search`, then asks
`/v2/insights` for neighbours in each domain. It writes `data/spike_report.md` and
`.json` (git-ignored).

- **Coverage verdict (GO / MAYBE / NO-GO)** counts how many seeds resolve and return
  at least 3 results in at least 2 domains. The thresholds are this project's own
  heuristic, not Qloo's.
- **Plausibility is yours to judge.** Read the "Neighbours to read" section and ask
  whether the results fit that culture and era.
- **API errors** lists every failed call with its status code, so a wrong parameter
  name is not mistaken for thin coverage.

If coverage fails, the fallback is "Taste Transplant": recommend equivalent venues,
food and music for someone relocating to a new city, reusing the same engine.

## Layout

```
src/echoes/qloo.py         Qloo client: auth, retries with backoff, SQLite cache
src/echoes/spike.py        the 10 seeds, the runner, the verdict and the report
src/echoes/mock_server.py  offline stand-in returning fabricated [MOCK] data
scripts/spike.py           command-line entry point for the spike
tests/                     pytest suite (runs against the mock)
```

## Submission checklist

Qloo requires all of these; none is done yet.

- [ ] Live demo URL, hosted externally (local-only does not qualify)
- [ ] Public repository with all source, assets and run instructions
- [ ] Text description: what it does and what makes it Qloo-powered
- [ ] Open-source license visible in the repo's About section (`LICENSE` is MIT)
- [ ] Confirm the exact deadline and time zone on the Devpost page. One third-party post
      lists the build period as 30 Sep to 30 Oct 2026, so treat Oct 30 as the real cutoff
      and Oct 31 as buffer only.

## Roadmap

- [ ] **Tue 27 Oct:** get the key, run the spike, make the go/no-go call
- [ ] **Wed 28 Oct:** agent (intake, retrieve, compose, adapt) and the LLM-only baseline
- [ ] **Thu 29 Oct:** UI, comparison view, deploy with the key kept server-side and per-IP rate limiting
- [ ] **Fri 30 Oct:** persona evaluation table, README and Devpost text, submit

## Safety and scope

Echoes is a caregiver aid, not therapy. Sessions use open prompts rather than memory
quizzes, and anything marked "upset" is excluded from later sessions. No accounts;
session state stays in the browser. Never commit `.env`.

## License

MIT. See [LICENSE](LICENSE).
