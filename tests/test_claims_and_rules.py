"""What the README and the rules say must match what was measured.

The audit (2026-10) found the README's "average 65%" was the token-weighted
aggregate, "zero information lost" was never measured, and the core rules
deleted nulls, counts and wrappers on every response. These tests keep each of
those from returning.
"""

import re

import pytest

from joutputmunch.bench.models import reduction_pct


def _read(repo, rel):
    return (repo / rel).read_text(encoding="utf-8")


def _published_rows(repo):
    rows = []
    for line in _read(repo, "benchmarks/results.md").splitlines():
        m = re.match(r"\|\s*([^|*]+?)\s*\|\s*([\d,]+)\s*\|\s*([\d,]+)\s*\|\s*\*\*-([\d.]+)%\*\*", line)
        if m:
            rows.append((m[1], int(m[2].replace(",", "")), int(m[3].replace(",", "")), float(m[4])))
    return rows


def test_every_published_percentage_follows_from_its_counts(repo):
    rows = _published_rows(repo)
    assert len(rows) == 5
    for label, base, munch, pct in rows:
        assert reduction_pct(base, munch) == pct, label
    total = re.search(r"\*\*Total\*\* \| \*\*([\d,]+)\*\* \| \*\*([\d,]+)\*\* \| \*\*-([\d.]+)%\*\*", _read(repo, "benchmarks/results.md"))
    base, munch = int(total[1].replace(",", "")), int(total[2].replace(",", "")),
    assert (base, munch) == (sum(r[1] for r in rows), sum(r[2] for r in rows))
    assert reduction_pct(base, munch) == float(total[3])


def test_the_readme_quotes_the_aggregate_as_an_aggregate(repo):
    readme = _read(repo, "README.md")
    assert "65.2% aggregate" in readme
    assert "4,520" in readme and "1,571" in readme


@pytest.mark.parametrize("rel", ["README.md", "benchmarks/results.md", "rules/core.md"])
@pytest.mark.parametrize(
    "phrase",
    [r"average\s+65", r"65(\.2)?%\s+average", r"zero information", r"no loss of information", r"25-40%", r"same answers"],
)
def test_no_unmeasured_claim_returns(repo, rel, phrase):
    assert not re.search(phrase, _read(repo, rel), re.IGNORECASE), (rel, phrase)


def test_the_safe_rules_change_no_schema(repo):
    core = _read(repo, "rules/core.md") + _read(repo, "rules/mcp.md")
    for unconditional in [
        "Omit keys whose value is null",
        "Never include a count field alongside the array",
        "Do not wrap data in single-key containers",
        "Strip null values and empty collections before serializing.",
        "Do not include a `success: true`",
    ]:
        assert unconditional not in core, unconditional
    assert "compress redundancy, never required information" in core
    assert "rules/profiles/aggressive.md" in core


def test_the_aggressive_rules_are_opt_in_and_name_their_condition(repo):
    aggressive = _read(repo, "rules/profiles/aggressive.md")
    assert "opt-in" in aggressive
    assert "only when you own the output contract" in aggressive
    assert "Omit keys whose value is `null`" in aggressive


def test_the_guides_do_not_copy_the_aggressive_rules_into_the_default(repo):
    for guide in sorted((repo / "guides").glob("*.md")):
        text = guide.read_text(encoding="utf-8")
        assert not re.search(r"no nulls|Omit empty fields, null values", text), guide.name


def test_the_rules_stay_zero_install(repo):
    """Rule consumers copy Markdown; nothing under rules/ may need code."""
    files = [p for p in (repo / "rules").rglob("*") if p.is_file()]
    assert files and all(p.suffix == ".md" for p in files), files
