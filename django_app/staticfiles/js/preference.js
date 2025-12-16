/**
 * Preference Page Logic
 */

document.addEventListener('DOMContentLoaded', () => {
    // State
    let step = 1;
    let gender = '';
    let birthdate = '';
    let mbti = [null, null, null, null];
    let selectedStyles = [];

    const staticImageMap = {
        vintage: 'vintage_interior/vintage_interior_0_1.jpg',
        luxury: 'luxury_interior/luxury_interior_0_1.jpg',
        natural: 'natural_interior/natural_interior_0_1.jpg',
        scandinavian: 'scandinavian_interior/scandinavian_interior_0_1.jpg',
        french: 'prench_interior/prench_interior_0_1.jpg',
        lovely: 'lovely_interior/lovely_interior_0_1.jpg',
        pastel: 'pastel_interior/pastel_interior_0_1.jpg',
        modern: 'modern_interior/modern_interior_0_1.jpg',
        bohemian: 'bohemian_interior/bohemian_interior_0_1.jpg',
        classic: 'calssic_interior/calssic_interior_0_1.jpg',
        industrial: 'industrial_interior/industrial_interior_0_1.jpg',
        minimal: 'minimal_interior/minimal_interior_0_1.jpg',
    };

    const PLACEHOLDER_DATA_URI = 'data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAEAAAABACAYAAACqaXHeAAAACXBIWXMAAAsTAAALEwEAmpwYAAAANklEQVR4nO3BMQEAAADCoPdPbQ43oAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA4LEBvgABGk0y7wAAAABJRU5ErkJggg==';
    const toStaticUrl = (path) => {
        if (!path) return '';
        if (path.startsWith('http://') || path.startsWith('https://')) return path;
        if (path.startsWith('/static/')) return `${path}?v=1`;
        return `/static/${path.replace(/^\//, '')}?v=1`;
    };

    const styleImages = Object.keys(staticImageMap).map((id) => {
        const displayNameMap = {
            vintage: '빈티지',
            luxury: '럭셔리',
            natural: '내추럴',
            scandinavian: '스칸디나비안',
            french: '프렌치',
            lovely: '러블리',
            pastel: '파스텔',
            modern: '모던',
            bohemian: '보헤미안',
            classic: '클래식',
            industrial: '인더스트리얼',
            minimal: '미니멀',
        };

        // IMAGE_DATA 우선 사용, 없으면 static 경로 사용
        // 이미지 데이터가 있어도 캐시/경로 문제를 제거하기 위해 static 경로를 우선 사용
        let url = `/static/images/${staticImageMap[id]}?v=1`;

        return {
            id,
            name: id,
            displayName: displayNameMap[id] || id,
            url,
        };
    });

    // Elements
    const headerNav = document.getElementById('header-nav');
    const step1 = document.getElementById('step-1');
    const step2 = document.getElementById('step-2');
    const step3 = document.getElementById('step-3');
    const step4 = document.getElementById('step-4');

    // Step 1
    const btnGenderFemale = document.getElementById('btn-gender-female');
    const btnGenderMale = document.getElementById('btn-gender-male');
    const btnGenderNone = document.getElementById('btn-gender-none');
    const btnStep1Next = document.getElementById('btn-step-1-next');

    // Step 2
    const birthdateInput = document.getElementById('birthdate-input');
    const birthdateError = document.getElementById('birthdate-error');
    const btnStep2Next = document.getElementById('btn-step-2-next');

    // Step 3
    const btnStep3Next = document.getElementById('btn-step-3-next');

    // Step 4
    const styleGrid = document.getElementById('style-grid');
    const btnComplete = document.getElementById('btn-complete');

    // Initialize
    renderHeaderNav();
    renderStyleGrid();

    // Functions
    function renderHeaderNav() {
        headerNav.innerHTML = `
            <button onclick="window.location.href='/user/mypage/'" class="px-4 py-2 text-[15px] font-normal text-gray-700 hover:text-blue-600 hover:bg-blue-50 rounded-lg transition-all leading-none">마이페이지</button>
            <button onclick="window.location.href='/favorites/reference-board/'" class="px-4 py-2 text-[15px] font-normal text-gray-700 hover:text-blue-600 hover:bg-blue-50 rounded-lg transition-all leading-none">레퍼런스 보드</button>
            <button onclick="window.location.href='/favorites/preference/'" class="px-4 py-2 text-[15px] font-normal text-gray-700 hover:text-blue-600 hover:bg-blue-50 rounded-lg transition-all leading-none">취향분석</button>
            <button onclick="Auth.logout()" class="px-4 py-2 text-[15px] font-normal text-gray-700 hover:text-blue-600 hover:bg-blue-50 rounded-lg transition-all leading-none">로그아웃</button>
        `;
    }

    window.showStep = (s) => {
        step = s;
        step1.classList.add('hidden');
        step2.classList.add('hidden');
        step3.classList.add('hidden');
        step4.classList.add('hidden');

        if (s === 1) step1.classList.remove('hidden');
        if (s === 2) step2.classList.remove('hidden');
        if (s === 3) step3.classList.remove('hidden');
        if (s === 4) step4.classList.remove('hidden');
    };

    // Step 1 Logic
    window.setGender = (val) => {
        gender = val;
        updateGenderButtons();
        btnStep1Next.disabled = false;
    };

    function updateGenderButtons() {
        [btnGenderFemale, btnGenderMale, btnGenderNone].forEach(btn => {
            btn.className = 'w-full py-3 rounded-full border-2 border-blue-200 hover:border-blue-400 transition-colors';
        });

        if (gender === '여성') btnGenderFemale.className = 'w-full py-3 rounded-full border-2 bg-gradient-to-r from-blue-500 to-blue-400 text-white border-blue-500 shadow-lg transition-colors';
        if (gender === '남성') btnGenderMale.className = 'w-full py-3 rounded-full border-2 bg-gradient-to-r from-blue-500 to-blue-400 text-white border-blue-500 shadow-lg transition-colors';
        if (gender === '선택 안함') btnGenderNone.className = 'w-full py-3 rounded-full border-2 bg-gradient-to-r from-blue-500 to-blue-400 text-white border-blue-500 shadow-lg transition-colors';
    }

    btnStep1Next.addEventListener('click', () => {
        if (gender) showStep(2);
    });

    // Step 2 Logic
    function validateBirthdate(value) {
        if (!/^\d{8}$/.test(value)) return false;
        const year = parseInt(value.substring(0, 4));
        const month = parseInt(value.substring(4, 6));
        const day = parseInt(value.substring(6, 8));
        if (month < 1 || month > 12) return false;
        if (day < 1 || day > 31) return false;
        const date = new Date(year, month - 1, day);
        if (date.getFullYear() !== year || date.getMonth() !== month - 1 || date.getDate() !== day) return false;
        const today = new Date();
        const kstToday = new Date(today.getTime() + 9 * 60 * 60 * 1000);
        const kstTodayString = kstToday.toISOString().slice(0, 10).replace(/-/g, '');
        if (parseInt(value) > parseInt(kstTodayString)) return false;
        return true;
    }

    birthdateInput.addEventListener('input', (e) => {
        const value = e.target.value.replace(/[^0-9]/g, '');
        birthdate = value;
        e.target.value = value;

        if (value.length > 0 && value.length < 8) {
            birthdateError.textContent = '생년월일을 올바른 형식으로 입력해 주시기 바랍니다.';
            birthdateError.classList.remove('hidden');
            btnStep2Next.disabled = true;
        } else if (value.length === 8) {
            if (!validateBirthdate(value)) {
                birthdateError.textContent = '생년월일을 다시 입력해 주시기 바랍니다.';
                birthdateError.classList.remove('hidden');
                btnStep2Next.disabled = true;
            } else {
                birthdateError.classList.add('hidden');
                btnStep2Next.disabled = false;
            }
        } else {
            birthdateError.classList.add('hidden');
            btnStep2Next.disabled = true;
        }
    });

    btnStep2Next.addEventListener('click', () => {
        if (birthdate && validateBirthdate(birthdate)) showStep(3);
    });

    // Step 3 Logic
    window.setMbti = (index, val) => {
        mbti[index] = val;
        updateMbtiButtons();
        btnStep3Next.disabled = mbti.includes(null);
    };

    function updateMbtiButtons() {
        const buttons = {
            0: { 'E': 'btn-mbti-e', 'I': 'btn-mbti-i' },
            1: { 'S': 'btn-mbti-s', 'N': 'btn-mbti-n' },
            2: { 'T': 'btn-mbti-t', 'F': 'btn-mbti-f' },
            3: { 'J': 'btn-mbti-j', 'P': 'btn-mbti-p' }
        };

        for (let i = 0; i < 4; i++) {
            for (const [val, id] of Object.entries(buttons[i])) {
                const btn = document.getElementById(id);
                if (mbti[i] === val) {
                    btn.className = 'w-full px-8 py-3 rounded-full border-2 bg-gradient-to-r from-blue-500 to-blue-400 text-white border-blue-500 shadow-lg transition-colors';
                } else {
                    btn.className = 'w-full px-8 py-3 rounded-full border-2 border-blue-200 hover:border-blue-400 transition-colors';
                }
            }
        }
    }

    btnStep3Next.addEventListener('click', () => {
        if (!mbti.includes(null)) showStep(4);
    });

    // Step 4 Logic
    function renderStyleGrid() {
        styleGrid.innerHTML = styleImages.map(style => `
            <button id="style-btn-${style.id}" onclick="toggleStyle('${style.id}')" class="relative aspect-square rounded-xl overflow-hidden group bg-white border border-gray-200 shadow-sm transition-all duration-200">
                <img src="${style.url}" alt="${style.name}" class="w-full h-full object-cover bg-gray-100" onerror="this.onerror=null;this.src='${PLACEHOLDER_DATA_URI}';">
                <div class="absolute inset-0 bg-black/0 group-hover:bg-black/30 transition-all duration-300 flex items-center justify-center">
                    <p class="text-white text-sm opacity-0 group-hover:opacity-100 transition-opacity duration-300">${style.displayName}</p>
                </div>
                <div id="style-overlay-${style.id}" class="hidden absolute bottom-2 right-2">
                    <div class="w-8 h-8 bg-blue-500 rounded-full flex items-center justify-center shadow">
                        <i data-lucide="check" class="w-4 h-4 text-white" stroke-width="3"></i>
                    </div>
                </div>
            </button>
        `).join('');
        lucide.createIcons();
    }

    window.toggleStyle = (id) => {
        if (selectedStyles.includes(id)) {
            selectedStyles = selectedStyles.filter(s => s !== id);
        } else {
            if (selectedStyles.length < 3) {
                selectedStyles.push(id);
            }
        }
        updateStyleSelection();
        btnComplete.disabled = selectedStyles.length === 0;
    };

    function updateStyleSelection() {
        styleImages.forEach(style => {
            const overlay = document.getElementById(`style-overlay-${style.id}`);
            const btn = document.getElementById(`style-btn-${style.id}`);
            if (selectedStyles.includes(style.id)) {
                overlay.classList.remove('hidden');
                btn?.classList.add('selected-style');
            } else {
                overlay.classList.add('hidden');
                btn?.classList.remove('selected-style');
            }
        });
    }

    btnComplete.addEventListener('click', () => {
        if (selectedStyles.length > 0) {
            const preferences = {
                gender,
                birthdate,
                mbti: mbti.join(''),
                styles: selectedStyles
            };
            State.set('userPreferences', preferences);
            window.location.href = '/favorites/reference-board/';
        }
    });
});
