import json

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from .models import AgentUser


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

    def test_registration_creates_user_and_agent_profile_from_json(self):
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
        user = User.objects.get(username='student@example.com')
        self.assertTrue(user.check_password('Strong-test-password-123'))
        profile = AgentUser.objects.get(user=user)
        self.assertEqual(profile.Full_Name, 'Test Student')
        self.assertEqual(profile.email, 'student@example.com')
        self.assertEqual(profile.mobile_number, '+8801712345678')

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
