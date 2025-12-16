# accounts/urls.py

from django.urls import path

from . import views

app_name = "accounts"

api_urlpatterns = [
    # 회원가입 (이메일 인증)
    path("register/email/", views.SendSignupCodeView.as_view(), name="register-send-email"),
    path("register/verify/", views.VerifySignupCodeView.as_view(), name="register-verify"),
    path("register/complete/", views.RegisterView.as_view(), name="register-complete"),
    # 로그인/로그아웃
    path("login/", views.LoginView.as_view(), name="login"),
    path("logout/", views.LogoutView.as_view(), name="logout"),
    # 비밀번호 재설정
    path("password/reset/email/", views.PasswordResetRequestView.as_view(), name="password-reset-email"),
    path("password/reset/verify/", views.PasswordResetVerifyView.as_view(), name="password-reset-verify"),
    path("password/reset/complete/", views.PasswordResetCompleteView.as_view(), name="password-reset-complete"),
    # 비밀번호 변경 (로그인 상태)
    path("password/change/", views.PasswordChangeView.as_view(), name="password-change"),
    # 회원 탈퇴
    path("delete/", views.DeleteAccountView.as_view(), name="delete-account"),
    # 세션 상태 확인
    path("session/", views.SessionStatusView.as_view(), name="session-status"),
]

# HTML 페이지용
web_urlpatterns = [
    path("", views.root_redirect, name="root-redirect"),
    path("login/", views.login_page, name="login-page"),
    path("signup/", views.signup_page, name="signup-page"),
    path("password/reset/", views.password_reset_page, name="password-reset-page"),
    path("password/change/", views.password_change_page, name="password-change-page"),
]

urlpatterns = api_urlpatterns

