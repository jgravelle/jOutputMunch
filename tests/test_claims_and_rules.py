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


def _user_facing(repo):
    """Every Markdown file a reader or a rule consumer sees, except the opt-in profile."""
    files = [repo / "README.md", *sorted((repo / "benchmarks").glob("*.md"))]
    files += sorted((repo / "rules").glob("*.md")) + sorted((repo / "guides").glob("*.md"))
    return files


UNMEASURED = [
    r"average\s+(of\s+)?\d",
    r"\d+(\.\d+)?%\s+(on\s+)?average",
    r"zero information",
    r"no loss of information",
    r"information (is |was )?(lost|preserved)",
    r"retains all",
    r"(keep|keeps|retain|retains) all (its|their|the) (information|knowledge)",
    r"same answers?\b",
    r"25-40%",
]


@pytest.mark.parametrize("phrase", UNMEASURED)
def test_no_unmeasured_claim_returns(repo, phrase):
    for f in _user_facing(repo):
        assert not re.search(phrase, f.read_text(encoding="utf-8"), re.IGNORECASE), (f.name, phrase)


def _blocks(text):
    """Bullets and paragraphs: a rule and its condition sit in the same block."""
    blocks, cur = [], []
    for line in text.splitlines():
        if not line.strip() or line.lstrip().startswith("- "):
            if cur:
                blocks.append(" ".join(cur))
            cur = [line.strip()] if line.strip() else []
        else:
            cur.append(line.strip())
    if cur:
        blocks.append(" ".join(cur))
    return blocks


SHAPE_CHANGE = re.compile(
    r"\b(omit|omitting|strip|stripping|drop|dropping|remove|no)\b.*"
    r"(\b(nulls?|empty|empties|counts?|wrappers?|metadata|envelopes?|success)\b|_meta)",
    re.IGNORECASE,
)
# A condition is a phrase that limits the rule, not a word that merely appears near it:
# "to keep the schema small" names a schema and limits nothing.
CONDITION = re.compile(
    r"\bunless\b|\bonly (when|for)\b|\byou own\b|\bopt-in\b|aggressive\.md"
    r"|\b(schema|contract|protocol|caller)s? (requires?|defines?|says)\b",
    re.IGNORECASE,
)


def test_the_safe_set_never_changes_shape_without_a_condition(repo):
    """A rule that drops nulls, empties, counts or wrappers must say when, in the same bullet."""
    safe = sorted((repo / "rules").glob("*.md")) + sorted((repo / "guides").glob("*.md"))
    for f in safe:
        for block in _blocks(f.read_text(encoding="utf-8")):
            if SHAPE_CHANGE.search(block):
                assert CONDITION.search(block), (f.name, block)


def test_the_old_unconditional_rules_are_not_in_the_safe_set(repo):
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
