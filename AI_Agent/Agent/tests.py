import json
import re
from datetime import timedelta

from django.core import mail
from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from .models import AgentUser, RegistrationOTP


@override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
class AuthenticationFlowTests(TestCase):
    def test_home_displays_login_and_registration_buttons(self):
        response = self.client.get(reverse('home'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'data-open-modal="login-modal"')
        self.assertContains(response, 'data-open-modal="register-modal"')

    def test_anonymous_dashboard_request_redirects_to_login(self):
        response = self.client.get(reverse('dashboard'))

        self.assertEqual(response.status_code, 302)
        self.assertEqual(
            response.headers['Location'],
            f"{reverse('login')}?next={reverse('dashboard')}",
        )

        login_page = self.client.get(response.headers['Location'])
        self.assertEqual(login_page.status_code, 200)
        self.assertContains(login_page, 'id="login-modal"')

    def test_registration_sends_otp_without_creating_account_until_verified(self):
        response = self.client.post(
            reverse('register'),
            data=json.dumps({
                'full_name': 'Test Student',
                'email': 'student@example.com',
                'mobile_number': '+8801712345678',
                'password': 'Strong-test-password-123',
                'confirm_password': 'Strong-test-password-123',
            }),
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()['success'])
        self.assertEqual(response.json()['email'], 'student@example.com')
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn('student@example.com', mail.outbox[0].to)
        self.assertFalse(User.objects.filter(username='student@example.com').exists())
        registration = RegistrationOTP.objects.get(email='student@example.com')
        self.assertNotIn('Strong-test-password-123', registration.password_hash)
        self.assertNotIn(
            re.search(r'code is (\d{6})', mail.outbox[0].body).group(1),
            registration.otp_hash,
        )

        otp = re.search(r'code is (\d{6})', mail.outbox[0].body).group(1)
        verify_response = self.client.post(
            reverse('verify_registration'),
            data=json.dumps({'email': 'student@example.com', 'otp': otp}),
            content_type='application/json',
        )

        self.assertEqual(verify_response.status_code, 200)
        self.assertTrue(verify_response.json()['success'])
        user = User.objects.get(username='student@example.com')
        self.assertTrue(user.check_password('Strong-test-password-123'))
        profile = AgentUser.objects.get(user=user)
        self.assertEqual(profile.Full_Name, 'Test Student')
        self.assertEqual(profile.email, 'student@example.com')
        self.assertEqual(profile.mobile_number, '+8801712345678')
        self.assertFalse(RegistrationOTP.objects.filter(email='student@example.com').exists())

    def test_invalid_otp_does_not_create_account_and_counts_attempt(self):
        self.client.post(
            reverse('register'),
            data=json.dumps({
                'full_name': 'Test Student',
                'email': 'student@example.com',
                'password': 'Strong-test-password-123',
                'confirm_password': 'Strong-test-password-123',
            }),
            content_type='application/json',
        )

        correct_otp = re.search(r'code is (\d{6})', mail.outbox[0].body).group(1)
        wrong_otp = f'{(int(correct_otp) + 1) % 1_000_000:06d}'
        response = self.client.post(
            reverse('verify_registration'),
            data=json.dumps({'email': 'student@example.com', 'otp': wrong_otp}),
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 400)
        self.assertFalse(User.objects.filter(username='student@example.com').exists())
        self.assertEqual(RegistrationOTP.objects.get(email='student@example.com').attempts, 1)

    def test_expired_otp_cannot_create_account(self):
        self.client.post(
            reverse('register'),
            data=json.dumps({
                'full_name': 'Test Student',
                'email': 'student@example.com',
                'password': 'Strong-test-password-123',
                'confirm_password': 'Strong-test-password-123',
            }),
            content_type='application/json',
        )
        registration = RegistrationOTP.objects.get(email='student@example.com')
        registration.expires_at = timezone.now() - timedelta(seconds=1)
        registration.save(update_fields=['expires_at'])
        otp = re.search(r'code is (\d{6})', mail.outbox[0].body).group(1)

        response = self.client.post(
            reverse('verify_registration'),
            data=json.dumps({'email': 'student@example.com', 'otp': otp}),
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 400)
        self.assertFalse(User.objects.filter(username='student@example.com').exists())

    def test_json_login_authenticates_user_and_returns_dashboard_url(self):
        user = User.objects.create_user(
            username='student@example.com',
            email='student@example.com',
            password='Strong-test-password-123',
        )
        AgentUser.objects.create(
            user=user,
            Full_Name='Test Student',
            email='student@example.com',
        )

        response = self.client.post(
            reverse('login'),
            data=json.dumps({
                'email': 'student@example.com',
                'password': 'Strong-test-password-123',
            }),
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()['success'])
        self.assertEqual(response.json()['redirect_url'], reverse('dashboard'))
        self.assertEqual(self.client.get(reverse('dashboard')).status_code, 200)
