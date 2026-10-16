from django.urls import path
from . import views


urlpatterns = [
    path('', views.home, name='home'),
    path('dashboard/', views.dashboard, name='dashboard'),
    path('login/', views.login_view, name='login'),
    path('register/', views.register, name='register'),
    path('register/verify/', views.verify_registration, name='verify_registration'),
    path('register/resend-otp/', views.resend_registration_otp, name='resend_registration_otp'),
    path('logout/', views.logout_view, name='logout'),
]