"""Validate the GitHub maintenance registry and its pre-change PR gate.

Only standard-library dependencies. This check is advisory until the GitHub
branch ruleset makes the "maintenance-guard" job a required status check.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HISTORY = ".github/maintenance/maintenance-history.json"
STATUS = ".github/maintenance/maintenance-status.json"
KINDS = {"routine", "extraordinary", "structural"}
EVENT_STATES = {"planned", "in_progress", "completed", "cancelled"}
SERVICE_STATES = {"unknown", "operational", "maintenance", "degraded", "unavailable"}
ID_PATTERN = re.compile(r"^MAINT-[0-9]{8}-[0-9]{3,}$")
UTC_PATTERN = re.compile(r"^\\d{4}-\\d{2}-\\d{2}T\\d{2}:\\d{2}:\\d{2}Z$")
RISK_PATHS = (
    ".github/workflows/",
    "services/bug-gateway/",
    "release-approvals/",
)
RISK_FILES = {"tools/release.py", "version.py", "version_info.txt"}


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def utc(value: object, field: str, *, nullable: bool = False) -> None:
    if value is None and nullable:
        return
    require(isinstance(value, str) and UTC_PATTERN.fullmatch(value) is not None,
            f"{field}: expected UTC ISO-8601 timestamp ending in Z")
    try:
        datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"{field}: invalid date") from exc


def strings(value: object, field: str, *, required: bool = False) -> None:
    require(isinstance(value, list) and all(isinstance(x, str) and x.strip() for x in value),
            f"{field}: expected list of nonblank strings")
    if required:
        require(bool(value), f"{field}: at least one value required")


def validate(history: dict, status: dict) -> None:
    require(isinstance(history, dict) and history.get("schema_version") == 1,
            "history: unsupported schema_version")
    require(isinstance(status, dict) and status.get("schema_version") == 1,
            "status: unsupported schema_version")
    events = history.get("events")
    require(isinstance(events, list), "history.events must be an array")
    known = set()
    for event in events:
        require(isinstance(event, dict), "history.events: expected object")
        identifier = event.get("id")
        require(isinstance(identifier, str) and ID_PATTERN.fullmatch(identifier) is not None,
                "history.events: invalid maintenance ID")
        require(identifier not in known, f"duplicate maintenance ID: {identifier}")
        known.add(identifier)
        require(event.get("type") in KINDS, f"{identifier}: invalid type")
        require(event.get("status") in EVENT_STATES, f"{identifier}: invalid status")
        for field in ("registered_at", "started_at", "ended_at",
                      "planned_start_at", "planned_end_at"):
            utc(event.get(field), f"{identifier}.{field}", nullable=field != "registered_at")
        for field in ("components", "affected_endpoints", "planned_steps", "expected_errors",
                      "related_workflows", "executed_steps", "commits", "observed_errors", "evidence"):
            strings(event.get(field, []), f"{identifier}.{field}",
                    required=field in ("components", "planned_steps"))
        for field in ("description", "expected_impact", "actor", "rollback"):
            require(isinstance(event.get(field), str) and bool(event[field].strip()),
                    f"{identifier}.{field}: required")
        for field in ("related_prs", "related_issues"):
            value = event.get(field, [])
            require(isinstance(value, list) and
                    all(isinstance(x, int) and not isinstance(x, bool) and x > 0 for x in value),
                    f"{identifier}.{field}: expected positive issue/PR numbers")
        if event.get("emergency_retrospective", False):
            require(isinstance(event.get("emergency_reason"), str) and
                    bool(event["emergency_reason"].strip()),
                    f"{identifier}: emergency reason required")
        start, end = event.get("started_at"), event.get("ended_at")
        if start and end:
            require(end >= start, f"{identifier}: ended_at precedes started_at")
        if event["status"] == "in_progress":
            require(start is not None, f"{identifier}: missing actual start")
        if event["status"] == "completed":
            require(start is not None and end is not None and bool(event.get("evidence")),
                    f"{identifier}: completed event needs times and verification evidence")
        if event["status"] == "planned":
            require(start is None and end is None, f"{identifier}: planned event has actual times")

    utc(status.get("updated_at"), "status.updated_at", nullable=True)
    services = status.get("services")
    require(isinstance(services, dict) and bool(services), "status.services: expected nonempty object")
    for name, info in services.items():
        require(isinstance(name, str) and name and isinstance(info, dict),
                "status.services: invalid service")
        state = info.get("status")
        require(state in SERVICE_STATES, f"{name}: invalid service status")
        event_id = info.get("event_id")
        require(event_id is None or event_id in known, f"{name}: unknown maintenance event")
        utc(info.get("planned_end_at"), f"{name}.planned_end_at", nullable=True)
        if state == "maintenance":
            require(event_id is not None, f"{name}: maintenance needs event_id")
        if state == "operational":
            require(status["updated_at"] is not None,
                    f"{name}: cannot assert operational without an observation timestamp")
        if status["updated_at"] is None:
            require(state == "unknown", f"{name}: no observation; service status must be unknown")


def git(*args: str) -> str:
    return subprocess.check_output(["git", *args], cwd=ROOT, text=True, stderr=subprocess.DEVNULL).strip()


def at_commit(commit: str, path: str) -> dict:
    try:
        return json.loads(git("show", f"{commit}:{path}"))
    except (subprocess.CalledProcessError, json.JSONDecodeError):
        return {"schema_version": 1, "events": []}


def risky(path: str) -> bool:
    return path in RISK_FILES or any(path.startswith(prefix) for prefix in RISK_PATHS)


def check_pr(base: str, pr: int) -> None:
    # Use the merge base: the target branch can have advanced since the PR branched.
    merge_base = git("merge-base", base, "HEAD")
    baseline = {e["id"] for e in at_commit(merge_base, HISTORY).get("events", [])}
    commits = git("rev-list", "--reverse", "--topo-order", f"{merge_base}..HEAD").splitlines()
    for commit in commits:
        files = git("diff-tree", "--root", "--no-commit-id", "--name-only", "-r", commit).splitlines()
        affected = [path for path in files if risky(path)]
        if not affected:
            continue
        # Only events already committed in a PRIOR revision qualify; never
        # allow an event added in the disruptive commit or backfilled later.
        previous = git("rev-parse", f"{commit}^")
        prior_events = at_commit(previous, HISTORY).get("events", [])
        matches = [
            e for e in prior_events
            if e.get("id") not in baseline
            and pr in e.get("related_prs", [])
            and e.get("status") in ("planned", "in_progress")
            and "rollback" in e and "expected_impact" in e
            and (("github-actions" in e.get("components", []))
                 if any(p.startswith(".github/workflows/") for p in affected)
                 else True)
        ]
        require(bool(matches),
                f"{commit[:12]} changed {', '.join(affected)} without a PREVIOUS-COMMIT "
                f"maintenance record for PR #{pr}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("validate", "check-pr"))
    parser.add_argument("--base")
    parser.add_argument("--pr", type=int)
    args = parser.parse_args()
    try:
        history = json.loads((ROOT / HISTORY).read_text(encoding="utf-8"))
        status = json.loads((ROOT / STATUS).read_text(encoding="utf-8"))
        validate(history, status)
        if args.action == "check-pr":
            require(bool(args.base) and bool(args.pr), "check-pr needs --base and --pr")
            check_pr(args.base, args.pr)
    except (ValueError, OSError, subprocess.CalledProcessError, json.JSONDecodeError) as exc:
        print(f"Maintenance guard FAILED: {exc}", file=sys.stderr)
        return 1
    print("Maintenance guard passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
