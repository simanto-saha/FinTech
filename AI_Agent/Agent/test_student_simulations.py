from decimal import Decimal
from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from Agent import llm, tools
from Agent.models import Session


class StudentLifeSimulationTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="student_tester", email="student@example.com")
        self.session = Session.objects.create(user=self.user, corridor="BD-CN")

    def test_tool_create_budget_returns_daily_and_weekly_envelopes(self):
        res = tools.tool_create_budget(self.session, {"monthly_income": "1200", "currency": "GBP"})
        self.assertEqual(res["monthly_income"], "1200")
        self.assertEqual(res["currency"], "GBP")
        self.assertIn("breakdown", res)
        self.assertIn("daily_living_allowance", res)
        self.assertIn("weekly_envelopes", res)
        self.assertIn("groceries", res["weekly_envelopes"])
        self.assertIn("transit", res["weekly_envelopes"])
        self.assertIn("utilities_mobile", res["weekly_envelopes"])
        self.assertIn("contingency_buffer", res["weekly_envelopes"])
        self.assertIn("fx_shock_test", res)
        self.assertEqual(res["fx_shock_test"]["baseline_runway_days"], 90)
        self.assertTrue(res["fx_shock_test"]["shock_10pct_runway_days"] < 90)

    def test_tool_prepare_credit_application_returns_alternative_credit_profile(self):
        res = tools.tool_prepare_credit_application(self.session, {"destination_country": "GB", "card_type": "student_credit_card"})
        self.assertEqual(res["destination_country"], "GB")
        self.assertIn("alternative_credit_score", res)
        self.assertGreaterEqual(res["alternative_credit_score"], 700)
        self.assertIn("verifiable_rental_reference", res)
        self.assertIn("score_grade", res)

    def test_offline_student_assistant_rent_query(self):
        msg = llm._offline_student_assistant([{"role": "user", "content": "I need to pay rent and deposit to my landlord in London"}])
        self.assertIn("offline", msg["content"].lower())
        self.assertIn("rent", msg["content"].lower())
        self.assertIn("deposit", msg["content"].lower())

    def test_offline_student_assistant_tuition_hold_query(self):
        msg = llm._offline_student_assistant([{"role": "user", "content": "Urgent tuition deadline at SZU Shenzhen University, avoid registration hold"}])
        self.assertIn("offline", msg["content"].lower())
        self.assertIn("shenzhen", msg["content"].lower())
        self.assertIn("hold", msg["content"].lower())

    def test_offline_student_assistant_fx_shock_query(self):
        msg = llm._offline_student_assistant([{"role": "user", "content": "Currency devaluation shock on my monthly allowance, test runway"}])
        self.assertIn("offline", msg["content"].lower())
        self.assertIn("runway", msg["content"].lower())
        self.assertIn("devaluation", msg["content"].lower())

    def test_offline_student_assistant_daily_envelopes_query(self):
        msg = llm._offline_student_assistant([{"role": "user", "content": "What is my daily allowance and weekly grocery transit envelope on £800/month"}])
        self.assertIn("offline", msg["content"].lower())
        self.assertIn("daily", msg["content"].lower())
        self.assertIn("envelope", msg["content"].lower())

    def test_offline_student_assistant_credit_query(self):
        msg = llm._offline_student_assistant([{"role": "user", "content": "How do I build an alternative credit score and tenant certificate for landlords"}])
        self.assertIn("offline", msg["content"].lower())
        self.assertIn("credit", msg["content"].lower())

    def test_offline_student_assistant_health_query(self):
        msg = llm._offline_student_assistant([{"role": "user", "content": "Calculate my UK NHS health surcharge and medical emergency buffer"}])
        self.assertIn("offline", msg["content"].lower())
        self.assertIn("health", msg["content"].lower())

    def test_home_page_contains_all_student_life_simulations(self):
        resp = self.client.get(reverse("home"))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'id="student-life"')
        self.assertContains(resp, 'id="tab-stu-rent"')
        self.assertContains(resp, 'id="tab-stu-tuition"')
        self.assertContains(resp, 'id="tab-stu-fxshock"')
        self.assertContains(resp, 'id="tab-stu-envelopes"')
        self.assertContains(resp, 'id="tab-stu-credit"')
        self.assertContains(resp, 'id="tab-stu-health"')

