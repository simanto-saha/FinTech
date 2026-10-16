import json
import logging
import secrets
from datetime import timedelta
from smtplib import SMTPException

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout, update_session_auth_hash
from django.contrib.auth.hashers import check_password, make_password
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.contrib.auth.password_validation import validate_password
from django.db import IntegrityError, transaction
from django.core.exceptions import ValidationError
from django.core.mail import send_mail
from django.http import Http404, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.http import urlencode
from hashids import Hashids
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme

from .models import AgentUser, AiAgentConversation, AiAgentQuestion, RegistrationOTP


logger = logging.getLogger(__name__)
OTP_LIFETIME = timedelta(minutes=10)
OTP_RESEND_DELAY = timedelta(seconds=60)
OTP_MAX_ATTEMPTS = 5
CONVERSATION_ID_HASH = Hashids(salt=settings.SECRET_KEY, min_length=8)


def _conversation_token(conversation_id):
    return CONVERSATION_ID_HASH.encode(conversation_id)


def _conversation_url(conversation_id):
    token = _conversation_token(conversation_id)
    return f"{reverse('dashboard')}?{urlencode({'conversation_id': token})}"


def _conversation_pk_from_token(token):
    if not isinstance(token, str):
        raise Http404
    if token.isdecimal():
        return int(token)
    decoded_ids = CONVERSATION_ID_HASH.decode(token)
    if len(decoded_ids) != 1:
        raise Http404
    return decoded_ids[0]


def home(request):
    context = {}
    if request.user.is_authenticated:
        conversations = list(AiAgentConversation.objects.filter(user=request.user)[:30])
        for item in conversations:
            item.token = _conversation_token(item.pk)
            item.url = _conversation_url(item.pk)
        context = {
            'agent_user': AgentUser.objects.get(user=request.user),
            'conversation': None,
            'conversations': conversations,
        }
    return render(request, 'Agent/index.html', context)


@login_required(login_url='login')
def dashboard(request):
    agent_user = AgentUser.objects.get(user=request.user)
    conversation = None
    conversation_token = request.GET.get('conversation_id')
    if conversation_token:
        conversation = get_object_or_404(
            AiAgentConversation,
            pk=_conversation_pk_from_token(conversation_token),
            user=request.user,
        )

    questions = (
        list(conversation.questions.order_by('created_at', 'pk'))
        if conversation
        else []
    )
    conversations = list(AiAgentConversation.objects.filter(user=request.user)[:30])
    for item in conversations:
        item.token = _conversation_token(item.pk)
        item.url = _conversation_url(item.pk)
    return render(
        request,
        'Agent/dashboard.html',
        {
            'agent_user': agent_user,
            'questions': questions,
            'conversation': conversation,
            'conversation_token': _conversation_token(conversation.pk) if conversation else '',
            'conversations': conversations,
        },
    )

# This is AI Agent Question Submission View
@login_required(login_url='login')
def submit_ai_question(request):
    if request.method != 'POST':
        return JsonResponse(
            {'success': False, 'message': 'POST is required.'},
            status=405,
        )

    data = _request_data(request)
    if data is None:
        return JsonResponse(
            {'success': False, 'message': 'The submitted data is not valid JSON.'},
            status=400,
        )

    # Questions are here
    question_text = data.get('question_text')
    if not isinstance(question_text, str):
        return JsonResponse(
            {'success': False, 'message': 'Enter a question first.'},
            status=400,
        )

    question_text = question_text.strip()
    if not question_text:
        return JsonResponse(
            {'success': False, 'message': 'Enter a question first.'},
            status=400,
        )
    if len(question_text) > 4000:
        return JsonResponse(
            {'success': False, 'message': 'Keep your question under 4,000 characters.'},
            status=400,
        )

    conversation_id = data.get('conversation_id')
    with transaction.atomic():
        if conversation_id is None:
            conversation = AiAgentConversation.objects.create(
                user=request.user,
                title=question_text[:120],
            )
        elif isinstance(conversation_id, (int, str)) and not isinstance(conversation_id, bool):
            if isinstance(conversation_id, str):
                try:
                    conversation_pk = _conversation_pk_from_token(conversation_id)
                except Http404:
                    return JsonResponse(
                        {'success': False, 'message': 'The selected conversation is not valid.'},
                        status=400,
                    )
            else:
                conversation_pk = conversation_id
            conversation = get_object_or_404(
                AiAgentConversation,
                pk=conversation_pk,
                user=request.user,
            )
        else:
            return JsonResponse(
                {'success': False, 'message': 'The selected conversation is not valid.'},
                status=400,
            )

        conversation.save(update_fields=['updated_at'])
        question = AiAgentQuestion.objects.create(
            user=request.user,
            conversation=conversation,
            question_text=question_text,
        )

    return JsonResponse(
        {
            'success': True,
            'conversation': {
                'id': _conversation_token(conversation.pk),
                'title': conversation.title,
                'url': _conversation_url(conversation.pk),
            },
            'question': {
                'id': question.pk,
                'question_text': question.question_text,
                'created_at': question.created_at.isoformat(),
                'answer_text': question.answer_text,
            },
        },
        status=201,
    )


@login_required(login_url='login')
def update_profile(request):
    if request.method != 'POST':
        return JsonResponse(
            {'success': False, 'message': 'POST is required.'},
            status=405,
        )

    data = _request_data(request)
    if data is None:
        return JsonResponse(
            {'success': False, 'message': 'The submitted data is not valid JSON.'},
            status=400,
        )

    full_name = data.get('full_name')
    mobile_number = data.get('mobile_number', '')
    if not isinstance(full_name, str) or not isinstance(mobile_number, str):
        return JsonResponse(
            {'success': False, 'message': 'Please provide valid profile details.'},
            status=400,
        )

    full_name = full_name.strip()
    mobile_number = mobile_number.strip()
    if not full_name:
        return JsonResponse(
            {'success': False, 'message': 'Full name is required.'},
            status=400,
        )
    if len(full_name) > 100:
        return JsonResponse(
            {'success': False, 'message': 'Full name must be 100 characters or fewer.'},
            status=400,
        )
    if len(mobile_number) > 15:
        return JsonResponse(
            {'success': False, 'message': 'Mobile number must be 15 characters or fewer.'},
            status=400,
        )

    profile = get_object_or_404(AgentUser, user=request.user)
    profile.Full_Name = full_name
    profile.mobile_number = mobile_number or None
    profile.save(update_fields=['Full_Name', 'mobile_number'])
    return JsonResponse({
        'success': True,
        'message': 'Your profile has been updated.',
        'profile': {
            'full_name': profile.Full_Name,
            'email': request.user.email,
            'mobile_number': profile.mobile_number or '',
        },
    })


@login_required(login_url='login')
def change_password(request):
    if request.method != 'POST':
        return JsonResponse(
            {'success': False, 'message': 'POST is required.'},
            status=405,
        )

    data = _request_data(request)
    if data is None:
        return JsonResponse(
            {'success': False, 'message': 'The submitted data is not valid JSON.'},
            status=400,
        )

    current_password = data.get('current_password')
    new_password = data.get('new_password')
    confirm_password = data.get('confirm_password')
    if not all(isinstance(value, str) for value in (
        current_password,
        new_password,
        confirm_password,
    )):
        return JsonResponse(
            {'success': False, 'message': 'Please complete all password fields.'},
            status=400,
        )
    if not request.user.check_password(current_password):
        return JsonResponse(
            {'success': False, 'message': 'Your current password is incorrect.'},
            status=400,
        )
    if new_password != confirm_password:
        return JsonResponse(
            {'success': False, 'message': 'The new passwords do not match.'},
            status=400,
        )

    try:
        validate_password(new_password, user=request.user)
    except ValidationError as error:
        return JsonResponse(
            {'success': False, 'message': ' '.join(error.messages)},
            status=400,
        )

    request.user.set_password(new_password)
    request.user.save(update_fields=['password'])
    update_session_auth_hash(request, request.user)
    return JsonResponse({'success': True, 'message': 'Your password has been changed.'})


def _request_data(request):
    if request.content_type == 'application/json':
        try:
            data = json.loads(request.body or '{}')
        except json.JSONDecodeError:
            return None
        return data if isinstance(data, dict) else None
    return request.POST.dict()


def _json_requested(request):
    return (
        request.content_type == 'application/json'
        or 'application/json' in request.headers.get('Accept', '')
    )


def _auth_error(request, message, status=400):
    if _json_requested(request):
        return JsonResponse({'success': False, 'message': message}, status=status)
    messages.error(request, message)
    return redirect('home')


def _send_registration_otp(request, registration, code):
    try:
        sent_count = send_mail(
            subject='Your Pathway verification code',
            message=(
                f'Your Pathway verification code is {code}. '
                'It expires in 10 minutes. If you did not request this, ignore this email.'
            ),
            from_email=None,
            recipient_list=[registration.email],
            fail_silently=False,
        )
    except (OSError, SMTPException):
        logger.exception('Failed to send registration OTP to %s', registration.email)
        registration.delete()
        return _auth_error(
            request,
            'We could not send the verification email. Please try again later.',
            status=503,
        )

    if sent_count != 1:
        logger.error('Registration OTP email was not accepted for %s', registration.email)
        registration.delete()
        return _auth_error(
            request,
            'We could not send the verification email. Please try again later.',
            status=503,
        )
    return None


def register(request):
    if request.method != 'POST':
        return render(request, 'Agent/index.html', {'initial_auth_dialog': 'register-modal'})

    data = _request_data(request)
    if data is None:
        return _auth_error(request, 'The submitted data is not valid JSON.')

    if not all(
        isinstance(data.get(field), str)
        for field in ('full_name', 'email', 'password', 'confirm_password')
    ):
        return _auth_error(request, 'Please provide valid registration details.')
    if data.get('mobile_number') is not None and not isinstance(data['mobile_number'], str):
        return _auth_error(request, 'Please provide a valid mobile number.')

    full_name = data['full_name'].strip()
    email = data['email'].strip().lower()
    mobile_number = (data.get('mobile_number') or '').strip()
    password = data.get('password', '')
    confirm_password = data.get('confirm_password', '')

    if not full_name or not email or not password or not confirm_password:
        return _auth_error(request, 'Please complete all registration fields.')
    if len(mobile_number) > 15:
        return _auth_error(request, 'Mobile number must be 15 characters or fewer.')
    if password != confirm_password:
        return _auth_error(request, 'Passwords do not match.')
    try:
        User._meta.get_field('email').clean(email, None)
    except ValidationError:
        return _auth_error(request, 'Enter a valid email address.')

    if (
        User.objects.filter(email__iexact=email).exists()
        or User.objects.filter(username__iexact=email).exists()
        or AgentUser.objects.filter(email__iexact=email).exists()
    ):
        return _auth_error(request, 'An account with this email already exists.', status=409)

    code = f'{secrets.randbelow(1_000_000):06d}'
    now = timezone.now()
    existing_registration = RegistrationOTP.objects.filter(email=email).first()
    if (
        existing_registration is not None
        and now < existing_registration.last_sent_at + OTP_RESEND_DELAY
    ):
        return _auth_error(
            request,
            'A verification code was sent recently. Please wait before trying again.',
            status=429,
        )

    registration, _ = RegistrationOTP.objects.update_or_create(
        email=email,
        defaults={
            'full_name': full_name,
            'mobile_number': mobile_number or None,
            'password_hash': make_password(password),
            'otp_hash': make_password(code),
            'expires_at': now + OTP_LIFETIME,
            'attempts': 0,
            'last_sent_at': now,
        },
    )
    delivery_error = _send_registration_otp(request, registration, code)
    if delivery_error:
        return delivery_error

    message = 'We sent a verification code to your email address.'
    if _json_requested(request):
        return JsonResponse({'success': True, 'message': message, 'email': email})
    messages.success(request, message)
    return render(
        request,
        'Agent/index.html',
        {
            'initial_auth_dialog': 'verify-registration-modal',
            'verification_email': email,
        },
    )


def verify_registration(request):
    if request.method != 'POST':
        return JsonResponse({'success': False, 'message': 'POST is required.'}, status=405)

    data = _request_data(request)
    if data is None:
        return _auth_error(request, 'The submitted data is not valid JSON.')
    email = data.get('email')
    code = data.get('otp')
    if not isinstance(email, str) or not isinstance(code, str):
        return _auth_error(request, 'Enter the email address and verification code.')

    email = email.strip().lower()
    code = code.strip()
    if len(code) != 6 or not code.isdigit():
        return _auth_error(request, 'Enter the 6-digit verification code.')

    try:
        with transaction.atomic():
            registration = RegistrationOTP.objects.select_for_update().get(email=email)
            now = timezone.now()
            if registration.expires_at <= now:
                return _auth_error(request, 'This code has expired. Request a new code.')
            if registration.attempts >= OTP_MAX_ATTEMPTS:
                return _auth_error(request, 'Too many attempts. Request a new code.', status=429)
            if not check_password(code, registration.otp_hash):
                registration.attempts += 1
                registration.save(update_fields=['attempts'])
                return _auth_error(request, 'That verification code is incorrect.')

            user = User.objects.create(
                username=registration.email,
                email=registration.email,
                password=registration.password_hash,
            )
            AgentUser.objects.create(
                user=user,
                Full_Name=registration.full_name,
                email=registration.email,
                mobile_number=registration.mobile_number,
            )
            registration.delete()
    except RegistrationOTP.DoesNotExist:
        return _auth_error(request, 'No pending registration was found. Please register again.', status=404)
    except IntegrityError:
        if (
            User.objects.filter(email__iexact=email).exists()
            or User.objects.filter(username__iexact=email).exists()
            or AgentUser.objects.filter(email__iexact=email).exists()
        ):
            RegistrationOTP.objects.filter(email=email).delete()
            return _auth_error(request, 'An account with this email already exists.', status=409)
        raise

    message = 'Email verified. Your account has been created. You can now log in.'
    if _json_requested(request):
        return JsonResponse({'success': True, 'message': message, 'email': email})
    messages.success(request, message)
    return redirect('home')


def resend_registration_otp(request):
    if request.method != 'POST':
        return JsonResponse({'success': False, 'message': 'POST is required.'}, status=405)

    data = _request_data(request)
    if data is None:
        return _auth_error(request, 'The submitted data is not valid JSON.')
    email = data.get('email')
    if not isinstance(email, str) or not email.strip():
        return _auth_error(request, 'Enter the email address for this registration.')

    email = email.strip().lower()
    registration = RegistrationOTP.objects.filter(email=email).first()
    if registration is None:
        return _auth_error(request, 'No pending registration was found. Please register again.', status=404)

    now = timezone.now()
    next_send_at = registration.last_sent_at + OTP_RESEND_DELAY
    if now < next_send_at:
        retry_after = int((next_send_at - now).total_seconds()) + 1
        return JsonResponse(
            {'success': False, 'message': f'Please wait {retry_after} seconds before requesting another code.'},
            status=429,
        )

    code = f'{secrets.randbelow(1_000_000):06d}'
    registration.otp_hash = make_password(code)
    registration.expires_at = now + OTP_LIFETIME
    registration.attempts = 0
    registration.last_sent_at = now
    registration.save(update_fields=['otp_hash', 'expires_at', 'attempts', 'last_sent_at'])
    delivery_error = _send_registration_otp(request, registration, code)
    if delivery_error:
        return delivery_error

    return JsonResponse({'success': True, 'message': 'A new verification code has been sent.'})


def login_view(request):
    if request.method != 'POST':
        return render(request, 'Agent/index.html', {'initial_auth_dialog': 'login-modal'})

    data = _request_data(request)
    if data is None:
        return _auth_error(request, 'The submitted data is not valid JSON.')

    if not isinstance(data.get('email'), str) or not isinstance(data.get('password'), str):
        return _auth_error(request, 'Please provide a valid email and password.')

    email = data['email'].strip().lower()
    password = data['password']
    if not email or not password:
        return _auth_error(request, 'Please enter your email and password.')

    user = authenticate(request, username=email, password=password)
    if user is None:
        return _auth_error(request, 'Invalid email or password.', status=401)

    login(request, user)
    next_url = data.get('next', '')
    redirect_url = reverse('dashboard')
    if next_url and url_has_allowed_host_and_scheme(
        next_url,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    ):
        redirect_url = next_url

    if _json_requested(request):
        return JsonResponse({'success': True, 'redirect_url': redirect_url})
    return redirect(redirect_url)


def logout_view(request):
    logout(request)
    return redirect('home')
