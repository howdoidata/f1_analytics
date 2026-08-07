#!/usr/bin/env python3
"""Analyze championship leader conversion at the latest completed cutoff round."""

from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from f1_analytics.analysis.championship_leaders import run_analysis


def main() -> int:
    """Run the championship leader analysis and print generated artifact paths."""
    result = run_analysis()

    print(f"Target season: {result['target_season']}")
    print(f"Cutoff round: {result['cutoff_round']}")
    print(f"Cutoff race: {result['cutoff_race_name']} ({result['cutoff_race_date']})")
    print(f"Report written: {Path(result['report_path']).relative_to(PROJECT_ROOT)}")
    print(f"Follow-up report written: {Path(result['followup_report_path']).relative_to(PROJECT_ROOT)}")
    print(f"Tables written: {Path(result['table_dir']).relative_to(PROJECT_ROOT)}")
    if result["figure_path"] is not None:
        print(f"Figure written: {Path(result['figure_path']).relative_to(PROJECT_ROOT)}")
    if result["largest_constructor_deficit"] is not None:
        print(f"Largest constructor deficit overcome: {result['largest_constructor_deficit']:.0f} points")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
