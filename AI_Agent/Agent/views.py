from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from .models import AgentUser
from django.contrib.auth.models import User




def register(request):
    if request.method == 'POST':
        username = request.POST['username']
        password = request.POST['password']
        full_name = request.POST['full_name']
        email = request.POST['email']
        bank_details = request.POST.get('bank_details', '{}')
        agent_details = request.POST.get('agent_details', '{}')

        if User.objects.filter(username=username).exists():
            messages.error(request, 'Username already exists.')
            return redirect('register')

        if User.objects.filter(email=email).exists():
            messages.error(request, 'Email already exists.')
            return redirect('register')

        user = User.objects.create_user(username=username, password=password, email=email)
        AgentUser.objects.create(user=user, Full_Name=full_name, bank_details=bank_details, agent_details=agent_details)

        messages.success(request, 'Registration successful. You can now log in.')
        return redirect('login')

    return render(request, 'Agent/register.html')

def login_view(request):
    if request.method == 'POST':
        username = request.POST['username']
        password = request.POST['password']
        user = authenticate(request, username=username, password=password)
        if user is not None:
            login(request, user)
            return redirect('dashboard')
        else:
            messages.error(request, 'Invalid username or password.')
            return redirect('login')

    return render(request, 'Agent/login.html')


def logout_view(request):
    logout(request)
    return redirect('login')



