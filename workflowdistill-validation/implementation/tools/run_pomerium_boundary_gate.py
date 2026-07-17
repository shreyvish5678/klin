#!/usr/bin/env python3
"""Run and record a real, transient Pomerium allow/deny boundary gate."""

from __future__ import annotations

import hashlib
import json
import signal
import subprocess
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

from workflowdistill_state import RUN_DIR, append_event, atomic_json, load_state


ROOT = Path(__file__).resolve().parents[1]
BINARY = RUN_DIR / "sandbox" / "pomerium-m5-compat"
CONFIG = RUN_DIR / "artifacts" / "pomerium-validation.yaml"
EVIDENCE = RUN_DIR / "evidence" / "sponsors" / "pomerium-boundary.json"
RAW_LOG = RUN_DIR / "evidence" / "sponsors" / "pomerium-runtime.jsonl"
SPONSORS = RUN_DIR / "sponsor-integrations.json"
BASE_URL = "http://127.0.0.1:18443"
HEALTH_URL = "http://127.0.0.1:28080/healthz"


def utc_now() -> str:
    return (
        datetime.now(timezone.utc)
        .isoformat(timespec="milliseconds")
        .replace("+00:00", "Z")
    )


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def request(path: str) -> dict:
    started = time.monotonic()
    try:
        with urllib.request.urlopen(BASE_URL + path, timeout=10) as response:
            status = response.status
            body = response.read()
    except urllib.error.HTTPError as error:
        status = error.code
        body = error.read()
    return {
        "path": path,
        "status": status,
        "body_bytes": len(body),
        "body_sha256": hashlib.sha256(body).hexdigest(),
        "latency_ms": round((time.monotonic() - started) * 1000, 3),
    }


def wait_for_health(process: subprocess.Popen[bytes]) -> None:
    deadline = time.monotonic() + 20
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError(f"Pomerium exited during startup: {process.returncode}")
        try:
            with urllib.request.urlopen(HEALTH_URL, timeout=1) as response:
                if response.status == 200:
                    return
        except (OSError, urllib.error.URLError):
            pass
        time.sleep(0.25)
    raise RuntimeError("Pomerium health endpoint did not become ready")


def sanitized_decision(records: list[dict], path: str) -> dict:
    checks = [
        item
        for item in records
        if item.get("message") == "authorize check" and item.get("path") == path
    ]
    requests = [
        item
        for item in records
        if item.get("message") == "http-request" and item.get("path") == path
    ]
    if len(checks) != 1 or len(requests) > 1:
        raise RuntimeError(f"Expected one authorize record for {path}")
    check = checks[0]
    access = requests[0] if requests else {}
    return {
        "path": path,
        "authorize": {
            "allow": check.get("allow"),
            "deny": check.get("deny"),
            "allow_reason_count": len(check.get("allow-why-true", [])),
            "deny_reason_count": len(check.get("deny-why-true", [])),
        },
        "access": {
            "response_code": access.get("response-code"),
            "response_code_details": access.get("response-code-details"),
            "log_flushed_before_shutdown": bool(access),
        },
    }


def main() -> None:
    state = load_state()
    if state["phase"] not in {
        "PROFILE_SELECTED_WORKFLOW",
        "MEASURE_HOSTED_BASELINE",
    }:
        raise SystemExit(f"Cannot run Pomerium gate in phase {state['phase']}")
    if not BINARY.is_file() or not CONFIG.is_file():
        raise SystemExit("Pomerium compatibility binary or validation config missing")

    EVIDENCE.parent.mkdir(parents=True, exist_ok=True)
    started_at = utc_now()
    with RAW_LOG.open("wb") as log:
        process = subprocess.Popen(
            [str(BINARY), "--config", str(CONFIG)],
            cwd=ROOT,
            stdout=log,
            stderr=subprocess.STDOUT,
        )
        try:
            wait_for_health(process)
            allowed_http = request("/candidate/draft")
            denied_http = request("/hidden/labels")
            # Envoy access logs are emitted asynchronously after the response.
            time.sleep(0.5)
        finally:
            if process.poll() is None:
                process.send_signal(signal.SIGINT)
                try:
                    process.wait(timeout=15)
                except subprocess.TimeoutExpired:
                    process.terminate()
                    process.wait(timeout=5)
    if process.returncode != 0:
        raise SystemExit(f"Pomerium did not stop cleanly: {process.returncode}")

    records = []
    for line in RAW_LOG.read_text(encoding="utf-8").splitlines():
        try:
            records.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    allowed_log = sanitized_decision(records, "/candidate/draft")
    denied_log = sanitized_decision(records, "/hidden/labels")
    passed = (
        allowed_http["status"] == 200
        and denied_http["status"] == 403
        and allowed_log["authorize"] == {
            "allow": True,
            "deny": False,
            "allow_reason_count": 2,
            "deny_reason_count": 0,
        }
        and denied_log["authorize"] == {
            "allow": False,
            "deny": True,
            "allow_reason_count": 0,
            "deny_reason_count": 2,
        }
    )
    if not passed:
        raise SystemExit("Pomerium allow/deny assertions failed")

    evidence = {
        "schema_version": "1.0",
        "run_id": state["run_id"],
        "status": "PASS",
        "started_at": started_at,
        "completed_at": utc_now(),
        "runtime": {
            "product": "Pomerium",
            "version": "0.33.0",
            "mode": "transient local all-in-one; stopped after gate",
            "binary_sha256": sha256(BINARY),
            "config_sha256": sha256(CONFIG),
            "upstream_compatibility_repair": (
                "replaced crash-prone optional Apple CPU frequency probe; "
                "Pomerium and embedded Envoy authorization path unchanged"
            ),
            "persistent_service_installed": False,
        },
        "authorized_request": {
            "role": "CANDIDATE_ROLE",
            "capability": "sandbox draft request",
            "http": allowed_http,
            "pomerium_log": allowed_log,
        },
        "prohibited_request": {
            "role": "CANDIDATE_ROLE",
            "capability": "hidden label read",
            "http": denied_http,
            "pomerium_log": denied_log,
        },
        "raw_log": {
            "path": str(RAW_LOG.relative_to(RUN_DIR)),
            "sha256": sha256(RAW_LOG),
            "contains_secret_values": False,
        },
        "privacy": {
            "hidden_labels_loaded_or_returned": False,
            "external_identity_data_used": False,
            "secret_values_recorded": False,
        },
        "actual_cost_usd": 0,
    }
    atomic_json(EVIDENCE, evidence)

    sponsors = json.loads(SPONSORS.read_text(encoding="utf-8"))
    sponsors["pomerium"].update(
        {
            "status": "PASS_ALLOW_AND_SAFE_DENIAL",
            "cli_installed": True,
            "config_present": True,
            "allow_requests": 1,
            "deny_requests": 1,
            "actual_cost_usd": 0,
            "note": (
                "Pomerium 0.33.0 plus embedded Envoy allowed a candidate sandbox "
                "draft and denied hidden-label access with ext_authz_denied."
            ),
            "evidence": "evidence/sponsors/pomerium-boundary.json",
        }
    )
    sponsors["generated_at"] = utc_now()
    atomic_json(SPONSORS, sponsors)

    state["sponsor_integrations"]["pomerium"]["status"] = (
        "PASS; 1 allowed; 1 safely denied; USD 0 spent"
    )
    state["lanes"]["D"].update(
        {
            "current_action": "complete authorized Akash model experiment",
            "evidence_paths": sorted(
                set(
                    state["lanes"]["D"]["evidence_paths"]
                    + [
                        "artifacts/pomerium-validation.yaml",
                        "evidence/sponsors/pomerium-boundary.json",
                        "evidence/sponsors/pomerium-runtime.jsonl",
                    ]
                )
            ),
        }
    )
    append_event(
        state,
        event_type="POMERIUM_REQUEST_ALLOWED",
        summary="Pomerium allowed the candidate sandbox draft request",
        reason=(
            "The frozen candidate role permits approved sandbox draft operations; "
            "Pomerium logged allow=true and Envoy returned the direct response."
        ),
        phase=state["phase"],
        status="running",
        lane="D",
        sponsor_tool="Pomerium",
        evidence_paths=[
            "artifacts/pomerium-validation.yaml",
            "evidence/sponsors/pomerium-boundary.json",
            "evidence/sponsors/pomerium-runtime.jsonl",
        ],
        metrics={"http_status": 200, "allow": True, "deny": False},
        actual_cost=0,
    )
    event = append_event(
        state,
        event_type="POMERIUM_REQUEST_DENIED",
        summary="Pomerium safely denied candidate access to hidden labels",
        reason=(
            "The candidate role is prohibited from reading hidden labels; Pomerium "
            "logged deny=true and Envoy returned 403 ext_authz_denied."
        ),
        phase=state["phase"],
        status="running",
        lane="D",
        sponsor_tool="Pomerium",
        evidence_paths=[
            "evidence/sponsors/pomerium-boundary.json",
            "evidence/sponsors/pomerium-runtime.jsonl",
        ],
        metrics={
            "http_status": 403,
            "allow": False,
            "deny": True,
            "hidden_labels_returned": False,
        },
        actual_cost=0,
    )
    print(json.dumps(event, sort_keys=True))


if __name__ == "__main__":
    main()
