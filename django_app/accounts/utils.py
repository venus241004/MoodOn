# accounts/utils.py
from django.conf import settings
from django.core.mail import send_mail


def send_verification_email(email: str, code: str, purpose: str) -> None:
    """인증 코드 이메일 발송."""

    if purpose == "signup":
        subject = "[MoodOn] 회원가입 이메일 인증 코드"
    elif purpose == "reset":
        subject = "[MoodOn] 비밀번호 재설정 인증 코드"
    else:
        subject = "[MoodOn] 이메일 인증 코드"

    message = (
        "MoodOn 이메일 인증 코드: {code}\n\n"
        "3분 이내에 인증을 완료해 주세요.\n"
        "이 코드는 회원가입 및 비밀번호 재설정에 사용됩니다."
    ).format(code=code)

    from_email = getattr(settings, "DEFAULT_FROM_EMAIL", None) or "no-reply@example.com"

    send_mail(
        subject=subject,
        message=message,
        from_email=from_email,
        recipient_list=[email],
        fail_silently=False,
    )

