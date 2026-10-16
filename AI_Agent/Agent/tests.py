import json
import re
from datetime import timedelta

from django.core import mail
from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from .models import AgentUser, AiAgentConversation, AiAgentQuestion, RegistrationOTP


@override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
class AuthenticationFlowTests(TestCase):
    def test_home_displays_login_and_registration_buttons(self):
        response = self.client.get(reverse('home'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'data-open-modal="login-modal"')
        self.assertContains(response, 'data-open-modal="register-modal"')

    def test_authenticated_home_keeps_recent_chats_visible(self):
        user = User.objects.create_user(
            username='student@example.com',
            email='student@example.com',
            password='Strong-test-password-123',
        )
        AgentUser.objects.create(user=user, Full_Name='Test Student', email=user.email)
        conversation = AiAgentConversation.objects.create(
            user=user,
            title='My saved tuition chat',
        )
        self.client.force_login(user)

        response = self.client.get(f"{reverse('home')}#features")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'aria-label="Chat history"')
        self.assertContains(response, 'title="My saved tuition chat"')
        conversation_url = response.context['conversations'][0].url
        self.assertContains(response, f'href="{conversation_url}"')
        self.assertNotContains(response, f'conversation_id={conversation.pk}"')

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

    def test_authenticated_pages_use_sidebar_instead_of_header(self):
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
        self.client.force_login(user)

        response = self.client.get(reverse('dashboard'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'id="app-sidebar"')
        self.assertContains(response, 'aria-label="Collapse sidebar"')
        self.assertContains(response, 'id="sidebar-resize-handle"')
        self.assertContains(response, 'aria-valuemin="220" aria-valuemax="420"')
        self.assertContains(response, 'id="new-chat-link"')
        self.assertContains(response, 'id="new-chat-link" href="/dashboard/" title="New chat" aria-current="page"')
        self.assertNotContains(response, '<span>Dashboard</span>')
        self.assertContains(response, 'id="account-menu-trigger"')
        self.assertContains(response, '<strong id="account-full-name">Test Student</strong>')
        self.assertContains(response, 'id="profile-modal"')
        self.assertContains(response, 'class="profile-layout"')
        self.assertContains(response, 'class="password-panel"')
        self.assertContains(response, 'id="password-form" action="/profile/change-password/"')
        self.assertNotContains(response, 'id="password-form" action="/profile/change-password/" method="post" data-password-form hidden')
        self.assertContains(response, 'id="profile-email" type="email" value="student@example.com" readonly')
        self.assertContains(response, 'href="/logout/">')
        self.assertContains(response, '>Reminders</span></a>')
        self.assertContains(response, '>Bank account</span></a>')
        self.assertContains(response, '>Payment history</span></a>')
        self.assertContains(response, 'id="assistant-question-form"')
        self.assertContains(response, 'placeholder="Ask anything"')
        self.assertNotContains(response, 'Ask the assistant')
        self.assertNotContains(response, '<header class="site-head">')

    def test_profile_can_be_updated_without_changing_email(self):
        user = User.objects.create_user(
            username='student@example.com',
            email='student@example.com',
            password='Strong-test-password-123',
        )
        profile = AgentUser.objects.create(
            user=user,
            Full_Name='Test Student',
            email='student@example.com',
            mobile_number='+8801712345678',
        )
        self.client.force_login(user)

        response = self.client.post(
            reverse('update_profile'),
            data=json.dumps({
                'full_name': '  Updated Student  ',
                'mobile_number': '+8801812345678',
            }),
            content_type='application/json',
            HTTP_ACCEPT='application/json',
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()['success'])
        profile.refresh_from_db()
        self.assertEqual(profile.Full_Name, 'Updated Student')
        self.assertEqual(profile.mobile_number, '+8801812345678')
        self.assertEqual(user.email, 'student@example.com')
        self.assertEqual(profile.email, 'student@example.com')

    def test_password_change_requires_current_password_and_keeps_session(self):
        user = User.objects.create_user(
            username='student@example.com',
            email='student@example.com',
            password='Strong-test-password-123',
        )
        AgentUser.objects.create(user=user, Full_Name='Test Student', email=user.email)
        self.client.force_login(user)

        invalid_response = self.client.post(
            reverse('change_password'),
            data=json.dumps({
                'current_password': 'wrong-password',
                'new_password': 'Another-Strong-password-456',
                'confirm_password': 'Another-Strong-password-456',
            }),
            content_type='application/json',
            HTTP_ACCEPT='application/json',
        )
        self.assertEqual(invalid_response.status_code, 400)
        self.assertFalse(invalid_response.json()['success'])

        response = self.client.post(
            reverse('change_password'),
            data=json.dumps({
                'current_password': 'Strong-test-password-123',
                'new_password': 'Another-Strong-password-456',
                'confirm_password': 'Another-Strong-password-456',
            }),
            content_type='application/json',
            HTTP_ACCEPT='application/json',
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()['success'])
        user.refresh_from_db()
        self.assertTrue(user.check_password('Another-Strong-password-456'))
        self.assertEqual(self.client.get(reverse('dashboard')).status_code, 200)

    def test_authenticated_user_can_submit_question_and_see_it_in_dashboard(self):
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
        self.client.force_login(user)

        response = self.client.post(
            reverse('submit_ai_question'),
            data=json.dumps({'question_text': '  Can I afford a flat near campus?  '}),
            content_type='application/json',
            HTTP_ACCEPT='application/json',
        )

        self.assertEqual(response.status_code, 201)
        self.assertTrue(response.json()['success'])
        conversation = AiAgentConversation.objects.get()
        question = AiAgentQuestion.objects.get()
        self.assertEqual(question.user, user)
        self.assertEqual(question.question_text, 'Can I afford a flat near campus?')
        self.assertEqual(question.conversation, conversation)
        self.assertEqual(conversation.title, 'Can I afford a flat near campus?')
        follow_up = self.client.post(
            reverse('submit_ai_question'),
            data=json.dumps({
                'question_text': 'What about utilities?',
                'conversation_id': response.json()['conversation']['id'],
            }),
            content_type='application/json',
            HTTP_ACCEPT='application/json',
        )
        self.assertEqual(follow_up.status_code, 201)
        self.assertEqual(AiAgentConversation.objects.count(), 1)
        self.assertEqual(conversation.questions.count(), 2)
        dashboard_response = self.client.get(response.json()['conversation']['url'])
        self.assertContains(dashboard_response, 'Can I afford a flat near campus?')
        self.assertContains(dashboard_response, 'What about utilities?')
        self.assertContains(dashboard_response, 'Recent chats')

    def test_new_chat_starts_empty_and_saved_chat_survives_relogin(self):
        user = User.objects.create_user(
            username='student@example.com',
            email='student@example.com',
            password='Strong-test-password-123',
        )
        AgentUser.objects.create(user=user, Full_Name='Test Student', email=user.email)
        conversation = AiAgentConversation.objects.create(user=user, title='My first question')
        AiAgentQuestion.objects.create(
            user=user,
            conversation=conversation,
            question_text='My first question',
        )
        self.client.force_login(user)

        selected = self.client.get(
            reverse('dashboard'),
            {'conversation_id': conversation.pk},
        )
        self.assertContains(selected, 'My first question')
        token = selected.context['conversation_token']
        conversation_url = selected.context['conversations'][0].url
        self.assertContains(selected, f'data-conversation-id="{token}"')
        self.assertContains(
            selected,
            f'<a class="sidebar-link active" href="{conversation_url}"',
        )
        self.assertNotContains(selected, f'conversation_id={conversation.pk}"')
        self.assertNotContains(
            selected,
            'id="new-chat-link" href="/dashboard/" title="New chat" aria-current="page"',
        )

        self.client.get(reverse('logout'))
        self.client.force_login(user)
        new_chat = self.client.get(reverse('dashboard'))
        self.assertNotContains(
            new_chat,
            '<div class="assistant-message user">My first question</div>',
        )
        self.assertContains(new_chat, 'title="My first question"')
        self.assertContains(new_chat, 'id="new-chat-link" href="/dashboard/" title="New chat" aria-current="page"')
        self.assertNotContains(
            new_chat,
            f'<a class="sidebar-link active" href="{conversation_url}"',
        )

    def test_hashed_conversation_url_loads_chat_and_is_used_for_submission(self):
        user = User.objects.create_user(
            username='student@example.com',
            email='student@example.com',
            password='Strong-test-password-123',
        )
        AgentUser.objects.create(user=user, Full_Name='Test Student', email=user.email)
        conversation = AiAgentConversation.objects.create(user=user, title='Existing chat')
        self.client.force_login(user)
        dashboard_response = self.client.get(reverse('dashboard'))
        conversation_token = dashboard_response.context['conversations'][0].token
        conversation_url = dashboard_response.context['conversations'][0].url

        self.assertNotIn(f'conversation_id={conversation.pk}', conversation_url)
        selected_chat = self.client.get(conversation_url)
        self.assertEqual(selected_chat.status_code, 200)
        self.assertEqual(selected_chat.context['conversation'], conversation)
        self.assertContains(
            selected_chat,
            f'data-conversation-id="{conversation_token}"',
        )

        submit_response = self.client.post(
            reverse('submit_ai_question'),
            data=json.dumps({
                'question_text': 'Continue this chat',
                'conversation_id': conversation_token,
            }),
            content_type='application/json',
            HTTP_ACCEPT='application/json',
        )
        self.assertEqual(submit_response.status_code, 201)
        self.assertEqual(submit_response.json()['conversation']['id'], conversation_token)
        self.assertEqual(submit_response.json()['conversation']['url'], conversation_url)

    def test_conversation_selection_and_question_submission_are_user_scoped(self):
        user = User.objects.create_user(username='student@example.com', email='student@example.com')
        other_user = User.objects.create_user(username='other@example.com', email='other@example.com')
        AgentUser.objects.create(user=user, Full_Name='Test Student', email=user.email)
        conversation = AiAgentConversation.objects.create(user=other_user, title='Private chat')
        self.client.force_login(user)

        page_response = self.client.get(
            reverse('dashboard'),
            {'conversation_id': conversation.pk},
        )
        submit_response = self.client.post(
            reverse('submit_ai_question'),
            data=json.dumps({
                'question_text': 'A question',
                'conversation_id': conversation.pk,
            }),
            content_type='application/json',
            HTTP_ACCEPT='application/json',
        )

        self.assertEqual(page_response.status_code, 404)
        self.assertEqual(submit_response.status_code, 404)
        self.assertEqual(AiAgentQuestion.objects.count(), 0)

    def test_anonymous_user_cannot_submit_ai_question(self):
        response = self.client.post(
            reverse('submit_ai_question'),
            data=json.dumps({'question_text': 'A question'}),
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(AiAgentQuestion.objects.count(), 0)

    def test_empty_ai_question_is_rejected(self):
        user = User.objects.create_user(
            username='student@example.com',
            email='student@example.com',
            password='Strong-test-password-123',
        )
        self.client.force_login(user)

        response = self.client.post(
            reverse('submit_ai_question'),
            data=json.dumps({'question_text': '   '}),
            content_type='application/json',
            HTTP_ACCEPT='application/json',
        )

        self.assertEqual(response.status_code, 400)
        self.assertFalse(response.json()['success'])
        self.assertEqual(AiAgentQuestion.objects.count(), 0)

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
