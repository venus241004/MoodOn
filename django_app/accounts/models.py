# accounts.models.py

from datetime import timedelta

from django.contrib.auth.models import AbstractUser, UserManager as DjangoUserManager
from django.db import models
from django.utils import timezone


class UserManager(DjangoUserManager):
    """email을 아이디로 사용하는 User용 매니저."""

    use_in_migrations = True

    def _create_user(self, email, password, **extra_fields):
        if not email:
            raise ValueError("이메일은 필수입니다.")
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_user(self, email, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", False)
        extra_fields.setdefault("is_superuser", False)
        return self._create_user(email, password, **extra_fields)

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)

        if extra_fields.get("is_staff") is not True:
            raise ValueError("Superuser must have is_staff=True.")
        if extra_fields.get("is_superuser") is not True:
            raise ValueError("Superuser must have is_superuser=True.")

        return self._create_user(email, password, **extra_fields)


class User(AbstractUser):
    """이메일을 아이디로 사용하는 커스텀 유저."""

    username = None
    email = models.EmailField(unique=True)

    # 로그인 잠금 관련
    failed_login_count = models.IntegerField(default=0)
    lock_until = models.DateTimeField(null=True, blank=True)

    # 선호도 설문용 기본 정보
    birth_date = models.DateField(null=True, blank=True)
    gender = models.CharField(max_length=10, null=True, blank=True)
    mbti = models.CharField(max_length=4, null=True, blank=True)

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS: list[str] = []

    objects = UserManager()

    def __str__(self) -> str:
        return self.email

    @property
    def is_locked(self) -> bool:
        """로그인 잠금 여부."""
        if self.lock_until and self.lock_until > timezone.now():
            return True
        return False

    def register_failed_login(self, max_failed: int = 5, lock_minutes: int = 10) -> None:
        """로그인 실패 시 카운트 증가 및 잠금 처리."""
        now = timezone.now()
        # 잠금이 풀린 뒤라면 카운트 리셋
        if self.lock_until and self.lock_until <= now:
            self.failed_login_count = 0
            self.lock_until = None

        self.failed_login_count += 1
        if self.failed_login_count >= max_failed:
            self.lock_until = now + timedelta(minutes=lock_minutes)

        self.save(update_fields=["failed_login_count", "lock_until"])

    def reset_login_lock(self) -> None:
        """성공적인 로그인 시 잠금 정보 초기화."""
        self.failed_login_count = 0
        self.lock_until = None
        self.save(update_fields=["failed_login_count", "lock_until"])


class EmailVerification(models.Model):
    """
    이메일 인증 코드 (회원가입/비밀번호 재설정 공용).

    - purpose: "signup" 또는 "reset"
    - code: 8자리 영문+숫자
    - 3분 유효
    - 같은 목적의 코드 전송은 5회까지, 이후 10분 잠금
    - 항상 가장 최근에 생성된 레코드만 유효하게 사용
    """

    PURPOSE_CHOICES = [
        ("signup", "회원가입"),
        ("reset", "비밀번호 재설정"),
    ]

    email = models.EmailField()
    purpose = models.CharField(max_length=10, choices=PURPOSE_CHOICES)
    code = models.CharField(max_length=8)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    is_used = models.BooleanField(default=False)

    # 전송/잠금 제어
    send_count = models.IntegerField(default=0)
    lock_until = models.DateTimeField(null=True, blank=True)
    verified_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        indexes = [
            models.Index(fields=["email", "purpose", "-created_at"]),
        ]

    def __str__(self) -> str:
        return f"{self.email} ({self.purpose}) - {self.code}"

    @property
    def is_expired(self) -> bool:
        return timezone.now() > self.expires_at

    @classmethod
    def create_new(cls, email: str, purpose: str, code: str) -> "EmailVerification":
        """새 인증 코드 생성 + 전송 카운트/잠금 제어."""
        now = timezone.now()

        # 같은 이메일/목적에 대한 가장 최근 레코드 조회
        latest = cls.objects.filter(email=email, purpose=purpose).order_by("-created_at").first()

        send_count = 1
        lock_until = None

        if latest:
            # 잠금 중이면 차단
            if latest.lock_until and latest.lock_until > now:
                raise ValueError("인증 번호 요청이 제한되었습니다. 10분 후 다시 시도해 주세요.")

            # 잠금이 풀렸다면 카운트 리셋
            if latest.lock_until and latest.lock_until <= now:
                send_count = 1
            else:
                send_count = latest.send_count + 1

        # 5회 초과 시 10분 잠금 부여 후 요청 거절
        if send_count > 5:
            lock_until = now + timedelta(minutes=10)
            if latest:
                latest.send_count = 5
                latest.lock_until = lock_until
                latest.save(update_fields=["send_count", "lock_until"])
            raise ValueError("인증 번호 요청이 5회를 초과했습니다. 10분 후 다시 시도해 주세요.")

        return cls.objects.create(
            email=email,
            purpose=purpose,
            code=code,
            expires_at=now + timedelta(minutes=3),
            send_count=send_count,
            lock_until=lock_until,
        )

    @classmethod
    def get_latest_valid(cls, email: str, purpose: str) -> "EmailVerification | None":
        """가장 최근의 (미사용 & 미만료) 레코드."""
        now = timezone.now()
        return (
            cls.objects.filter(
                email=email,
                purpose=purpose,
                is_used=False,
                expires_at__gte=now,
            )
            .order_by("-created_at")
            .first()
        )

    def mark_verified(self) -> None:
        """성공적으로 검증되었을 때 호출."""
        self.is_used = True
        self.verified_at = timezone.now()
        self.save(update_fields=["is_used", "verified_at"])

    @classmethod
    def has_recent_verified(cls, email: str, purpose: str, minutes: int = 30) -> bool:
        """최근 N분 이내에 정상 인증된 기록이 있는지."""
        now = timezone.now()
        threshold = now - timedelta(minutes=minutes)
        return cls.objects.filter(
            email=email,
            purpose=purpose,
            is_used=True,
            verified_at__gte=threshold,
        ).exists()
