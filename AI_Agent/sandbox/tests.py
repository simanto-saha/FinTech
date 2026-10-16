from decimal import Decimal
from django.contrib.auth.models import User
from django.test import TestCase

from Agent.models import LedgerEntry, Plan, Session, University
from sandbox import compliance, corridors, failures, fx, rails, universities


class CorridorRulesTests(TestCase):
    def test_list_supported_corridors(self):
        supported = corridors.list_supported_corridors()
        self.assertIn("BD-CN", supported)
        self.assertIn("IN-GB", supported)
        self.assertIn("PH-AE", supported)

    def test_get_corridor_rules_bd_cn(self):
        rule = corridors.get_corridor_rules("BD-CN")
        self.assertIsNotNone(rule)
        self.assertEqual(rule["from_country"], "BD")
        self.assertEqual(rule["to_country"], "CN")
        self.assertEqual(rule["from_ccy"], "BDT")
        self.assertEqual(rule["to_ccy"], "CNY")
        self.assertEqual(rule["cap_daily"], Decimal("500000.00"))
        self.assertIn("student_visa", rule["requires"])
        self.assertIn("admission_letter", rule["requires"])
        self.assertIn("invoice", rule["requires"])

    def test_check_corridor_cap_breach(self):
        # 750,000 BDT exceeds 500,000 BDT cap -> must recommend 2 legs
        res = corridors.check_corridor_cap("BD-CN", 750000, "BDT")
        self.assertTrue(res["breaches_cap"])
        self.assertTrue(res["requires_split"])
        self.assertEqual(res["recommended_legs"], 2)

    def test_check_corridor_cap_within_limit(self):
        res = corridors.check_corridor_cap("BD-CN", 250000, "BDT")
        self.assertFalse(res["breaches_cap"])
        self.assertFalse(res["requires_split"])
        self.assertEqual(res["recommended_legs"], 1)

    def test_unsupported_corridor_returns_none(self):
        self.assertIsNone(corridors.get_corridor_rules("XX-YY"))


class UniversityReferenceTests(TestCase):
    def test_lookup_all_five_universities_by_slug(self):
        slugs = ["szu", "tsinghua", "nus", "manchester", "melbourne"]
        for slug in slugs:
            uni = universities.lookup_university(slug)
            self.assertIsNotNone(uni, f"Failed to look up {slug}")
            self.assertEqual(uni["slug"], slug)
            self.assertTrue(len(uni["payment_channels"]) > 0)
            self.assertTrue(len(uni["common_issues"]) > 0)
            self.assertIn("email", uni["support"])

    def test_lookup_by_aliases(self):
        szu_alias = universities.lookup_university("深大")
        self.assertIsNotNone(szu_alias)
        self.assertEqual(szu_alias["slug"], "szu")

        thu_alias = universities.lookup_university("THU")
        self.assertIsNotNone(thu_alias)
        self.assertEqual(thu_alias["slug"], "tsinghua")

        man_alias = universities.lookup_university("UoM")
        self.assertIsNotNone(man_alias)
        self.assertEqual(man_alias["slug"], "manchester")

    def test_seed_universities_to_db_and_lookup_from_db(self):
        count = universities.seed_universities_to_db()
        self.assertEqual(count, 5)
        self.assertEqual(University.objects.count(), 5)

        db_lookup = universities.lookup_university("Shenzhen University")
        self.assertIsNotNone(db_lookup)
        self.assertEqual(db_lookup["source"], "database")


class DeterministicFXTests(TestCase):
    def test_bdt_to_cny_conversion_rate(self):
        # 120 BDT/USD, 7.20 CNY/USD => 7.20 / 120.00 = 0.060000 CNY per BDT
        rate = fx.get_base_rate("BDT", "CNY")
        self.assertEqual(rate, Decimal("0.060000"))

        quote = fx.get_fx_quote("BDT", "CNY", amount_from=Decimal("750000.00"))
        self.assertEqual(quote["rate"], Decimal("0.060000"))
        self.assertEqual(quote["target_amount"], Decimal("45000.00"))
        self.assertTrue(quote["is_simulated"])
        self.assertIn("Simulated", quote["disclaimer"])

    def test_php_to_aed_conversion(self):
        quote = fx.get_fx_quote("PHP", "AED", amount_from=Decimal("10000.00"))
        self.assertTrue(quote["target_amount"] > 0)
        self.assertTrue(quote["is_simulated"])

    def test_currency_rounding(self):
        # JPY rounds to 0 decimal places
        jpy_rounded = fx.round_amount("1234.56", "JPY")
        self.assertEqual(jpy_rounded, Decimal("1235"))

        # CNY rounds to 2 decimal places
        cny_rounded = fx.round_amount("45000.567", "CNY")
        self.assertEqual(cny_rounded, Decimal("45000.57"))


class DeterministicComplianceTests(TestCase):
    def setUp(self):
        self.clean_user = User.objects.create_user(
            username="regular_student",
            email="student@university.edu",
        )
        self.blocked_user = User.objects.create_user(
            username="test_blocked_individual",
            email="test_blocked@example.com",
        )

    def test_clean_user_passes_all_checks(self):
        res = compliance.run_all(self.clean_user.pk)
        self.assertTrue(res["passed"])
        self.assertEqual(res["risk_level"], "LOW")
        self.assertTrue(res["checks"]["sanctions"]["passed"])
        self.assertTrue(res["checks"]["aml"]["passed"])
        self.assertTrue(res["checks"]["pep"]["passed"])
        self.assertTrue(res["checks"]["adverse_media"]["passed"])

    def test_blocked_identity_fails_sanctions(self):
        res = compliance.run_all(self.blocked_user.pk)
        self.assertFalse(res["passed"])
        self.assertEqual(res["risk_level"], "BLOCKED")
        self.assertFalse(res["checks"]["sanctions"]["passed"])
        self.assertEqual(res["checks"]["sanctions"]["status"], "blocked")

    def test_blocked_identity_by_string(self):
        res = compliance.run_all("test_blocked_account")
        self.assertFalse(res["passed"])
        self.assertEqual(res["risk_level"], "BLOCKED")

    def test_enforce_compliance_raises_for_blocked_user(self):
        with self.assertRaises(compliance.ComplianceCheckFailed):
            compliance.enforce_compliance(self.blocked_user.pk)

    def test_high_amount_aml_threshold(self):
        res = compliance.run_all(self.clean_user.pk, amount=Decimal("2500000.00"))
        self.assertFalse(res["passed"])
        self.assertEqual(res["risk_level"], "HIGH")
        self.assertFalse(res["checks"]["aml"]["passed"])


class SandboxRailsAndPlanningTests(TestCase):
    def test_list_rails_for_bd_cn(self):
        available = rails.list_rails(corridor="BD-CN")
        rail_ids = [r["rail_id"] for r in available]
        self.assertIn("bdt_bank_wire", rail_ids)
        self.assertIn("alipay_crossborder", rail_ids)
        self.assertIn("unionpay_intl", rail_ids)

    def test_quote_cost_calculation(self):
        quote = rails.quote_cost("bdt_bank_wire", Decimal("100000.00"), "BDT", "CNY")
        # fee_pct = 0.005 -> 500 BDT, fixed_fee = 500 BDT -> 1000 BDT total
        self.assertEqual(quote["fee_breakdown"]["total_fee"], Decimal("1000.00"))
        self.assertEqual(quote["exchange_rate"], Decimal("0.060000"))
        self.assertEqual(quote["target_amount"], Decimal("6000.00"))

    def test_build_plan_splits_over_cap_bd_cn(self):
        # 750,000 BDT exceeds 500,000 BDT daily cap -> split into 2 legs
        plan = rails.build_plan(
            corridor="BD-CN",
            target_amount=Decimal("45000.00"),
            target_ccy="CNY",
            currency_from="BDT",
        )
        self.assertTrue(plan["requires_split"])
        self.assertEqual(plan["number_of_legs"], 2)
        self.assertEqual(len(plan["legs"]), 2)
        self.assertEqual(plan["total_source_amount"], Decimal("750000.00"))
        self.assertEqual(plan["target_amount"], Decimal("45000.00"))

        # Both legs must be under cap (500,000 BDT)
        for leg in plan["legs"]:
            self.assertLessEqual(Decimal(str(leg["amount_from"])), Decimal("500000.00"))

        total_target_delivered = sum((Decimal(str(leg["target_amount"])) for leg in plan["legs"]), Decimal("0"))
        self.assertEqual(total_target_delivered, Decimal("45000.00"))


class ExecutionAndIdempotencyTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="student_executor",
            email="executor@example.com",
        )
        self.session = Session.objects.create(
            user=self.user,
            corridor="BD-CN",
            tier=Session.Tier.SUGGEST,
        )
        failures.clear_simulated_failures()

    def test_execute_plan_creates_ledger_and_receipt(self):
        plan_dict = rails.build_plan(
            corridor="BD-CN",
            target_amount=Decimal("45000.00"),
            target_ccy="CNY",
            currency_from="BDT",
        )
        django_plan = Plan.objects.create(
            session=self.session,
            user=self.user,
            legs=plan_dict["legs"],
            target_amount=Decimal("45000.00"),
            target_ccy="CNY",
            total_cost=plan_dict["total_cost"],
            status=Plan.Status.APPROVED,
        )

        exec_res = rails.execute(django_plan, idempotency_key="test_idem_key_001", user=self.user)
        self.assertEqual(exec_res["status"], "executed")
        self.assertTrue(exec_res["receipt_id"].startswith(f"REC-{django_plan.id}-"))
        self.assertTrue(len(exec_res["audit_hash"]) == 64)
        self.assertEqual(len(exec_res["legs"]), 2)

        # Verify ledger entries in database
        entries = LedgerEntry.objects.filter(user=self.user, status=LedgerEntry.Status.EXECUTED)
        self.assertEqual(entries.count(), 2)

    def test_repeated_execution_with_same_idempotency_key_does_not_duplicate(self):
        plan_dict = rails.build_plan(
            corridor="BD-CN",
            target_amount=Decimal("45000.00"),
            target_ccy="CNY",
            currency_from="BDT",
        )
        django_plan = Plan.objects.create(
            session=self.session,
            user=self.user,
            legs=plan_dict["legs"],
            target_amount=Decimal("45000.00"),
            target_ccy="CNY",
            total_cost=plan_dict["total_cost"],
            status=Plan.Status.APPROVED,
        )

        # First run
        exec_1 = rails.execute(django_plan, idempotency_key="idempotent_test_key_002", user=self.user)
        self.assertEqual(exec_1["status"], "executed")
        initial_ledger_count = LedgerEntry.objects.filter(user=self.user).count()
        self.assertEqual(initial_ledger_count, 2)

        # Repeated run with same idempotency key
        exec_2 = rails.execute(django_plan, idempotency_key="idempotent_test_key_002", user=self.user)
        self.assertEqual(exec_2["status"], "executed")
        subsequent_ledger_count = LedgerEntry.objects.filter(user=self.user).count()
        # Must not duplicate ledger entries
        self.assertEqual(subsequent_ledger_count, initial_ledger_count)


class SimulatedFailureRecoveryTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="student_recovery",
            email="recovery@example.com",
        )
        self.session = Session.objects.create(
            user=self.user,
            corridor="BD-CN",
            tier=Session.Tier.SUGGEST,
        )
        failures.clear_simulated_failures()

    def tearDown(self):
        failures.clear_simulated_failures()

    def test_multi_leg_failure_simulation_and_recovery(self):
        # Configure simulated failure on leg index 1 (the second leg, e.g. Task T5)
        failures.set_simulated_failure(
            leg_index=1,
            error_code="PARTNER_TIMEOUT",
            error_message="Downstream rail gateway timed out during leg 2 settlement.",
            once=True,
        )

        plan_dict = rails.build_plan(
            corridor="BD-CN",
            target_amount=Decimal("45000.00"),
            target_ccy="CNY",
            currency_from="BDT",
        )
        django_plan = Plan.objects.create(
            session=self.session,
            user=self.user,
            legs=plan_dict["legs"],
            target_amount=Decimal("45000.00"),
            target_ccy="CNY",
            total_cost=plan_dict["total_cost"],
            status=Plan.Status.APPROVED,
        )

        exec_res = rails.execute(django_plan, idempotency_key="t5_failure_run", user=self.user)
        self.assertEqual(exec_res["status"], "failed")
        self.assertEqual(exec_res["failed_leg"]["leg_index"], 1)
        self.assertEqual(exec_res["failed_leg"]["error_code"], "PARTNER_TIMEOUT")

        # Leg 0 succeeded, Leg 1 failed
        self.assertEqual(exec_res["legs"][0]["status"], "executed")
        self.assertEqual(exec_res["legs"][1]["status"], "failed")

        # Recovery scenario: replan remaining 22,500 CNY using an alternative rail (unionpay_intl)
        failed_leg_target = exec_res["legs"][1]["amount"] if "amount" in exec_res["legs"][1] else Decimal("22500.00")
        recovered_plan = rails.build_plan(
            corridor="BD-CN",
            target_amount=failed_leg_target,
            target_ccy="CNY",
            currency_from="BDT",
            rail_preference="unionpay_intl",
        )
        recovery_django_plan = Plan.objects.create(
            session=self.session,
            user=self.user,
            legs=recovered_plan["legs"],
            target_amount=failed_leg_target,
            target_ccy="CNY",
            total_cost=recovered_plan["total_cost"],
            status=Plan.Status.APPROVED,
        )

        recovery_exec = rails.execute(recovery_django_plan, idempotency_key="t5_recovery_run", user=self.user)
        self.assertEqual(recovery_exec["status"], "executed")
        self.assertEqual(recovery_exec["legs"][0]["rail_id"], "unionpay_intl")
