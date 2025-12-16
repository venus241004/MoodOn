# accounts/validators.py

import re


def validate_password_policy(password: str) -> None:
    """
    비밀번호 정책 위반 시 ValueError 발생.

    - 길이: 6~16자
    - 영문/숫자/특수문자 중 2종류 이상 포함
    - 연속 숫자 / 동일 숫자 반복 금지
    - 연속 영문 / 동일 영문 반복 금지
    """

    if len(password) < 6 or len(password) > 16:
        raise ValueError("비밀번호는 6~16자여야 합니다.")

    has_alpha = bool(re.search(r"[A-Za-z]", password))
    has_digit = bool(re.search(r"\d", password))
    has_special = bool(re.search(r"[!?~@#$%&^]", password))

    types = sum([has_alpha, has_digit, has_special])
    if types < 2:
        raise ValueError("영문, 숫자, 특수문자 중 2종류 이상을 포함해야 합니다.")

    # 연속 숫자
    if re.search(r"(0123|1234|2345|3456|4567|5678|6789)", password):
        raise ValueError("연속된 숫자는 사용할 수 없습니다.")
    # 동일 숫자 3회 이상 반복
    if re.search(r"(\d)\1\1", password):
        raise ValueError("동일 숫자 반복은 사용할 수 없습니다.")

    low = password.lower()
    # 연속 영문
    if re.search(r"(abcd|bcde|cdef|defg|efgh|fghi|ghij)", low):
        raise ValueError("연속된 영문은 사용할 수 없습니다.")
    # 동일 영문 반복
    if re.search(r"([a-z])\1\1", low):
        raise ValueError("동일 영문 반복은 사용할 수 없습니다.")
