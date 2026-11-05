"""Generate a local Markdown report from deterministic assessment results."""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from compliance.engine import ComplianceEngine
from compliance.models import Assessment


def _display(value: Any) -> str:
    if value is None:
        return "N/A"
    return str(value).replace("|", "\\|").replace("\n", " ")


def render_markdown(assessment: Assessment) -> str:
    title = "Synthetic inverter compliance assessment" if assessment.synthetic else "Observed inverter compliance assessment"
    warning = (
        "> **SYNTHETIC DATA - NOT A REAL INVERTER ASSESSMENT.**"
        if assessment.synthetic
        else "> **READ-ONLY OBSERVATION. Human review is required before any compliance decision.**"
    )
    lines = [
        f"# {title}",
        "",
        warning,
        "",
        f"- Dataset: `{assessment.dataset_id}`",
        f"- Region: `{assessment.region}`",
        f"- Inspected interface: `{assessment.interface}`",
        "- Rules are source-checked but require independent human validation before operational use.",
        "",
        "## Summary",
        "",
        "| Outcome | Count |",
        "|---|---:|",
    ]
    lines.extend(f"| {status} | {count} |" for status, count in sorted(assessment.counts.items()))
    lines.extend(
        [
            "",
            "## Findings",
            "",
            "| Rule | Clause | Parameter | Observed | Outcome | Evidence | Explanation |",
            "|---|---|---|---|---|---|---|",
        ]
    )
    for result in assessment.results:
        lines.append(
            "| "
            + " | ".join(
                _display(item)
                for item in (
                    result.rule_id,
                    result.clause,
                    result.parameter,
                    result.observed_value,
                    result.status.value,
                    json.dumps(result.evidence, sort_keys=True) if result.evidence else "N/A",
                    result.message,
                )
            )
            + " |"
        )
    lines.extend(
        [
            "",
            "## Interpretation limits",
            "",
            "An unavailable app field means only that the inspected interface did not expose it. It does not show that the inverter lacks the capability. Requirements assigned to type testing cannot be concluded from app settings. Approved variations require authentic distributor/operator evidence in a future controlled workflow; this demonstration uses a clearly synthetic reference.",
            "",
        ]
    )
    return "\n".join(lines)


def write_reports(assessment: Assessment, output_directory: Path, stem: str | None = None) -> tuple[Path, Path]:
    """Write timestamped Markdown and machine-readable JSON reports locally."""
    output_directory.mkdir(parents=True, exist_ok=True)
    safe_stem = stem or f"assessment-{datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ')}"
    markdown_path = output_directory / f"{safe_stem}.md"
    json_path = output_directory / f"{safe_stem}.json"
    markdown_path.write_text(render_markdown(assessment), encoding="utf-8")
    json_path.write_text(json.dumps(assessment.to_dict(), indent=2), encoding="utf-8")
    return markdown_path, json_path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("configuration", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--rules", type=Path, default=Path("standards/standards_rules.json"))
    parser.add_argument("--catalog", type=Path, default=Path("standards/parameter_catalog.json"))
    args = parser.parse_args()
    assessment = ComplianceEngine(args.rules, args.catalog).assess_file(args.configuration)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(render_markdown(assessment), encoding="utf-8")
    args.output.with_suffix(".json").write_text(
        json.dumps(assessment.to_dict(), indent=2), encoding="utf-8"
    )
    print(f"Wrote reports to {args.output} and {args.output.with_suffix('.json')}")


if __name__ == "__main__":
    main()
