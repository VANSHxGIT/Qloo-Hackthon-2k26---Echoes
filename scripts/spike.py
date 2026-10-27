#!/usr/bin/env python3
"""Run the day-1 Qloo spike and write data/spike_report.md and .json.

    python scripts/spike.py              # real API: needs QLOO_API_KEY (see .env.example)
    python scripts/spike.py --mock       # offline dry run against the fabricated [MOCK] server
    python scripts/spike.py --domains artist,movie --seeds 4 --delay 0.5
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from echoes.mock_server import start_mock  # noqa: E402
from echoes.qloo import QlooClient, QlooError, load_env  # noqa: E402
from echoes.spike import (  # noqa: E402
    DEFAULT_DOMAINS,
    DOMAINS,
    SEEDS,
    is_mock_url,
    render_report,
    run_spike,
    to_json,
    verdict,
)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--mock", action="store_true", help="use the local fabricated [MOCK] server")
    ap.add_argument("--domains", default=",".join(DEFAULT_DOMAINS), help=f"comma list from: {', '.join(DOMAINS)}")
    ap.add_argument("--seeds", type=int, default=len(SEEDS), help="run only the first N seeds")
    ap.add_argument("--take", type=int, default=8, help="results requested per insights call")
    ap.add_argument("--delay", type=float, default=0.2, help="seconds to pause between calls")
    ap.add_argument("--no-cache", action="store_true", help="do not read or write .cache/qloo.sqlite")
    ap.add_argument("--out", default=str(ROOT / "data" / "spike_report"), help="output path without extension")
    args = ap.parse_args()

    domains = [d.strip() for d in args.domains.split(",") if d.strip()]
    bad = [d for d in domains if d not in DOMAINS]
    if bad:
        print(f"Unknown domain(s): {bad}. Choose from: {', '.join(DOMAINS)}", file=sys.stderr)
        return 2

    server = None
    try:
        if args.mock:
            server, base_url = start_mock(0)
            client = QlooClient(api_key="mock", base_url=base_url, cache_path=None)
        else:
            load_env(str(ROOT / ".env"))
            client = QlooClient(cache_path=None if args.no_cache else str(ROOT / ".cache" / "qloo.sqlite"))
            base_url = client.base_url
    except QlooError as e:
        print(f"Setup problem: {e}", file=sys.stderr)
        return 2

    def progress(i: int, n: int, seed) -> None:
        print(f"[{i}/{n}] {seed.culture}: {seed.name}", file=sys.stderr)

    try:
        results = run_spike(
            client,
            seeds=SEEDS[: args.seeds],
            domains=domains,
            take=args.take,
            delay=0.0 if args.mock else args.delay,
            progress=progress,
        )
    finally:
        if server:
            server.shutdown()

    mock = args.mock or is_mock_url(base_url)
    report = render_report(results, base_url=base_url, is_mock=mock, domains=domains, stats=client.stats)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.with_suffix(".md").write_text(report, encoding="utf-8")
    out.with_suffix(".json").write_text(json.dumps(to_json(results), indent=2, ensure_ascii=False), encoding="utf-8")

    print(report)
    print(f"\nWrote {out.with_suffix('.md')} and {out.with_suffix('.json')}", file=sys.stderr)
    if not mock:
        print(f"Verdict: {verdict(results)[0]}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
