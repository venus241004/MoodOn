/**
 * Sign Up Page Logic
 */

document.addEventListener('DOMContentLoaded', () => {
    // State
    let step = 1;
    let email = '';
    let verificationCode = '';
    let hasSentCode = false;
    let password = '';
    let confirmPassword = '';
    let termsAccepted = false;
    let privacyAccepted = false;
    let timeLeft = 0;
    let sendCount = 0;
    let isBlocked = false;
    let blockTimeLeft = 0;
    let resendCooldown = 0;
    let timerInterval = null;
    let blockTimerInterval = null;
    let resendTimerInterval = null;

    // Elements
    const progressContainer = document.getElementById('progress-container');
    const step1 = document.getElementById('step-1');
    const step2 = document.getElementById('step-2');
    const step3 = document.getElementById('step-3');

    // Step 1 Elements
    const termsCheck = document.getElementById('terms-check');
    const privacyCheck = document.getElementById('privacy-check');
    const btnViewTerms = document.getElementById('btn-view-terms');
    const btnViewPrivacy = document.getElementById('btn-view-privacy');
    const btnStep1Next = document.getElementById('btn-step-1-next');
    const popupTerms = document.getElementById('popup-terms');
    const popupPrivacy = document.getElementById('popup-privacy');

    // Step 2 Elements
    const emailInput = document.getElementById('email-input');
    const btnSendCode = document.getElementById('btn-send-code');
    const sendCountMsg = document.getElementById('send-count-msg');
    const verificationSection = document.getElementById('verification-section');
    const verificationCodeInput = document.getElementById('verification-code-input');
    const timerText = document.getElementById('timer-text');
    const step2Error = document.getElementById('step-2-error');
    const step2ErrorMsg = document.getElementById('step-2-error-msg');
    const btnStep2Prev = document.getElementById('btn-step-2-prev');
    const btnStep2Next = document.getElementById('btn-step-2-next');
    const popupCodeSent = document.getElementById('popup-code-sent');
    const popupCodeDisplay = document.getElementById('popup-code-display');
    const popupResendError = document.getElementById('popup-resend-error');
    const resendCooldownDisplay = document.getElementById('resend-cooldown-display');

    // Step 3 Elements
    const passwordInput = document.getElementById('password-input');
    const confirmPasswordInput = document.getElementById('confirm-password-input');
    const togglePasswordBtn = document.getElementById('toggle-password');
    const toggleConfirmPasswordBtn = document.getElementById('toggle-confirm-password');
    const step3Error = document.getElementById('step-3-error');
    const step3ErrorMsg = document.getElementById('step-3-error-msg');
    const btnStep3Prev = document.getElementById('btn-step-3-prev');
    const btnCompleteSignUp = document.getElementById('btn-complete-signup');
    const popupComplete = document.getElementById('popup-complete');

    // Helper Functions
    function updateProgress() {
        let html = '';
        for (let s = 1; s <= 4; s++) {
            const isActive = step >= s;
            const isCompleted = step > s;

            const circleClass = isActive
                ? 'bg-gradient-to-r from-blue-500 to-blue-400 text-white shadow-lg'
                : 'bg-gray-200 text-gray-400';

            const icon = isCompleted
                ? '<i data-lucide="check" class="w-4 h-4"></i>'
                : s;

            html += `
                <div class="w-8 h-8 rounded-full flex items-center justify-center transition-all text-sm ${circleClass}">
                    ${icon}
                </div>
            `;

            if (s < 4) {
                const lineClass = isCompleted
                    ? 'bg-gradient-to-r from-blue-500 to-blue-400'
                    : 'bg-gray-200';
                html += `<div class="w-12 h-1 mx-1.5 transition-all ${lineClass}"></div>`;
            }
        }
        progressContainer.innerHTML = html;
        lucide.createIcons();
    }

    function showStep(s) {
        step = s;
        step1.classList.add('hidden');
        step2.classList.add('hidden');
        step3.classList.add('hidden');

        if (s === 1) step1.classList.remove('hidden');
        if (s === 2) step2.classList.remove('hidden');
        if (s === 3) step3.classList.remove('hidden');

        updateProgress();
    }

    function showError(element, msgElement, msg) {
        msgElement.textContent = msg;
        element.classList.remove('hidden');
    }

    function hideError(element) {
        element.classList.add('hidden');
    }

    function validateEmail(email) {
        const regex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
        return regex.test(email);
    }

    function validatePassword(pwd) {
        if (pwd.length < 6 || pwd.length > 16) return '비밀번호는 6~16자로 입력해주세요.';

        const hasLetter = /[a-zA-Z]/.test(pwd);
        const hasNumber = /[0-9]/.test(pwd);
        const hasSpecial = /[!?~@#$%&^]/.test(pwd);
        const typesCount = [hasLetter, hasNumber, hasSpecial].filter(Boolean).length;

        if (typesCount < 2) return '영문, 숫자, 특수문자(!?~@#$%&^) 중 2종류 이상을 혼용해주세요.';
        if (/(\d)\1{2,}/.test(pwd)) return '연속되거나 동일한 숫자는 사용할 수 없습니다.';
        if (/012|123|234|345|456|567|678|789|987|876|765|654|543|432|321|210/.test(pwd)) return '연속되거나 동일한 숫자는 사용할 수 없습니다.';
        if (/([a-zA-Z])\1{2,}/.test(pwd)) return '연속되거나 동일한 문자는 사용할 수 없습니다.';
        if (/abc|bcd|cde|def|efg|fgh|ghi|hij|ijk|jkl|klm|lmn|mno|nop|opq|pqr|qrs|rst|stu|tuv|uvw|vwx|wxy|xyz|qwer|asdf|zxcv/.test(pwd.toLowerCase())) return '연속되거나 동일한 문자는 사용할 수 없습니다.';

        return '';
    }

    // Step 1 Logic
    function checkStep1Validity() {
        btnStep1Next.disabled = !(termsAccepted && privacyAccepted);
    }

    termsCheck.addEventListener('change', (e) => {
        termsAccepted = e.target.checked;
        checkStep1Validity();
    });

    privacyCheck.addEventListener('change', (e) => {
        privacyAccepted = e.target.checked;
        checkStep1Validity();
    });

    btnViewTerms.addEventListener('click', (e) => {
        e.preventDefault();
        popupTerms.classList.remove('hidden');
    });

    btnViewPrivacy.addEventListener('click', (e) => {
        e.preventDefault();
        popupPrivacy.classList.remove('hidden');
    });

    btnStep1Next.addEventListener('click', () => showStep(2));

    // Step 2 Logic
    function startTimer() {
        timeLeft = 180;
        updateTimerDisplay();
        if (timerInterval) clearInterval(timerInterval);
        timerInterval = setInterval(() => {
            timeLeft--;
            updateTimerDisplay();
            if (timeLeft <= 0) clearInterval(timerInterval);
        }, 1000);
    }

    function updateTimerDisplay() {
        const minutes = Math.floor(timeLeft / 60);
        const seconds = (timeLeft % 60).toString().padStart(2, '0');
        timerText.textContent = `${minutes}:${seconds}`;
    }

    function startResendCooldown() {
        resendCooldown = 10;
        if (resendTimerInterval) clearInterval(resendTimerInterval);
        resendTimerInterval = setInterval(() => {
            resendCooldown--;
            if (resendCooldown <= 0) clearInterval(resendTimerInterval);
        }, 1000);
    }

    btnSendCode.addEventListener('click', async () => {
        hideError(step2Error);
        email = emailInput.value;

        if (isBlocked) {
            const minutes = Math.floor(blockTimeLeft / 60);
            const seconds = (blockTimeLeft % 60).toString().padStart(2, '0');
            showError(step2Error, step2ErrorMsg, `10분 후 다시 시도해주세요. (${minutes}:${seconds})`);
            return;
        }

        if (!validateEmail(email)) {
            showError(step2Error, step2ErrorMsg, '올바른 이메일 형식이 아닙니다.');
            return;
        }

        if (sendCount > 0 && resendCooldown > 0) {
            resendCooldownDisplay.textContent = resendCooldown;
            popupResendError.classList.remove('hidden');
            return;
        }

        if (sendCount >= 5) {
            isBlocked = true;
            blockTimeLeft = 600;
            showError(step2Error, step2ErrorMsg, '인증번호 전송 횟수를 초과했습니다. 10분 후 다시 시도해주세요.');

            if (blockTimerInterval) clearInterval(blockTimerInterval);
            blockTimerInterval = setInterval(() => {
                blockTimeLeft--;
                if (blockTimeLeft <= 0) {
                    clearInterval(blockTimerInterval);
                    isBlocked = false;
                    sendCount = 0;
                    sendCountMsg.classList.add('hidden');
                }
            }, 1000);
            return;
        }

        try {
            btnSendCode.disabled = true;
            await fetchJson('/api/accounts/register/email/', {
                method: 'POST',
                body: { email }
            });
            hasSentCode = true;
            sendCount++;

            sendCountMsg.textContent = `발송 횟수: ${sendCount}/5`;
            sendCountMsg.classList.remove('hidden');

            startTimer();
            startResendCooldown();

            verificationSection.classList.remove('hidden');
            btnSendCode.textContent = '재발송';

            popupCodeSent.classList.remove('hidden');
        } catch (err) {
            const msg = err?.data?.detail || err?.message || '인증번호 발송에 실패했습니다.';
            showError(step2Error, step2ErrorMsg, msg);
        } finally {
            btnSendCode.disabled = false;
        }
    });

    verificationCodeInput.addEventListener('input', (e) => {
        verificationCode = e.target.value;
        btnStep2Next.disabled = !verificationCode || !hasSentCode;
    });

    btnStep2Next.addEventListener('click', async () => {
        hideError(step2Error);

        if (timeLeft <= 0) {
            showError(step2Error, step2ErrorMsg, '인증 시간이 만료되었습니다. 인증번호를 재발송해주세요.');
            return;
        }

        try {
            btnStep2Next.disabled = true;
            await fetchJson('/api/accounts/register/verify/', {
                method: 'POST',
                body: { email, code: verificationCode }
            });
            showStep(3);
        } catch (err) {
            const msg = err?.data?.detail || err?.message || '인증번호가 올바르지 않습니다.';
            showError(step2Error, step2ErrorMsg, msg);
        } finally {
            btnStep2Next.disabled = false;
        }
    });

    btnStep2Prev.addEventListener('click', () => showStep(1));

    // Step 3 Logic
    function togglePasswordVisibility(input, btn) {
        const type = input.getAttribute('type') === 'password' ? 'text' : 'password';
        input.setAttribute('type', type);
        const iconName = type === 'password' ? 'eye' : 'eye-off';
        btn.innerHTML = `<i data-lucide="${iconName}" class="w-[18px] h-[18px]"></i>`;
        lucide.createIcons();
    }

    togglePasswordBtn.addEventListener('click', () => togglePasswordVisibility(passwordInput, togglePasswordBtn));
    toggleConfirmPasswordBtn.addEventListener('click', () => togglePasswordVisibility(confirmPasswordInput, toggleConfirmPasswordBtn));

    function checkStep3Validity() {
        password = passwordInput.value;
        confirmPassword = confirmPasswordInput.value;
        btnCompleteSignUp.disabled = !password || !confirmPassword;
    }

    passwordInput.addEventListener('input', checkStep3Validity);
    confirmPasswordInput.addEventListener('input', checkStep3Validity);

    btnCompleteSignUp.addEventListener('click', async () => {
        hideError(step3Error);

        const pwdError = validatePassword(password);
        if (pwdError) {
            showError(step3Error, step3ErrorMsg, pwdError);
            return;
        }

        if (password !== confirmPassword) {
            showError(step3Error, step3ErrorMsg, '비밀번호가 일치하지 않습니다.');
            return;
        }

        try {
            btnCompleteSignUp.disabled = true;
            await fetchJson('/api/accounts/register/complete/', {
                method: 'POST',
                body: {
                    email,
                    password,
                    password2: confirmPassword,
                },
            });
            // Success
            step = 4;
            updateProgress();
            popupComplete.classList.remove('hidden');
        } catch (err) {
            const msg = err?.data?.detail || err?.message || '회원가입에 실패했습니다.';
            showError(step3Error, step3ErrorMsg, msg);
        } finally {
            btnCompleteSignUp.disabled = false;
        }
    });

    btnStep3Prev.addEventListener('click', () => showStep(2));

    // Initialize
    updateProgress();
});
