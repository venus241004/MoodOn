# acounts/serializers.py

from django.contrib.auth import get_user_model
from rest_framework import serializers

from .models import EmailVerification
from .validators import validate_password_policy

User = get_user_model()


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["id", "email", "birth_date", "gender", "mbti"]
        read_only_fields = ["id", "email"]


# ---------- 회원가입 ----------


class RegisterEmailSerializer(serializers.Serializer):
    email = serializers.EmailField()

    def validate_email(self, value):
        if User.objects.filter(email=value).exists():
            raise serializers.ValidationError("이미 가입된 이메일입니다.")
        return value


class RegisterVerifySerializer(serializers.Serializer):
    email = serializers.EmailField()
    code = serializers.CharField(max_length=8)

    def validate(self, attrs):
        email = attrs.get("email")
        code = attrs.get("code")

        ev = EmailVerification.get_latest_valid(email=email, purpose="signup")
        if not ev:
            raise serializers.ValidationError("유효한 인증 코드가 없습니다. 다시 요청해 주세요.")
        if ev.code != code:
            raise serializers.ValidationError("인증 코드가 올바르지 않습니다.")

        attrs["verification"] = ev
        return attrs


class RegisterSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)
    password2 = serializers.CharField(write_only=True)
    birth_date = serializers.DateField(required=False)
    gender = serializers.CharField(required=False, allow_blank=True)
    mbti = serializers.CharField(required=False, allow_blank=True)

    def validate(self, attrs):
        email = attrs.get("email")
        password = attrs.get("password")
        password2 = attrs.get("password2")

        if User.objects.filter(email=email).exists():
            raise serializers.ValidationError("이미 가입된 이메일입니다.")

        if password != password2:
            raise serializers.ValidationError("비밀번호와 비밀번호 확인이 일치하지 않습니다.")

        try:
            validate_password_policy(password)
        except ValueError as e:
            raise serializers.ValidationError({"password": str(e)})

        # 최근 30분 이내 인증 완료 여부 체크
        if not EmailVerification.has_recent_verified(email=email, purpose="signup", minutes=30):
            raise serializers.ValidationError("이메일 인증을 먼저 완료해 주세요.")

        return attrs

    def create(self, validated_data):
        email = validated_data["email"]
        password = validated_data["password"]
        birth_date = validated_data.get("birth_date")
        gender = validated_data.get("gender")
        mbti = validated_data.get("mbti")

        user = User.objects.create_user(
            email=email,
            password=password,
            birth_date=birth_date,
            gender=gender,
            mbti=mbti,
        )
        return user


# ---------- 로그인 / 로그아웃 ----------


class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)


# ---------- 비밀번호 재설정 ----------


class PasswordResetRequestSerializer(serializers.Serializer):
    email = serializers.EmailField()

    def validate_email(self, value):
        if not User.objects.filter(email=value).exists():
            raise serializers.ValidationError("가입되어 있지 않은 이메일입니다.")
        return value


class PasswordResetVerifySerializer(serializers.Serializer):
    email = serializers.EmailField()
    code = serializers.CharField(max_length=8)

    def validate(self, attrs):
        email = attrs.get("email")
        code = attrs.get("code")

        ev = EmailVerification.get_latest_valid(email=email, purpose="reset")
        if not ev:
            raise serializers.ValidationError("유효한 인증 코드가 없습니다. 다시 요청해 주세요.")
        if ev.code != code:
            raise serializers.ValidationError("인증 코드가 올바르지 않습니다.")

        attrs["verification"] = ev
        return attrs


class PasswordResetCompleteSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)
    password2 = serializers.CharField(write_only=True)

    def validate(self, attrs):
        email = attrs.get("email")
        password = attrs.get("password")
        password2 = attrs.get("password2")

        if password != password2:
            raise serializers.ValidationError("비밀번호와 비밀번호 확인이 일치하지 않습니다.")

        try:
            validate_password_policy(password)
        except ValueError as e:
            raise serializers.ValidationError({"password": str(e)})

        if not EmailVerification.has_recent_verified(email=email, purpose="reset", minutes=30):
            raise serializers.ValidationError("이메일 인증을 먼저 완료해 주세요.")

        if not User.objects.filter(email=email).exists():
            raise serializers.ValidationError({"email": "가입되어 있지 않은 이메일입니다."})

        return attrs


# ---------- 비밀번호 변경 (로그인 상태) ----------


class PasswordChangeSerializer(serializers.Serializer):
    old_password = serializers.CharField(write_only=True)
    password = serializers.CharField(write_only=True)
    password2 = serializers.CharField(write_only=True)

    def validate(self, attrs):
        user = self.context["request"].user
        old_password = attrs.get("old_password")
        password = attrs.get("password")
        password2 = attrs.get("password2")

        if not user.check_password(old_password):
            raise serializers.ValidationError({"old_password": "기존 비밀번호가 올바르지 않습니다."})

        if password != password2:
            raise serializers.ValidationError("비밀번호와 비밀번호 확인이 일치하지 않습니다.")

        if old_password == password:
            raise serializers.ValidationError({"password": "기존 비밀번호와 다른 비밀번호를 사용해야 합니다."})

        try:
            validate_password_policy(password)
        except ValueError as e:
            raise serializers.ValidationError({"password": str(e)})

        return attrs


class DeleteAccountSerializer(serializers.Serializer):
    password = serializers.CharField(write_only=True, required=False, allow_blank=True)

    def validate(self, attrs):
        user = self.context["request"].user
        password = attrs.get("password")
        # 비밀번호가 제공된 경우에만 검증, 없으면 통과
        if password:
            if not user.check_password(password):
                raise serializers.ValidationError({"password": "비밀번호가 올바르지 않습니다."})
        return attrs
