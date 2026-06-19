"""Unit tests for the manifest freshness checker (pure logic)."""

from __future__ import annotations

import sys
from pathlib import Path

# The checker lives in scripts/, which is not a package on the path.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from check_manifest_freshness import (  # noqa: E402
    Outdated,
    find_outdated,
    pinned_requirements,
    render_issue_body,
)


def test_pinned_requirements_keeps_only_exact_pins():
    """Only requirements with a single == specifier are returned."""
    manifest = {
        "requirements": [
            "openplantbook-sdk==0.6.1",
            "json-timeseries==0.1.7",
            "async-timeout>=4.0.2",  # range -> skipped
            "some-pkg",  # unpinned -> skipped
            "other>=1.0,<2.0",  # multi-spec -> skipped
        ]
    }
    assert pinned_requirements(manifest) == [
        ("openplantbook-sdk", "0.6.1"),
        ("json-timeseries", "0.1.7"),
    ]


def test_pinned_requirements_empty_when_no_requirements():
    """A manifest with no requirements yields no pins."""
    assert pinned_requirements({}) == []


def test_find_outdated_reports_newer_releases():
    """A package whose latest release is newer than the pin is flagged."""
    pins = [("openplantbook-sdk", "0.6.1")]
    outdated = find_outdated(pins, lambda name: "0.7.0")
    assert outdated == [Outdated("openplantbook-sdk", "0.6.1", "0.7.0")]


def test_find_outdated_ignores_up_to_date_and_older():
    """Equal or older latest versions are not reported."""
    pins = [("a", "1.2.3"), ("b", "2.0.0")]
    latest = {"a": "1.2.3", "b": "1.9.9"}
    assert find_outdated(pins, latest.get) == []


def test_find_outdated_skips_lookup_failures():
    """A None from the fetcher (network error / unknown) is skipped, not flagged."""
    pins = [("a", "1.0.0"), ("b", "1.0.0")]
    latest = {"a": None, "b": "2.0.0"}
    assert find_outdated(pins, latest.get) == [Outdated("b", "1.0.0", "2.0.0")]


def test_find_outdated_skips_unparseable_latest():
    """A non-PEP440 latest string is skipped rather than raising."""
    pins = [("a", "1.0.0")]
    assert find_outdated(pins, lambda name: "not-a-version") == []


def test_render_issue_body_lists_packages_sorted():
    """The issue body renders a Markdown table sorted by package name."""
    body = render_issue_body(
        [
            Outdated("zlib-pkg", "1.0", "1.1"),
            Outdated("alpha-pkg", "2.0", "3.0"),
        ]
    )
    assert "| `alpha-pkg` | 2.0 | 3.0 |" in body
    assert "| `zlib-pkg` | 1.0 | 1.1 |" in body
    assert body.index("alpha-pkg") < body.index("zlib-pkg")
