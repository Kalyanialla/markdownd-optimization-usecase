"""
UC-RT-03: Optimizer Audit & Artifact Service.

Ensures that every optimization and pilot execution is written to an isolated,
timestamped run directory without overwriting prior pilot records.
Captures full audit logs, recommendation summaries, markdown reports, and run metadata.
"""

import os
import json
import uuid
import pandas as pd
from datetime import datetime
from typing import Dict, Any, List, Optional

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
DEFAULT_REPORTS_DIR = os.path.join(REPO_ROOT, "data/reports/optimizer")


class OptimizerAuditService:
    def __init__(self, base_reports_dir: str = DEFAULT_REPORTS_DIR):
        self.base_reports_dir = base_reports_dir
        self.runs_dir = os.path.join(self.base_reports_dir, "runs")
        os.makedirs(self.runs_dir, exist_ok=True)

    def initialize_run(self, run_tag: str = "pilot") -> Dict[str, str]:
        """
        Initializes an isolated directory for a new optimization execution.
        Returns run_id, run_dir, and ISO timestamp.
        """
        now = datetime.now()
        timestamp_str = now.strftime("%Y%m%d_%H%M%S")
        unique_suffix = uuid.uuid4().hex[:6]
        run_id = f"run_{timestamp_str}_{run_tag}_{unique_suffix}"
        
        run_dir = os.path.join(self.runs_dir, run_id)
        os.makedirs(run_dir, exist_ok=True)
        
        return {
            "run_id": run_id,
            "run_dir": run_dir,
            "created_at": now.isoformat()
        }

    def save_run_artifacts(
        self,
        run_info: Dict[str, str],
        audit_records: List[Dict[str, Any]],
        summary_df: pd.DataFrame,
        report_markdown: str,
        extra_metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, str]:
        """
        Persists audit.json, recommendations.csv, report.md, and run_metadata.json
        into the isolated run directory.
        """
        run_dir = run_info["run_dir"]
        run_id = run_info["run_id"]
        
        # 1. Save detailed audit.json
        audit_json_path = os.path.join(run_dir, "audit.json")
        with open(audit_json_path, "w", encoding="utf-8") as f:
            json.dump(audit_records, f, indent=2)
            
        # 2. Save recommendations.csv
        rec_csv_path = os.path.join(run_dir, "recommendations.csv")
        summary_df.to_csv(rec_csv_path, index=False)
        
        # 3. Save report.md
        report_md_path = os.path.join(run_dir, "report.md")
        with open(report_md_path, "w", encoding="utf-8") as f:
            f.write(report_markdown)
            
        # 4. Save run_metadata.json
        feasible_count = sum(1 for r in audit_records if r.get("recommendation_status") == "RECOMMENDED")
        metadata = {
            "run_id": run_id,
            "created_at": run_info["created_at"],
            "total_items_evaluated": len(audit_records),
            "feasible_recommendations_count": feasible_count,
            "infeasible_count": len(audit_records) - feasible_count,
            "extra_metadata": extra_metadata or {}
        }
        metadata_path = os.path.join(run_dir, "run_metadata.json")
        with open(metadata_path, "w", encoding="utf-8") as f:
            json.dump(metadata, f, indent=2)
            
        return {
            "audit_json": audit_json_path,
            "recommendations_csv": rec_csv_path,
            "report_md": report_md_path,
            "run_metadata": metadata_path
        }
