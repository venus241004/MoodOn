/**
 * My Page Logic
 */

document.addEventListener('DOMContentLoaded', () => {
    // Check Login
    if (!Auth.requireLogin()) return;

    // State
    let userEmail = State.get('userEmail', 'mountainstar03@gmail.com');
    let userPreferences = State.get('userPreferences', null);
    let favoriteProducts = State.get('favoriteProducts', []);
    let sortBy = 'recent';
    let showSortMenu = false;

    // Elements
    const headerNav = document.getElementById('header-nav');
    const profileName = document.getElementById('profile-name');
    const profileEmail = document.getElementById('profile-email');
    const moodGender = document.getElementById('mood-gender');
    const moodGenderIcon = document.getElementById('mood-gender-icon');
    const moodBirthdate = document.getElementById('mood-birthdate');
    const moodMbti = document.getElementById('mood-mbti');
    const moodMbtiText = document.getElementById('mood-mbti-text');
    const moodStyle = document.getElementById('mood-style');
    const favoritesCountBadge = document.getElementById('favorites-count-badge');
    const favoritesGrid = document.getElementById('favorites-grid');
    const btnSort = document.getElementById('btn-sort');
    const sortLabel = document.getElementById('sort-label');
    const sortMenu = document.getElementById('sort-menu');
    const btnDeleteAccount = document.getElementById('btn-delete-account');
    const btnConfirmDeleteAccount = document.getElementById('btn-confirm-delete-account');

    // Initialize
    renderHeaderNav();
    renderProfile();
    renderMood();
    renderFavorites();

    // Event Listeners
    btnSort.addEventListener('click', () => {
        showSortMenu = !showSortMenu;
        sortMenu.classList.toggle('hidden', !showSortMenu);
    });

    document.addEventListener('click', (e) => {
        if (!btnSort.contains(e.target) && !sortMenu.contains(e.target)) {
            showSortMenu = false;
            sortMenu.classList.add('hidden');
        }
    });

    btnDeleteAccount.addEventListener('click', () => {
        document.getElementById('popup-delete-account').classList.remove('hidden');
    });

    btnConfirmDeleteAccount.addEventListener('click', async () => {
        try {
            document.getElementById('popup-delete-account').classList.add('hidden');
            document.getElementById('popup-success').classList.remove('hidden');

            await fetchJson('/api/accounts/delete/', { method: 'POST' });
            await Auth.logout();
        } catch (error) {
            document.getElementById('popup-delete-account').classList.add('hidden');
            alert(error.message || '회원탈퇴 처리 중 오류가 발생했습니다.');
        }
    });

    // Functions
    function renderHeaderNav() {
        headerNav.innerHTML = `
            <button onclick="window.location.href='/user/mypage/'" class="px-4 py-2 text-[15px] font-normal text-gray-700 hover:text-blue-600 hover:bg-blue-50 rounded-lg transition-all leading-none">마이페이지</button>
            <button onclick="window.location.href='/favorites/reference-board/'" class="px-4 py-2 text-[15px] font-normal text-gray-700 hover:text-blue-600 hover:bg-blue-50 rounded-lg transition-all leading-none">레퍼런스 보드</button>
            <button onclick="window.location.href='/favorites/preference/'" class="px-4 py-2 text-[15px] font-normal text-gray-700 hover:text-blue-600 hover:bg-blue-50 rounded-lg transition-all leading-none">취향분석</button>
            <button onclick="Auth.logout()" class="px-4 py-2 text-[15px] font-normal text-gray-700 hover:text-blue-600 hover:bg-blue-50 rounded-lg transition-all leading-none">로그아웃</button>
        `;
    }

    function renderProfile() {
        const id = userEmail.split('@')[0];
        profileName.textContent = id;
        profileEmail.textContent = userEmail;
    }

    function renderMood() {
        const gender = userPreferences?.gender || '여성';
        moodGender.textContent = gender;
        moodGenderIcon.textContent = gender === '여성' ? '👩' : gender === '남성' ? '👨' : '🧑';

        moodBirthdate.textContent = userPreferences?.birthdate || '2000.06.17';

        const mbti = userPreferences?.mbti || 'ENTJ';
        moodMbti.textContent = mbti;
        moodMbtiText.textContent = mbti;

        moodStyle.textContent = userPreferences?.styles?.[0] || '북유럽';
    }

    window.setSort = (option) => {
        sortBy = option;
        showSortMenu = false;
        sortMenu.classList.add('hidden');

        switch (option) {
            case 'price-low': sortLabel.textContent = '가격 낮은순'; break;
            case 'price-high': sortLabel.textContent = '가격 높은순'; break;
            default: sortLabel.textContent = '등록순'; break;
        }

        renderFavorites();
    };

    function renderFavorites() {
        favoritesCountBadge.textContent = `${favoriteProducts.length}개`;

        if (favoriteProducts.length === 0) {
            favoritesGrid.innerHTML = `
                <div class="h-full flex flex-col items-center justify-center">
                    <div class="w-32 h-32 bg-gradient-to-br from-pink-100 to-rose-100 rounded-full flex items-center justify-center mb-6">
                        <i data-lucide="heart" class="text-pink-300 w-[64px] h-[64px]"></i>
                    </div>
                    <h3 class="text-2xl mb-3 text-gray-800">아직 관심 상품이 없어요</h3>
                    <p class="text-gray-500 mb-8 text-center">
                        챗봇에서 마음에 드는 상품을 찾아보세요!<br/>
                        AI가 당신의 취향에 맞는 상품을 추천해드릴게요.
                    </p>
                    <button onclick="window.location.href='/chat/'" class="px-8 py-4 bg-gradient-to-r from-blue-500 to-blue-400 text-white rounded-2xl hover:from-blue-600 hover:to-blue-500 transition-all shadow-lg hover:shadow-xl transform hover:-translate-y-1 flex items-center gap-2">
                        <span>챗봇으로 가기</span>
                        <span>💬</span>
                    </button>
                </div>
            `;
        } else {
            let sorted = [...favoriteProducts];
            if (sortBy === 'price-low') {
                sorted.sort((a, b) => parseInt(a.price.replace(/[^\d]/g, '')) - parseInt(b.price.replace(/[^\d]/g, '')));
            } else if (sortBy === 'price-high') {
                sorted.sort((a, b) => parseInt(b.price.replace(/[^\d]/g, '')) - parseInt(a.price.replace(/[^\d]/g, '')));
            }

            favoritesGrid.innerHTML = `
                <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-5 gap-5">
                    ${sorted.map(p => `
                        <div class="group">
                            <div class="bg-white rounded-2xl overflow-hidden shadow-md hover:shadow-xl transition-all border border-gray-200 hover:border-pink-200 transform hover:-translate-y-1">
                                <div class="relative aspect-square overflow-hidden">
                                    <img src="${p.image}" alt="${p.name}" class="w-full h-full object-cover group-hover:scale-105 transition-transform duration-300">
                                    <div class="absolute top-3 left-3 px-3 py-1 bg-gradient-to-r from-pink-500 to-rose-500 text-white rounded-lg text-xs flex items-center gap-1">관심상품</div>
                                    <button onclick="removeFavorite('${p.id}')" class="absolute top-3 right-3 p-1.5 bg-white/95 backdrop-blur rounded-lg hover:bg-pink-50 transition-all shadow-md group/btn" title="관심 상품 해제">
                                        <i data-lucide="heart" class="text-pink-500 fill-pink-500 w-[18px] h-[18px] group-hover/btn:scale-110 transition-transform"></i>
                                    </button>
                                </div>
                                <div class="p-4">
                                    <h4 class="mb-1 truncate text-gray-800">${p.name}</h4>
                                    <p class="text-xs text-gray-500 mb-2">${p.brand || 'Brand'}</p>
                                    <p class="text-blue-600 mb-3">${p.price}</p>
                                    <a href="${p.link}" target="_blank" class="w-full flex items-center justify-center gap-2 px-4 py-2.5 bg-blue-500 text-white rounded-lg hover:bg-blue-600 transition-all text-sm">
                                        <i data-lucide="external-link" class="w-[16px] h-[16px]"></i>
                                        <span>구매하러 가기</span>
                                    </a>
                                </div>
                            </div>
                        </div>
                    `).join('')}
                </div>
            `;
        }
        lucide.createIcons();
    }

    window.removeFavorite = (id) => {
        favoriteProducts = favoriteProducts.filter(p => p.id !== id);
        State.set('favoriteProducts', favoriteProducts);
        renderFavorites();
    };
});
