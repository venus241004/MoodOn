/**
 * Reference Board Page Logic
 */

document.addEventListener('DOMContentLoaded', () => {
    // Check Login
    if (!Auth.requireLogin()) return;

    // State
    let userPreferences = State.get('userPreferences', null);
    let userEmail = State.get('userEmail', '');
    let selectedStyles = userPreferences?.styles || [];

    const styleCategories = [
        'vintage', 'luxury', 'natural', 'scandinavian', 'french',
        'lovely', 'pastel', 'modern', 'bohemian', 'classic',
        'industrial', 'minimal'
    ];

    const styleDirMap = {
        vintage: 'vintage_interior',
        luxury: 'luxury_interior',
        natural: 'natural_interior',
        scandinavian: 'scandinavian_interior',
        french: 'prench_interior', // 주의: 디렉터리명이 prench로 생성됨
        lovely: 'lovely_interior',
        pastel: 'pastel_interior',
        modern: 'modern_interior',
        bohemian: 'bohemian_interior',
        classic: 'calssic_interior', // 디렉터리명이 calssic으로 생성됨
        industrial: 'industrial_interior',
        minimal: 'minimal_interior',
    };

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

    // IMAGE_DATA가 있으면 활용 (카테고리별), 없으면 정적 이미지로 대체
    const categoryImages = typeof IMAGE_DATA !== 'undefined' ? IMAGE_DATA : {};

    const toStaticUrl = (path) => {
        if (!path) return '';
        if (path.startsWith('http://') || path.startsWith('https://')) return path;
        if (path.startsWith('/static/')) return `${path}?v=1`;
        if (path.startsWith('images/')) return `/static/${path}?v=1`;
        return `/static/${path.replace(/^\//, '')}?v=1`;
    };

    const filterByStyleDir = (style, list) => {
        const dir = styleDirMap[style];
        if (!dir) return list;
        const filtered = (list || []).filter((url) => typeof url === 'string' && url.includes(`/${dir}/`));
        return filtered.length > 0 ? filtered : list || [];
    };

    // Elements
    const headerNav = document.getElementById('header-nav');
    const styleTags = document.getElementById('style-tags');
    const imageGrid = document.getElementById('image-grid');
    const emptyMessage = document.getElementById('empty-message');
    const preferenceMessage = document.getElementById('preference-message');
    const userNameDisplay = document.getElementById('user-name-display');

    // Initialize
    renderHeaderNav();
    renderStyleTags();
    renderImages();

    if (userPreferences && userPreferences.styles && userPreferences.styles.length > 0) {
        preferenceMessage.classList.remove('hidden');
        userNameDisplay.textContent = userEmail ? userEmail.split('@')[0] : (userPreferences.gender || '회원');
    }

    // Functions
    function renderHeaderNav() {
        headerNav.innerHTML = `
            <button onclick="window.location.href='/user/mypage/'" class="px-4 py-2 text-[15px] font-normal text-gray-700 hover:text-blue-600 hover:bg-blue-50 rounded-lg transition-all leading-none">마이페이지</button>
            <button onclick="window.location.href='/favorites/reference-board/'" class="px-4 py-2 text-[15px] font-normal text-gray-700 hover:text-blue-600 hover:bg-blue-50 rounded-lg transition-all leading-none">레퍼런스 보드</button>
            <button onclick="window.location.href='/favorites/preference/'" class="px-4 py-2 text-[15px] font-normal text-gray-700 hover:text-blue-600 hover:bg-blue-50 rounded-lg transition-all leading-none">취향분석</button>
            <button onclick="Auth.logout()" class="px-4 py-2 text-[15px] font-normal text-gray-700 hover:text-blue-600 hover:bg-blue-50 rounded-lg transition-all leading-none">로그아웃</button>
        `;
    }

    function renderStyleTags() {
        styleTags.innerHTML = styleCategories.map(style => `
            <button onclick="toggleStyle('${style}')" class="px-6 py-2 rounded-full border-2 transition-all whitespace-nowrap ${selectedStyles.includes(style)
                ? 'bg-gradient-to-r from-pink-400 via-purple-400 to-blue-400 text-white border-transparent shadow-lg'
                : 'bg-white text-purple-600 border-purple-300 hover:border-purple-400'
            }">
                ${style}
            </button>
        `).join('');
    }

    window.toggleStyle = (style) => {
        if (selectedStyles.includes(style)) {
            selectedStyles = selectedStyles.filter(s => s !== style);
        } else {
            if (selectedStyles.length >= 3) {
                alert('태그는 최대 3개까지 선택할 수 있습니다.');
                return;
            }
            selectedStyles.push(style);
        }
        renderStyleTags();
        renderImages();
    };

    function renderImages() {
        // 선택이 전혀 없으면 빈 상태 유지 (취향분석 기본값도 적용하지 않음)
        if (!selectedStyles || selectedStyles.length === 0) {
            imageGrid.innerHTML = '';
            emptyMessage.classList.remove('hidden');
            lucide.createIcons();
            return;
        }

        // 선택된 각 스타일별 이미지 목록 확보
        const perStyleImages = selectedStyles.map(style => {
            let imgs = [];
            if (categoryImages[style] && Array.isArray(categoryImages[style])) {
                imgs = filterByStyleDir(style, categoryImages[style]).map(toStaticUrl);
            }
            if (!imgs || imgs.length === 0) {
                if (staticImageMap[style]) {
                    imgs = [`/static/images/${staticImageMap[style]}?v=1`];
                }
            }
            return imgs;
        });

        // 라운드로빈으로 섞기
        let displayImages = [];
        let idx = 0;
        while (true) {
            let added = false;
            for (let i = 0; i < perStyleImages.length; i++) {
                if (perStyleImages[i][idx]) {
                    displayImages.push(perStyleImages[i][idx]);
                    added = true;
                }
            }
            if (!added) break;
            idx += 1;
        }

        if (displayImages.length > 0) {
            imageGrid.innerHTML = displayImages.map((img, index) => `
                <div class="relative group">
                    <div class="aspect-square rounded-3xl overflow-hidden">
                        <img src="${toStaticUrl(img)}" alt="Interior ${index + 1}" class="w-full h-full object-cover">
                    </div>
                    <button onclick="downloadImage('${img}', ${index})" class="absolute bottom-4 left-1/2 -translate-x-1/2 px-6 py-2 bg-white rounded-full border border-gray-300 opacity-0 group-hover:opacity-100 transition-opacity flex items-center gap-2 hover:bg-gray-50">
                        <i data-lucide="download" class="w-4 h-4"></i>
                        download
                    </button>
                </div>
            `).join('');
            emptyMessage.classList.add('hidden');
        } else {
            imageGrid.innerHTML = '';
            emptyMessage.classList.remove('hidden');
        }
        lucide.createIcons();
    }

    window.downloadImage = async (url, index) => {
        try {
            const response = await fetch(toStaticUrl(url));
            const blob = await response.blob();
            const blobUrl = window.URL.createObjectURL(blob);
            const link = document.createElement('a');
            link.href = blobUrl;
            link.download = `mood-on-reference-${index + 1}.jpg`;
            document.body.appendChild(link);
            link.click();
            document.body.removeChild(link);
            window.URL.revokeObjectURL(blobUrl);
        } catch (error) {
            console.error('Download failed:', error);
            alert('이미지 다운로드에 실패했습니다.');
        }
    };
});
