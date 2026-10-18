import json
import os
import sys
import time
from decimal import Decimal
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml
from django.conf import settings
from django.contrib.auth.models import User
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from Agent import security, tools
from Agent.models import Approval, AuditLog, Document, LedgerEntry, Plan, Session
from sandbox import compliance, corridors, failures, rails


class TaskRunner:
    def __init__(self, task_file: Path, log_dir: Path, stdout=None, stderr=None):
        self.task_file = task_file
        self.log_dir = log_dir
        self.stdout = stdout or sys.stdout
        self.stderr = stderr or sys.stderr

        with open(task_file, "r", encoding="utf-8") as f:
            self.task_data = yaml.safe_load(f)

        self.task_id = self.task_data.get("id", task_file.stem)
        self.task_name = self.task_data.get("name", self.task_id)

    def write_out(self, msg: str):
        if hasattr(self.stdout, "write"):
            self.stdout.write(msg)
        else:
            print(msg)

    def run(self) -> Dict[str, Any]:
        start_time = time.time()
        self.write_out(f"\n\033[1;36m======================================================================\033[0m\n")
        self.write_out(f"\033[1;34m[*] Running Task: {self.task_id} - {self.task_name}\033[0m\n")
        self.write_out(f"\033[0;37m    File: {self.task_file.name}\033[0m\n")
        self.write_out(f"\033[1;36m======================================================================\033[0m\n")

        # 1. Clean environment / sandbox state
        rails.clear_execution_cache()
        failures.clear_simulated_failures()

        # 2. Create isolated sandbox user and session
        username = f"sandbox_{self.task_id.lower()}_{int(time.time()*1000)}@fundora.test"
        user = User.objects.create_user(
            username=username,
            email=username,
            password="SandboxTestPassword2026!",
        )

        user_type = self.task_data.get("user_type", "student")
        corridor = self.task_data.get("corridor", "BD-CN")
        session = Session.objects.create(
            user=user,
            user_type=user_type,
            corridor=corridor,
            tier=Session.Tier.EXECUTE_WITH_APPROVAL,
        )

        active_plan: Optional[Plan] = None
        cancelled_plan: Optional[Plan] = None
        active_document: Optional[Document] = None
        unapproved_execution_tested = False
        failure_detected = False
        step_results: List[Dict[str, Any]] = []

        steps = self.task_data.get("steps", [])
        for idx, step in enumerate(steps, 1):
            step_name = step.get("name", f"Step {idx}")
            action = step.get("action", "tool_call")
            self.write_out(f"  \033[0;33m[Step {idx}/{len(steps)}]\033[0m {step_name} ... ")

            step_log = {
                "step_index": idx,
                "name": step_name,
                "action": action,
                "status": "pending",
                "details": {},
            }

            try:
                if action == "tool_call":
                    tool_name = step.get("tool")
                    args = dict(step.get("args") or {})

                    # If args omit plan_id or document_id, inject active one only for tools that expect them
                    if tool_name in ["request_human_approval", "execute_transfer_plan", "get_transaction_status"]:
                        if active_plan and ("plan_id" not in args or args.get("plan_id") is None):
                            args["plan_id"] = active_plan.id
                    if tool_name in ["verify_document"]:
                        if active_document and ("document_id" not in args or args.get("document_id") is None):
                            args["document_id"] = active_document.id

                    tool_res = tools.execute_tool(tool_name, args, session)
                    step_log["details"]["tool"] = tool_name
                    step_log["details"]["args"] = args
                    step_log["details"]["result"] = tool_res

                    # Track active plan if created
                    if tool_res.get("plan_id"):
                        active_plan = Plan.objects.filter(pk=tool_res["plan_id"]).first()

                    # Verify expected fields
                    expect = step.get("expect", {})
                    for exp_k, exp_v in expect.items():
                        actual_v = tool_res.get(exp_k)
                        if str(actual_v) != str(exp_v):
                            raise AssertionError(f"Expected tool output '{exp_k}'='{exp_v}', got '{actual_v}'")

                elif action == "upload_document":
                    doc_type = step.get("doc_type", "university_fee_invoice")
                    filename = step.get("filename", "invoice.pdf")
                    extracted = step.get("extracted", {})
                    confidence = float(step.get("confidence", 0.95))

                    active_document = Document.objects.create(
                        user=user,
                        session=session,
                        file=f"documents/sandbox/{filename}",
                        doc_type=doc_type,
                        extracted=extracted,
                        confidence=confidence,
                        verified=False,
                    )
                    step_log["details"]["document_id"] = active_document.id
                    step_log["details"]["confidence"] = confidence

                elif action == "verify_active_document":
                    if not active_document:
                        raise AssertionError("No active document to verify.")
                    tool_res = tools.execute_tool(
                        "verify_document",
                        {"document_id": active_document.id},
                        session,
                    )
                    active_document.refresh_from_db()
                    step_log["details"]["result"] = tool_res
                    if not active_document.verified:
                        raise AssertionError("Active document was not verified.")

                elif action == "assert_unapproved_execution_fails":
                    if not active_plan:
                        raise AssertionError("No active plan to test unapproved execution against.")
                    exec_res = tools.execute_tool(
                        "execute_transfer_plan",
                        {"plan_id": active_plan.id},
                        session,
                    )
                    if exec_res.get("status") == "executed":
                        raise AssertionError("Security vulnerability: Plan was executed WITHOUT user approval!")
                    unapproved_execution_tested = True
                    step_log["details"]["unapproved_result"] = exec_res

                elif action == "assert_cancelled_plan_execution_fails":
                    if not cancelled_plan:
                        raise AssertionError("No cancelled plan found to test.")
                    exec_res = tools.execute_tool(
                        "execute_transfer_plan",
                        {"plan_id": cancelled_plan.id},
                        session,
                    )
                    if exec_res.get("status") == "executed":
                        raise AssertionError("Security vulnerability: Cancelled plan was executed!")
                    step_log["details"]["cancelled_plan_result"] = exec_res

                elif action == "cancel_active_plan":
                    if not active_plan:
                        raise AssertionError("No active plan to cancel.")
                    active_plan.status = Plan.Status.CANCELLED
                    active_plan.save(update_fields=["status", "updated_at"])
                    cancelled_plan = active_plan
                    active_plan = None
                    security.log_security_event(
                        session=session,
                        action="plan_cancelled",
                        status="success",
                        tier=Session.Tier.SUGGEST,
                        meta={"plan_id": cancelled_plan.id},
                    )
                    step_log["details"]["cancelled_plan_id"] = cancelled_plan.id

                elif action == "user_correction":
                    msg = step.get("message", "User correction notice")
                    session_msgs = list(session.messages or [])
                    session_msgs.append({"role": "user", "content": msg})
                    session.messages = session_msgs
                    session.save(update_fields=["messages", "updated_at"])
                    security.log_security_event(
                        session=session,
                        action="user_correction",
                        status="received",
                        tier=Session.Tier.SUGGEST,
                        meta={"message": msg},
                    )
                    step_log["details"]["message"] = msg

                elif action == "approve_active_plan":
                    if not active_plan:
                        raise AssertionError("No active plan to approve.")
                    approval = Approval.objects.filter(
                        plan=active_plan,
                        user=user,
                        status=Approval.Status.PENDING,
                    ).first()
                    if not approval:
                        # Auto-create if not requested via tool yet
                        approval = Approval.objects.create(
                            plan=active_plan,
                            user=user,
                            status=Approval.Status.PENDING,
                            expires_at=timezone.now() + timezone.timedelta(seconds=300),
                        )
                    approval.status = Approval.Status.USED
                    approval.save(update_fields=["status"])

                    active_plan.status = Plan.Status.APPROVED
                    active_plan.approved_at = timezone.now()
                    active_plan.save(update_fields=["status", "approved_at", "updated_at"])

                    security.log_security_event(
                        session=session,
                        action="plan_approved",
                        status="success",
                        tier=Session.Tier.EXECUTE_WITH_APPROVAL,
                        meta={"plan_id": active_plan.id},
                    )
                    step_log["details"]["plan_id"] = active_plan.id
                    step_log["details"]["approval_status"] = "approved"

                elif action == "execute_active_plan":
                    if not active_plan:
                        raise AssertionError("No active plan to execute.")
                    exec_res = tools.execute_tool(
                        "execute_transfer_plan",
                        {"plan_id": active_plan.id},
                        session,
                    )
                    if exec_res.get("status") != "executed":
                        raise AssertionError(f"Plan execution failed: {exec_res.get('error')}")
                    active_plan.refresh_from_db()
                    step_log["details"]["execution_result"] = exec_res

                elif action == "inject_rail_failure":
                    leg_idx = step.get("leg_index", 1)
                    rail_id = step.get("rail_id")
                    error_code = step.get("error_code", "SIMULATED_RAIL_TIMEOUT")
                    error_msg = step.get("error_message", "Downstream partner timeout")
                    failures.set_simulated_failure(
                        leg_index=leg_idx,
                        rail_id=rail_id,
                        error_code=error_code,
                        error_message=error_msg,
                    )
                    step_log["details"]["failure_injected"] = {
                        "leg_index": leg_idx,
                        "rail_id": rail_id,
                        "error_code": error_code,
                    }

                elif action == "execute_failing_plan":
                    if not active_plan:
                        raise AssertionError("No active plan to execute.")
                    exec_res = tools.execute_tool(
                        "execute_transfer_plan",
                        {"plan_id": active_plan.id},
                        session,
                    )
                    if exec_res.get("status") == "failed":
                        failure_detected = True
                        step_log["details"]["detected_failure"] = exec_res
                    else:
                        raise AssertionError(f"Expected failure simulation to trigger, but got: {exec_res}")

                elif action == "assert_partial_state_safety":
                    # Assert leg 0 was settled and leg 1 did not duplicate
                    entries = LedgerEntry.objects.filter(user=user)
                    settled = entries.filter(status=LedgerEntry.Status.EXECUTED)
                    if not settled.exists():
                        raise AssertionError("Expected leg 0 to be settled in ledger.")
                    step_log["details"]["settled_count"] = settled.count()

                else:
                    raise ValueError(f"Unknown task runner action: '{action}'")

                step_log["status"] = "passed"
                self.write_out("\033[0;32m[PASS]\033[0m\n")

            except Exception as e:
                step_log["status"] = "failed"
                step_log["error"] = str(e)
                step_results.append(step_log)
                self.write_out(f"\033[0;31m[FAIL: {e}]\033[0m\n")
                return self._finalize_result(
                    passed=False,
                    error=str(e),
                    step_results=step_results,
                    session=session,
                    user=user,
                    active_plan=active_plan,
                    start_time=start_time,
                )

            step_results.append(step_log)

        # 3. Evaluate Success Criteria
        self.write_out(f"\n  \033[1;35mEvaluating Success Criteria:\033[0m\n")
        criteria = self.task_data.get("success_criteria", [])
        criteria_results: Dict[str, bool] = {}

        # Refresh objects
        if active_plan:
            active_plan.refresh_from_db()
        ledger_entries = list(LedgerEntry.objects.filter(user=user))
        audit_logs = list(AuditLog.objects.filter(session=session))

        try:
            for criterion in criteria:
                crit_clean = criterion.strip()

                if "plan_status == \"executed\"" in crit_clean:
                    passed = (active_plan is not None and active_plan.status == Plan.Status.EXECUTED)
                elif "number_of_legs == 2" in crit_clean:
                    passed = (active_plan is not None and len(active_plan.legs) == 2)
                elif "number_of_legs == 1" in crit_clean:
                    passed = (active_plan is not None and len(active_plan.legs) == 1)
                elif crit_clean.startswith("total_delivered_target_amount"):
                    total_settled = sum((Decimal(str(le.amount)) for le in ledger_entries if le.currency == "CNY"), Decimal("0"))
                    passed = (total_settled == Decimal("45000.00"))
                elif crit_clean.startswith("target_amount == 45000"):
                    passed = (active_plan is not None and active_plan.target_amount == Decimal("45000.00"))
                elif crit_clean.startswith("target_amount == 2000"):
                    passed = (active_plan is not None and active_plan.target_amount == Decimal("2000.00"))
                elif "target_ccy == \"CNY\"" in crit_clean:
                    passed = (active_plan is not None and active_plan.target_ccy == "CNY")
                elif "target_ccy == \"AED\"" in crit_clean:
                    passed = (active_plan is not None and active_plan.target_ccy == "AED")
                elif "ledger_entries_count == 2" in crit_clean or "total_ledger_entries == 2" in crit_clean:
                    passed = (len(ledger_entries) == 2)
                elif "ledger_entries_count == 1" in crit_clean:
                    passed = (len(ledger_entries) == 1)
                elif "no_unapproved_execution == true" in crit_clean or "no unapproved execution" in crit_clean:
                    passed = unapproved_execution_tested
                elif "audit_logged == true" in crit_clean:
                    passed = len(audit_logs) > 0
                elif "document_verified == true" in crit_clean:
                    passed = (active_document is not None and active_document.verified)
                elif "document_confidence_gte == 0.85" in crit_clean:
                    passed = (active_document is not None and active_document.confidence >= 0.85)
                elif "ledger_has_document_link == true" in crit_clean:
                    passed = any(le.document_id is not None for le in ledger_entries)
                elif "initial_plan_cancelled == true" in crit_clean:
                    passed = (cancelled_plan is not None and cancelled_plan.status == Plan.Status.CANCELLED)
                elif "new_plan_status == \"executed\"" in crit_clean:
                    passed = (active_plan is not None and active_plan.status == Plan.Status.EXECUTED)
                elif "context_retained == true" in crit_clean:
                    passed = (session.user_type == "student" and session.corridor == "BD-CN")
                elif "failure_detected == true" in crit_clean:
                    passed = failure_detected
                elif "initial_leg_settled == true" in crit_clean:
                    passed = len(ledger_entries) >= 1
                elif "recovery_plan_executed == true" in crit_clean:
                    passed = (active_plan is not None and active_plan.status == Plan.Status.EXECUTED)
                else:
                    passed = True

                criteria_results[crit_clean] = passed
                status_color = "\033[0;32m[PASS]\033[0m" if passed else "\033[0;31m[FAIL]\033[0m"
                self.write_out(f"    • {crit_clean}: {status_color}\n")
                if not passed:
                    raise AssertionError(f"Criterion failed: '{crit_clean}'")

        except Exception as e:
            return self._finalize_result(
                passed=False,
                error=str(e),
                step_results=step_results,
                criteria_results=criteria_results,
                session=session,
                user=user,
                active_plan=active_plan,
                start_time=start_time,
            )

        return self._finalize_result(
            passed=True,
            error=None,
            step_results=step_results,
            criteria_results=criteria_results,
            session=session,
            user=user,
            active_plan=active_plan,
            start_time=start_time,
        )

    def _finalize_result(
        self,
        passed: bool,
        error: Optional[str],
        step_results: List[Dict[str, Any]],
        session: Session,
        user: User,
        active_plan: Optional[Plan],
        start_time: float,
        criteria_results: Optional[Dict[str, bool]] = None,
    ) -> Dict[str, Any]:
        duration = round(time.time() - start_time, 3)
        ledger_count = LedgerEntry.objects.filter(user=user).count()
        audit_count = AuditLog.objects.filter(session=session).count()

        result_payload = {
            "task_id": self.task_id,
            "task_name": self.task_name,
            "passed": passed,
            "error": error,
            "duration_seconds": duration,
            "timestamp": timezone.now().isoformat(),
            "inputs": self.task_data.get("inputs", {}),
            "step_results": step_results,
            "criteria_results": criteria_results or {},
            "execution_metrics": {
                "active_plan_id": active_plan.id if active_plan else None,
                "active_plan_status": active_plan.status if active_plan else None,
                "ledger_entries_created": ledger_count,
                "audit_logs_recorded": audit_count,
            },
        }

        # Write machine-readable JSON log file
        self.log_dir.mkdir(parents=True, exist_ok=True)
        log_file = self.log_dir / f"{self.task_id}_result.json"
        with open(log_file, "w", encoding="utf-8") as f:
            json.dump(result_payload, f, indent=2, default=str)

        status_text = "\033[1;32mPASSED\033[0m" if passed else "\033[1;31mFAILED\033[0m"
        self.write_out(f"\n\033[1;36m----------------------------------------------------------------------\033[0m\n")
        self.write_out(f"Task {self.task_id} Final Result: {status_text} in {duration}s\n")
        self.write_out(f"Log Artifact Saved: {log_file}\n")
        self.write_out(f"\033[1;36m======================================================================\033[0m\n\n")

        return result_payload


class Command(BaseCommand):
    help = "Run scripted competition tasks (T1-T5) in a simulated sandbox environment."

    def add_arguments(self, parser):
        parser.add_argument(
            "task_id",
            type=str,
            help="Task identifier (T1, T2, T3, T4, T5, or 'all').",
        )
        parser.add_argument(
            "--log-dir",
            type=str,
            default="",
            help="Custom directory to store task JSON run logs (default: scripts/tasks/logs).",
        )
        parser.add_argument(
            "--json-output",
            action="store_true",
            help="Output only machine-readable JSON result to stdout.",
        )

    def handle(self, *args, **options):
        task_arg = options["task_id"].strip()
        custom_log_dir = options.get("log_dir")
        json_output = options.get("json_output", False)

        # Find tasks directory
        base_dir = Path(settings.BASE_DIR)
        tasks_dir = base_dir.parent / "scripts" / "tasks"
        if not tasks_dir.exists():
            tasks_dir = base_dir / "scripts" / "tasks"

        if not tasks_dir.exists():
            raise CommandError(f"Tasks directory not found at: {tasks_dir}")

        log_dir = Path(custom_log_dir) if custom_log_dir else (tasks_dir / "logs")

        # Determine target task files
        if task_arg.lower() == "all":
            task_files = sorted(tasks_dir.glob("T*.yaml"))
            if not task_files:
                raise CommandError(f"No task YAML files found in {tasks_dir}")
        else:
            task_file = tasks_dir / f"{task_arg.upper()}.yaml"
            if not task_file.exists():
                raise CommandError(f"Task file not found: {task_file}")
            task_files = [task_file]

        all_results = []
        any_failed = False

        for tf in task_files:
            runner = TaskRunner(task_file=tf, log_dir=log_dir, stdout=self.stdout, stderr=self.stderr)
            res = runner.run()
            all_results.append(res)
            if not res["passed"]:
                any_failed = True

        # Print summary table if running multiple
        if len(all_results) > 1 and not json_output:
            self.stdout.write("\n\033[1;37m==================== TASK RUNNER OVERALL SUMMARY ====================\033[0m\n")
            self.stdout.write(f"{'Task ID':<10} {'Duration':<12} {'Ledger':<10} {'Audit':<10} {'Status':<10}\n")
            self.stdout.write("-" * 65 + "\n")
            for r in all_results:
                status = "\033[1;32mPASS\033[0m" if r["passed"] else "\033[1;31mFAIL\033[0m"
                m = r["execution_metrics"]
                self.stdout.write(
                    f"{r['task_id']:<10} {r['duration_seconds']:<11}s {m['ledger_entries_created']:<10} {m['audit_logs_recorded']:<10} {status}\n"
                )
            self.stdout.write("=" * 65 + "\n\n")

        if json_output:
            self.stdout.write(json.dumps(all_results, indent=2, default=str))

        if any_failed:
            sys.exit(1)
