#!/usr/bin/env python3
"""Check manifest.json runtime requirements against the latest PyPI releases.

Reads the integration manifest, and for every requirement pinned with an exact
``==`` version, looks up the latest stable release on PyPI. Requirements that
are not exactly pinned (ranges, no version) are skipped.

This script only *reports*; it never edits the manifest. It is run by the
``manifest-deps`` workflow, which turns the result into a single GitHub issue.
"""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from packaging.requirements import Requirement
from packaging.utils import canonicalize_name
from packaging.version import InvalidVersion, Version

DEFAULT_MANIFEST = (
    Path(__file__).resolve().parent.parent
    / "custom_components"
    / "openplantbook"
    / "manifest.json"
)
PYPI_URL = "https://pypi.org/pypi/{name}/json"


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    """Refuse to follow redirects, so a request can't leave the guarded URL."""

    def redirect_request(self, *args, **kwargs):
        return None


# Opener that does not follow redirects: combined with the https://pypi.org/
# guard in fetch_latest_pypi, the request can only ever reach PyPI over https.
# Any 3xx surfaces as a non-200 status and is treated as a failed lookup.
_OPENER = urllib.request.build_opener(_NoRedirect)


@dataclass(frozen=True)
class Outdated:
    """A pinned requirement that has a newer release on PyPI."""

    name: str
    current: str
    latest: str


def pinned_requirements(manifest: dict) -> list[tuple[str, str]]:
    """Return ``(name, version)`` for requirements pinned with an exact ``==``.

    Requirements without a single ``==`` pin (ranges, ``>=``, unpinned) are
    skipped — there is no single "current" version to compare against.
    """
    pins: list[tuple[str, str]] = []
    for raw in manifest.get("requirements", []):
        req = Requirement(raw)
        specs = list(req.specifier)
        if len(specs) == 1 and specs[0].operator == "==":
            pins.append((req.name, specs[0].version))
    return pins


def find_outdated(
    pins: list[tuple[str, str]],
    fetch_latest: Callable[[str], str | None],
) -> list[Outdated]:
    """Return the subset of ``pins`` whose latest PyPI release is newer.

    ``fetch_latest`` maps a package name to its latest stable version string,
    or ``None`` when the lookup failed (network error, unknown package, bad
    version). Failures are skipped, never reported as outdated.
    """
    outdated: list[Outdated] = []
    for name, current in pins:
        latest = fetch_latest(name)
        if latest is None:
            continue
        try:
            if Version(latest) > Version(current):
                outdated.append(Outdated(name=name, current=current, latest=latest))
        except InvalidVersion:
            continue
    return outdated


def fetch_latest_pypi(name: str) -> str | None:
    """Return the latest stable version of ``name`` on PyPI, or ``None``.

    Uses PyPI's ``info.version``, which is the latest non-prerelease,
    non-yanked release. Any network/parse error returns ``None`` so a transient
    outage never fails the caller.
    """
    url = PYPI_URL.format(name=canonicalize_name(name))
    # Defensive: the name is canonicalised and the base is a constant, but
    # never let urllib follow anything other than an https PyPI URL (no
    # file://, no other host).
    if not url.startswith("https://pypi.org/"):
        return None
    request = urllib.request.Request(url, method="GET")
    try:
        # URL is a constant https PyPI endpoint with a canonicalised package
        # name from our own manifest, guarded above, and redirects are refused
        # by _OPENER; not user input and can't leave pypi.org.
        # nosemgrep: python.lang.security.audit.dynamic-urllib-use-detected.dynamic-urllib-use-detected
        with _OPENER.open(request, timeout=30) as resp:
            if resp.status != 200:
                return None
            data = json.load(resp)
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, ValueError):
        return None
    version = data.get("info", {}).get("version")
    return version or None


def render_issue_body(outdated: list[Outdated]) -> str:
    """Render the GitHub issue body listing outdated dependencies."""
    lines = [
        "The following `manifest.json` requirements have newer releases on PyPI.",
        "",
        "Update the pin in `custom_components/openplantbook/manifest.json` by "
        "hand after verifying compatibility — this issue is informational and "
        "closes automatically once everything is current.",
        "",
        "| Package | Pinned | Latest |",
        "| --- | --- | --- |",
    ]
    for item in sorted(outdated, key=lambda o: o.name):
        lines.append(f"| `{item.name}` | {item.current} | {item.latest} |")
    return "\n".join(lines) + "\n"


def _set_output(name: str, value: str) -> None:
    """Append ``name=value`` to the GitHub Actions output file, if present."""
    output = os.environ.get("GITHUB_OUTPUT")
    if output:
        with Path(output).open("a", encoding="utf-8") as handle:
            handle.write(f"{name}={value}\n")


def main(argv: list[str] | None = None) -> int:
    """CLI: print a summary, write the issue body, and set ``count`` output."""
    argv = sys.argv[1:] if argv is None else argv
    manifest_path = Path(argv[0]) if argv else DEFAULT_MANIFEST
    body_path = Path(os.environ.get("FRESHNESS_BODY", "manifest_freshness_body.md"))

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    pins = pinned_requirements(manifest)
    outdated = find_outdated(pins, fetch_latest_pypi)

    if outdated:
        body = render_issue_body(outdated)
        body_path.write_text(body, encoding="utf-8")
        print(f"{len(outdated)} outdated requirement(s):")
        for item in outdated:
            print(f"  {item.name}: {item.current} -> {item.latest}")
    else:
        print(f"All {len(pins)} pinned requirement(s) are up to date.")

    _set_output("count", str(len(outdated)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
