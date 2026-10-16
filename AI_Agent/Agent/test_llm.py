import os
from unittest.mock import patch
from django.contrib.auth.models import User
from django.test import TestCase
import httpx

from Agent import llm, security
from Agent.models import AuditLog, Session


class LLMClientTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="llm_tester", email="llm@example.com")
        self.session = Session.objects.create(user=self.user, corridor="BD-CN")

    def test_tool_definitions_contain_all_16_tools(self):
        tools = llm.get_openai_tool_definitions()
        self.assertEqual(len(tools), 16)
        tool_names = [t["function"]["name"] for t in tools]
        self.assertIn("classify_user", tool_names)
        self.assertIn("create_transfer_plan", tool_names)
        self.assertIn("request_human_approval", tool_names)
        self.assertIn("execute_transfer_plan", tool_names)
        self.assertIn("get_masked_field", tool_names)

    async def test_call_llm_missing_api_key_returns_fallback(self):
        with patch.dict(os.environ, {"DEEPSEEK_API_KEY": ""}):
            res = await llm.call_llm([{"role": "user", "content": "Hello"}])
            self.assertEqual(res["role"], "assistant")
            self.assertIn("offline", res["content"].lower())

    async def test_call_llm_success_with_mock_client(self):
        mock_response_data = {
            "choices": [
                {
                    "message": {
                        "role": "assistant",
                        "content": "I will classify your profile.",
                        "tool_calls": [
                            {
                                "id": "call_123",
                                "type": "function",
                                "function": {
                                    "name": "classify_user",
                                    "arguments": '{"user_type": "student", "from_country": "BD", "to_country": "CN"}',
                                },
                            }
                        ],
                    }
                }
            ]
        }

        async def mock_handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json=mock_response_data, request=request)

        transport = httpx.MockTransport(mock_handler)
        async with httpx.AsyncClient(transport=transport) as client:
            with patch.dict(os.environ, {"DEEPSEEK_API_KEY": "fake_test_key"}):
                res = await llm.call_llm(
                    messages=[{"role": "user", "content": "I am an international student."}],
                    client=client,
                )
                self.assertEqual(res["role"], "assistant")
                self.assertEqual(len(res["tool_calls"]), 1)
                self.assertEqual(res["tool_calls"][0]["function"]["name"], "classify_user")

    async def test_call_llm_malformed_response_raises(self):
        async def mock_handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json={"unexpected": []}, request=request)

        transport = httpx.MockTransport(mock_handler)
        async with httpx.AsyncClient(transport=transport) as client:
            with patch.dict(os.environ, {"DEEPSEEK_API_KEY": "fake_test_key"}):
                with self.assertRaises(llm.ProviderUnavailableError):
                    await llm.call_llm([{"role": "user", "content": "Hi"}], client=client)

    async def test_call_llm_retry_on_server_error_and_log_audit(self):
        calls = 0

        async def mock_handler(request: httpx.Request) -> httpx.Response:
            nonlocal calls
            calls += 1
            if calls == 1:
                return httpx.Response(503, text="Service Unavailable", request=request)
            return httpx.Response(
                200,
                json={"choices": [{"message": {"role": "assistant", "content": "Recovered!"}}]},
                request=request,
            )

        transport = httpx.MockTransport(mock_handler)
        async with httpx.AsyncClient(transport=transport) as client:
            with patch.dict(os.environ, {"DEEPSEEK_API_KEY": "fake_test_key"}):
                res = await llm.call_llm(
                    messages=[{"role": "user", "content": "Retry test"}],
                    session=self.session,
                    client=client,
                )
                self.assertEqual(res["content"], "Recovered!")
                self.assertEqual(calls, 2)

                # Verify audit event logged for retry
                retry_log = await AuditLog.objects.filter(session=self.session, action="llm_retry").afirst()
                self.assertIsNotNone(retry_log)
                self.assertEqual(retry_log.status, "retry")

    async def test_call_llm_exhausted_retries_raises(self):
        async def mock_handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(500, text="Internal Server Error", request=request)

        transport = httpx.MockTransport(mock_handler)
        async with httpx.AsyncClient(transport=transport) as client:
            with patch.dict(os.environ, {"DEEPSEEK_API_KEY": "fake_test_key"}):
                with self.assertRaises(llm.ProviderUnavailableError):
                    await llm.call_llm([{"role": "user", "content": "Fail test"}], client=client)


class VisionClientTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="vision_tester", email="vision@example.com")
        self.session = Session.objects.create(user=self.user, corridor="BD-CN")

    async def test_call_vision_missing_api_key_returns_fallback(self):
        with patch.dict(os.environ, {"GEMINI_API_KEY": ""}):
            res = await llm.call_vision(b"dummy image bytes", "Extract invoice details")
            self.assertEqual(res["doc_type"], "unknown")
            self.assertTrue(res["requires_confirmation"])

    async def test_call_vision_success_with_mock_client(self):
        mock_response_data = {
            "choices": [
                {
                    "message": {
                        "role": "assistant",
                        "content": '{"doc_type": "university_fee_invoice", "university": "SZU", "amount": 45000, "currency": "CNY"}',
                    }
                }
            ]
        }

        async def mock_handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json=mock_response_data, request=request)

        transport = httpx.MockTransport(mock_handler)
        async with httpx.AsyncClient(transport=transport) as client:
            with patch.dict(os.environ, {"GEMINI_API_KEY": "fake_vision_key"}):
                res = await llm.call_vision(
                    b"dummy image bytes",
                    "Extract invoice data",
                    client=client,
                )
                self.assertIn("university_fee_invoice", res["content"])

    async def test_call_vision_retry_on_network_error(self):
        calls = 0

        async def mock_handler(request: httpx.Request) -> httpx.Response:
            nonlocal calls
            calls += 1
            if calls == 1:
                raise httpx.ConnectTimeout("Connection timeout")
            return httpx.Response(
                200,
                json={"choices": [{"message": {"role": "assistant", "content": "Vision recovered"}}]},
                request=request,
            )

        transport = httpx.MockTransport(mock_handler)
        async with httpx.AsyncClient(transport=transport) as client:
            with patch.dict(os.environ, {"GEMINI_API_KEY": "fake_vision_key"}):
                res = await llm.call_vision(
                    b"dummy image bytes",
                    "Extract details",
                    session=self.session,
                    client=client,
                )
                self.assertEqual(res["content"], "Vision recovered")
                self.assertEqual(calls, 2)
                retry_log = await AuditLog.objects.filter(session=self.session, action="vision_retry").afirst()
                self.assertIsNotNone(retry_log)
