import io
import json
import re
from pathlib import Path
from django.core.management import call_command
from django.test import TransactionTestCase


def strip_ansi(text: str) -> str:
    return re.sub(r"\x1b\[[0-9;]*[mGKH]", "", text)


class TaskAndAttackRunnerCommandTests(TransactionTestCase):
    """
    Test suite verifying management commands `run_task` and `run_attack`.
    Ensures that scripted tasks T1-T5 and attack suites A1-A4 are fully
    tested within Django's automated test runner.
    """

    def test_run_task_t1(self):
        out = io.StringIO()
        call_command("run_task", "T1", stdout=out)
        output = strip_ansi(out.getvalue())
        self.assertIn("Task T1 Final Result: PASSED", output)
        self.assertIn("plan_status == \"executed\": [PASS]", output)

    def test_run_task_t2(self):
        out = io.StringIO()
        call_command("run_task", "T2", stdout=out)
        output = strip_ansi(out.getvalue())
        self.assertIn("Task T2 Final Result: PASSED", output)
        self.assertIn("number_of_legs == 1: [PASS]", output)

    def test_run_task_t3(self):
        out = io.StringIO()
        call_command("run_task", "T3", stdout=out)
        output = strip_ansi(out.getvalue())
        self.assertIn("Task T3 Final Result: PASSED", output)
        self.assertIn("document_verified == true: [PASS]", output)

    def test_run_task_t4(self):
        out = io.StringIO()
        call_command("run_task", "T4", stdout=out)
        output = strip_ansi(out.getvalue())
        self.assertIn("Task T4 Final Result: PASSED", output)
        self.assertIn("initial_plan_cancelled == true: [PASS]", output)
        self.assertIn("new_plan_status == \"executed\": [PASS]", output)

    def test_run_task_t5(self):
        out = io.StringIO()
        call_command("run_task", "T5", stdout=out)
        output = strip_ansi(out.getvalue())
        self.assertIn("Task T5 Final Result: PASSED", output)
        self.assertIn("failure_detected == true: [PASS]", output)
        self.assertIn("recovery_plan_executed == true: [PASS]", output)
        self.assertIn("total_delivered_target_amount == 45000.00: [PASS]", output)

    def test_run_task_all(self):
        out = io.StringIO()
        call_command("run_task", "all", stdout=out)
        output = strip_ansi(out.getvalue())
        self.assertIn("TASK RUNNER OVERALL SUMMARY", output)
        self.assertIn("T1", output)
        self.assertIn("T2", output)
        self.assertIn("T3", output)
        self.assertIn("T4", output)
        self.assertIn("T5", output)

    def test_run_attack_a1(self):
        out = io.StringIO()
        call_command("run_attack", "A1", stdout=out)
        output = strip_ansi(out.getvalue())
        self.assertIn("Attack Test A1 Result: DEFENSE PASSED", output)
        self.assertIn("[VERIFIED 0 EXECUTED]", output)
        self.assertIn("[VERIFIED 0 LEDGER ENTRIES]", output)

    def test_run_attack_a2(self):
        out = io.StringIO()
        call_command("run_attack", "A2", stdout=out)
        output = strip_ansi(out.getvalue())
        self.assertIn("Attack Test A2 Result: DEFENSE PASSED", output)
        self.assertIn("[MASKED]", output)
        self.assertIn("[TOKEN SHIELDED]", output)
        self.assertIn("[CONTEXT CLEAN]", output)

    def test_run_attack_a3(self):
        out = io.StringIO()
        call_command("run_attack", "A3", stdout=out)
        output = strip_ansi(out.getvalue())
        self.assertIn("Attack Test A3 Result: DEFENSE PASSED", output)
        self.assertIn("[TIER IMMUTABLE]", output)
        self.assertIn("[NON-STAFF SECURED]", output)

    def test_run_attack_a4(self):
        out = io.StringIO()
        call_command("run_attack", "A4", stdout=out)
        output = strip_ansi(out.getvalue())
        self.assertIn("Attack Test A4 Result: DEFENSE PASSED", output)
        self.assertIn("[ISOLATED IN <untrusted_document>]", output)
        self.assertIn("[ZERO UNAUTHORIZED ACTIONS]", output)

    def test_run_attack_all(self):
        out = io.StringIO()
        call_command("run_attack", "all", stdout=out)
        output = strip_ansi(out.getvalue())
        self.assertIn("ATTACK RUNNER OVERALL SUMMARY", output)
        self.assertIn("A1", output)
        self.assertIn("A2", output)
        self.assertIn("A3", output)
        self.assertIn("A4", output)

