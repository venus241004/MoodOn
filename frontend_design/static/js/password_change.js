/**
 * Password Change Page Logic
 */

document.addEventListener('DOMContentLoaded', () => {
    // Check Login
    if (!Auth.requireLogin()) return;

    // Elements
    const headerNav = document.getElementById('header-nav');
    const currentPasswordInput = document.getElementById('current-password');
    const newPasswordInput = document.getElementById('new-password');
    const confirmPasswordInput = document.getElementById('confirm-password');
    const toggleCurrentPasswordBtn = document.getElementById('toggle-current-password');
    const toggleNewPasswordBtn = document.getElementById('toggle-new-password');
    const toggleConfirmPasswordBtn = document.getElementById('toggle-confirm-password');
    const btnSubmit = document.getElementById('btn-submit');
    const errorMessage = document.getElementById('error-message');
    const errorText = document.getElementById('error-text');
    const popupSuccess = document.getElementById('popup-success');

    // Initialize
    renderHeaderNav();

    // Functions
    function renderHeaderNav() {
        headerNav.innerHTML = `
            <button onclick="window.location.href='/user/mypage/'" class="px-4 py-2 text-[15px] font-normal text-gray-700 hover:text-blue-600 hover:bg-blue-50 rounded-lg transition-all leading-none">마이페이지</button>
            <button onclick="window.location.href='/favorites/reference-board/'" class="px-4 py-2 text-[15px] font-normal text-gray-700 hover:text-blue-600 hover:bg-blue-50 rounded-lg transition-all leading-none">레퍼런스 보드</button>
            <button onclick="window.location.href='/favorites/preference/'" class="px-4 py-2 text-[15px] font-normal text-gray-700 hover:text-blue-600 hover:bg-blue-50 rounded-lg transition-all leading-none">취향분석</button>
            <button onclick="Auth.logout()" class="px-4 py-2 text-[15px] font-normal text-gray-700 hover:text-blue-600 hover:bg-blue-50 rounded-lg transition-all leading-none">로그아웃</button>
        `;
    }

    function togglePasswordVisibility(input, btn) {
        const type = input.getAttribute('type') === 'password' ? 'text' : 'password';
        input.setAttribute('type', type);
        const iconName = type === 'password' ? 'eye' : 'eye-off';
        btn.innerHTML = `<i data-lucide="${iconName}" class="w-[18px] h-[18px]"></i>`;
        lucide.createIcons();
    }

    function showError(msg) {
        errorText.textContent = msg;
        errorMessage.classList.remove('hidden');
    }

    function hideError() {
        errorMessage.classList.add('hidden');
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

    // Event Listeners
    toggleCurrentPasswordBtn.addEventListener('click', () => togglePasswordVisibility(currentPasswordInput, toggleCurrentPasswordBtn));
    toggleNewPasswordBtn.addEventListener('click', () => togglePasswordVisibility(newPasswordInput, toggleNewPasswordBtn));
    toggleConfirmPasswordBtn.addEventListener('click', () => togglePasswordVisibility(confirmPasswordInput, toggleConfirmPasswordBtn));

    btnSubmit.addEventListener('click', async () => {
        hideError();

        const currentPassword = currentPasswordInput.value;
        const newPassword = newPasswordInput.value;
        const confirmPassword = confirmPasswordInput.value;

        if (!currentPassword) {
            showError('기존 비밀번호를 입력해주세요.');
            return;
        }

        if (!newPassword) {
            showError('새 비밀번호를 입력해주세요.');
            return;
        }

        const pwdError = validatePassword(newPassword);
        if (pwdError) {
            showError(pwdError);
            return;
        }

        if (!confirmPassword) {
            showError('새 비밀번호 확인을 입력해주세요.');
            return;
        }

        if (newPassword !== confirmPassword) {
            showError('새 비밀번호가 일치하지 않습니다.');
            return;
        }

        if (currentPassword === newPassword) {
            showError('기존 비밀번호와 동일한 비밀번호는 사용할 수 없습니다.');
            return;
        }

        try {
            await fetchJson('/api/accounts/password/change/', {
                method: 'POST',
                body: {
                    old_password: currentPassword,
                    password: newPassword,
                    password2: confirmPassword,
                },
            });
            popupSuccess.classList.remove('hidden');
        } catch (error) {
            showError(error.message || '비밀번호 변경에 실패했습니다.');
        }
    });
});
