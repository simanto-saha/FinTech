import json
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.db import IntegrityError, transaction
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme

from .models import AgentUser


def home(request):
    return render(request, 'Agent/index.html')


@login_required(login_url='login')
def dashboard(request):
    agent_user = AgentUser.objects.get(user=request.user)
    return render(request, 'Agent/dashboard.html', {'agent_user': agent_user})


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

    full_name = data['full_name'].strip()
    email = data['email'].strip().lower()
    password = data.get('password', '')
    confirm_password = data.get('confirm_password', '')

    if not full_name or not email or not password or not confirm_password:
        return _auth_error(request, 'Please complete all registration fields.')
    if password != confirm_password:
        return _auth_error(request, 'Passwords do not match.')
    if (
        User.objects.filter(email__iexact=email).exists()
        or User.objects.filter(username__iexact=email).exists()
        or AgentUser.objects.filter(email__iexact=email).exists()
    ):
        return _auth_error(request, 'An account with this email already exists.', status=409)

    try:
        with transaction.atomic():
            user = User.objects.create_user(username=email, email=email, password=password)
            AgentUser.objects.create(user=user, Full_Name=full_name, email=email)
    except IntegrityError:
        if (
            User.objects.filter(email__iexact=email).exists()
            or User.objects.filter(username__iexact=email).exists()
            or AgentUser.objects.filter(email__iexact=email).exists()
        ):
            return _auth_error(request, 'An account with this email already exists.', status=409)
        raise

    message = 'Registration successful. Please log in.'
    if _json_requested(request):
        return JsonResponse({'success': True, 'message': message})
    messages.success(request, message)
    return redirect('home')


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
