/**
 * Login Page Logic
 */

document.addEventListener('DOMContentLoaded', () => {
    const emailInput = document.getElementById('email');
    const passwordInput = document.getElementById('password');
    const loginButton = document.getElementById('login-button');
    const togglePasswordBtn = document.getElementById('togglePassword');
    const errorContainer = document.getElementById('error-container');
    const errorMessage = document.getElementById('error-message');

    // Toggle Password Visibility
    togglePasswordBtn.addEventListener('click', () => {
        const type = passwordInput.getAttribute('type') === 'password' ? 'text' : 'password';
        passwordInput.setAttribute('type', type);

        const iconName = type === 'password' ? 'eye' : 'eye-off';
        togglePasswordBtn.innerHTML = `<i data-lucide="${iconName}" class="w-[18px] h-[18px]"></i>`;
        lucide.createIcons();
    });

    function validateEmail(email) {
        const regex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
        return regex.test(email);
    }

    function showError(msg) {
        errorMessage.textContent = msg;
        errorContainer.classList.remove('hidden');
    }

    function hideError() {
        errorContainer.classList.add('hidden');
    }

    function getNextUrl() {
        const params = new URLSearchParams(window.location.search);
        const next = params.get('next');
        if (next && next.startsWith('/')) return next;
        return '/chat/';
    }

    async function handleLogin() {
        hideError();

        const email = emailInput.value.trim();
        const password = passwordInput.value;

        if (!validateEmail(email)) {
            showError('올바른 이메일 형식이 아닙니다.');
            return;
        }

        if (!email || !password) {
            showError('이메일과 비밀번호를 입력해주세요.');
            return;
        }

        loginButton.disabled = true;
        loginButton.textContent = '로그인 중...';

        try {
            await Auth.login(email, password);
            window.location.href = getNextUrl();
        } catch (error) {
            showError(error.message || '로그인에 실패했습니다.');
        } finally {
            loginButton.disabled = false;
            loginButton.textContent = '로그인';
        }
    }

    loginButton.addEventListener('click', (e) => {
        e.preventDefault();
        handleLogin();
    });

    [emailInput, passwordInput].forEach(input => {
        input.addEventListener('keypress', (e) => {
            if (e.key === 'Enter') {
                e.preventDefault();
                handleLogin();
            }
        });
    });
});
