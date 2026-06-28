"""Export integrity issues to various formats (CSV, JSON, Markdown)."""

import csv
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

from src.integrity.models import IntegrityIssue, IntegrityReport

logger = logging.getLogger(__name__)


class DataExporter:
    """Export integrity issues and assessment data to backup formats."""

    def export_to_csv(self, records: List[Dict[str, Any]], output_file: str) -> int:
        """Export records to CSV format."""
        try:
            with open(output_file, "w", newline="") as f:
                if not records:
                    logger.warning(f"No records to export to {output_file}")
                    return 0

                writer = csv.DictWriter(f, fieldnames=records[0].keys())
                writer.writeheader()
                writer.writerows(records)

            logger.info(f"Exported {len(records)} records to {output_file}")
            return len(records)
        except Exception as e:
            logger.error(f"Error exporting to CSV {output_file}: {e}")
            return 0

    def export_to_json(self, records: List[Dict[str, Any]], output_file: str) -> int:
        """Export records to JSON format."""
        try:
            with open(output_file, "w") as f:
                json.dump(records, f, indent=2, default=str)

            logger.info(f"Exported {len(records)} records to {output_file}")
            return len(records)
        except Exception as e:
            logger.error(f"Error exporting to JSON {output_file}: {e}")
            return 0

    def export_issues_to_markdown(
        self, issues: List[IntegrityIssue], output_file: str
    ) -> int:
        """Export integrity issues to Markdown report."""
        try:
            lines = []
            lines.append("# Integrity Issues Report")
            lines.append(f"\nGenerated: {datetime.utcnow().isoformat()} UTC\n")

            # Summary section
            error_count = sum(1 for i in issues if i.severity == "error")
            warning_count = sum(1 for i in issues if i.severity == "warning")
            info_count = sum(1 for i in issues if i.severity == "info")

            lines.append("## Summary")
            lines.append(f"- **Total Issues**: {len(issues)}")
            lines.append(f"- **Errors**: {error_count}")
            lines.append(f"- **Warnings**: {warning_count}")
            lines.append(f"- **Info**: {info_count}\n")

            # Group by issue type
            by_type: Dict[str, List[IntegrityIssue]] = {}
            for issue in issues:
                if issue.issue_type not in by_type:
                    by_type[issue.issue_type] = []
                by_type[issue.issue_type].append(issue)

            # Issues by type table
            lines.append("## Issues by Type")
            lines.append(
                "| Type | Count | Table | Severity | Action |"
            )
            lines.append("|------|-------|-------|----------|--------|")

            for issue_type in sorted(by_type.keys()):
                type_issues = by_type[issue_type]
                severity = type_issues[0].severity
                count = len(type_issues)
                table = type_issues[0].table
                action = type_issues[0].suggested_action

                lines.append(f"| {issue_type} | {count} | {table} | {severity} | {action} |")

            lines.append("\n")

            # Details section
            lines.append("## Issue Details\n")
            for issue_type in sorted(by_type.keys()):
                lines.append(f"### {issue_type.replace('_', ' ').title()}\n")
                for issue in by_type[issue_type]:
                    lines.append(f"- **{issue.record_id}**: {issue.details}")
                    lines.append(f"  - Action: {issue.suggested_action}\n")

            with open(output_file, "w") as f:
                f.write("\n".join(lines))

            logger.info(f"Exported {len(issues)} issues to Markdown {output_file}")
            return len(issues)
        except Exception as e:
            logger.error(f"Error exporting to Markdown {output_file}: {e}")
            return 0

    def export_report_to_markdown(self, report: IntegrityReport, output_file: str) -> int:
        """Export full integrity report to Markdown."""
        try:
            lines = []
            lines.append("# Database Integrity Report")
            lines.append(f"\nGenerated: {report.timestamp.isoformat()} UTC\n")

            # Summary
            lines.append("## Summary")
            lines.append(f"- **Total Issues Found**: {len(report.issues_found)}")
            lines.append(f"- **Total Checks Run**: {report.total_checks}")
            lines.append(f"- **Records Affected**: {report.total_records_affected}")
            lines.append(f"- **Errors**: {report.error_count}")
            lines.append(f"- **Warnings**: {report.warning_count}")
            lines.append(f"- **Info**: {report.info_count}\n")

            # Issues by type
            if report.summary_by_type:
                lines.append("## Issues by Type")
                lines.append("| Type | Count |")
                lines.append("|------|-------|")
                for issue_type, count in sorted(report.summary_by_type.items()):
                    lines.append(f"| {issue_type} | {count} |")
                lines.append("")

            # Recommended purges
            if report.purge_recommendations:
                lines.append("## Recommended Actions")
                for i, rec in enumerate(report.purge_recommendations, 1):
                    lines.append(f"{i}. {rec}")
                lines.append("")

            # Detailed issues
            if report.issues_found:
                lines.append("## Detailed Issues\n")
                by_severity: dict[str, list] = {
                    "error": [],
                    "warning": [],
                    "info": [],
                }
                for issue in report.issues_found:
                    by_severity[issue.severity].append(issue)

                for severity in ["error", "warning", "info"]:
                    if by_severity[severity]:
                        lines.append(f"### {severity.upper()}\n")
                        for issue in by_severity[severity]:
                            lines.append(f"- **{issue.record_id}** ({issue.table})")
                            lines.append(f"  - Type: {issue.issue_type}")
                            lines.append(f"  - Details: {issue.details}")
                            lines.append(f"  - Action: {issue.suggested_action}\n")

            with open(output_file, "w") as f:
                f.write("\n".join(lines))

            logger.info(f"Exported report to {output_file}")
            return len(report.issues_found)
        except Exception as e:
            logger.error(f"Error exporting report to {output_file}: {e}")
            return 0

    def generate_backup(self, issues: List[IntegrityIssue], output_dir: str) -> Dict[str, str]:
        """Generate full backup of issues grouped by type."""
        try:
            Path(output_dir).mkdir(parents=True, exist_ok=True)

            # Group issues by type
            by_type: Dict[str, List[Dict[str, Any]]] = {}
            for issue in issues:
                if issue.issue_type not in by_type:
                    by_type[issue.issue_type] = []

                issue_dict = {
                    "issue_type": issue.issue_type,
                    "severity": issue.severity,
                    "table": issue.table,
                    "record_id": issue.record_id,
                    "details": issue.details,
                    "suggested_action": issue.suggested_action,
                }
                by_type[issue.issue_type].append(issue_dict)

            # Export each type to CSV
            exported_files = {}
            for issue_type, records in by_type.items():
                filename = f"{output_dir}/{issue_type}.csv"
                count = self.export_to_csv(records, filename)
                if count > 0:
                    exported_files[issue_type] = filename

            logger.info(f"Generated backup with {len(exported_files)} issue types in {output_dir}")
            return exported_files
        except Exception as e:
            logger.error(f"Error generating backup: {e}")
            return {}
