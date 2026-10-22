"""Simulate a registration rush: many students hit "Register" at the same instant.

Proves the seat counter can't be overbooked under concurrency.
Uses only the Python standard library, so it runs anywhere.

    python3 scripts/concurrency_test.py --url http://localhost:8080 \
        --event devops-bootcamp --students 50
"""

import argparse
import json
import sys
import urllib.error
import urllib.request
from collections import Counter
from concurrent.futures import ThreadPoolExecutor


def register(base_url: str, event_id: str, n: int) -> int:
    body = json.dumps({"name": f"Student {n}", "email": f"rush{n}@example.edu", "student_id": f"RUSH{n:04d}"})
    req = urllib.request.Request(  # noqa: S310 (URL comes from CLI arg)
        f"{base_url}/api/events/{event_id}/registrations",
        data=body.encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:  # noqa: S310 (URL comes from CLI arg)
            return resp.status
    except urllib.error.HTTPError as err:
        return err.code


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="http://localhost:8080")
    parser.add_argument("--event", default="devops-bootcamp")
    parser.add_argument("--students", type=int, default=50)
    args = parser.parse_args()

    with urllib.request.urlopen(f"{args.url}/api/events/{args.event}") as resp:  # noqa: S310
        seats = json.load(resp)["seats_left"]

    with ThreadPoolExecutor(max_workers=args.students) as pool:
        codes = Counter(pool.map(lambda n: register(args.url, args.event, n), range(args.students)))

    with urllib.request.urlopen(f"{args.url}/api/events/{args.event}") as resp:  # noqa: S310
        after = json.load(resp)

    print(f"seats available before: {seats}")
    print(f"responses: {dict(codes)}")
    print(f"registered_count={after['registered_count']} capacity={after['capacity']}")
    ok = codes[201] == min(seats, args.students) and after["registered_count"] <= after["capacity"]
    print("PASS: no overbooking" if ok else "FAIL: seat count is wrong")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
