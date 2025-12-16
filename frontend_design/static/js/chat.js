document.addEventListener('DOMContentLoaded', () => {
    // --------------- State ---------------
    let sessions = [];
    let currentSessionId = null;
    let favoriteProducts = State.get('favoriteProducts', []);
    let excludedProductIds = new Set();
    let uploadedImage = null; // data URL preview
    let uploadedFile = null; // File object to send
    let sidebarOpen = true;
    let isSending = false;
    let selectedImageType = 'current'; // current | reference
    let pendingMessages = {}; // {sessionId: [{id, role, text, created_at, image, image_type}]}
    let pendingPollTimer = null;
    let historyExpanded = false;
    let favoritesExpanded = false;
    let sessionToDelete = null;
    let isLoggedIn = false;

    // --------------- Elements ---------------
    const sidebar = document.getElementById('sidebar');
    const sidebarLoggedOut = document.getElementById('sidebar-logged-out');
    const sidebarLoggedIn = document.getElementById('sidebar-logged-in');
    const sessionContext = document.getElementById('session-context');
    const headerNav = document.getElementById('header-nav');
    const emptyState = document.getElementById('empty-state');
    const messagesContainer = document.getElementById('messages-container');
    const messagesList = document.getElementById('messages-list');
    const chatInput = document.getElementById('chat-input');
    const btnSend = document.getElementById('btn-send');
    const fileInput = document.getElementById('file-input');
    const btnUploadImage = document.getElementById('btn-upload-image');
    const imagePreviewContainer = document.getElementById('image-preview-container');
    const imagePreview = document.getElementById('image-preview');
    const btnRemoveImage = document.getElementById('btn-remove-image');
    const charCount = document.getElementById('char-count');
    const exampleQuestionsContainer = document.getElementById('example-questions');

    const exampleQuestions = [
        '빈티지 스타일 소파 추천해줘',
        '원목 테이블 어디서 구매할 수 있을까?',
        '작은 거실에 어울리는 인테리어 소품은?',
        '모던한 조명 추천 부탁해',
    ];

    // 이미지/텍스트 동시 입력 지원
    function clearImageSelection() {
        uploadedImage = null;
        uploadedFile = null;
        imagePreviewContainer.classList.add('hidden');
        btnUploadImage.disabled = false;
        chatInput.disabled = false;
        chatInput.placeholder = '인테리어 고민을 물어보세요...';
    }

    function updateAttachmentLock() {
        // 텍스트와 이미지 모두 허용하되, 전송 중에는 입력 비활성화
        const isLoggedInLocal = Auth.isLoggedIn();
        if (!isSending) {
            chatInput.disabled = false;
            btnUploadImage.disabled = false;
            chatInput.placeholder = isLoggedInLocal ? '인테리어 고민을 물어보세요...' : '로그인 후 사용 가능합니다';
        } else {
            chatInput.disabled = true;
            btnUploadImage.disabled = true;
        }
    }

    // --------------- Helpers ---------------
    function normalizeSession(raw) {
        if (!raw) return null;
        const rawId = typeof raw === 'number' ? raw : (raw.id ?? raw.session_id ?? raw.pk ?? raw);
        const id = Number(rawId);
        if (!Number.isFinite(id)) return null;
        const messages = sortMessagesByCreatedAt(raw.messages || []);
        const state = raw.state || {};
        const budget =
            state.price_min != null && state.price_max != null
                ? `${state.price_min.toLocaleString()}~${state.price_max.toLocaleString()}`
                : state.price_min != null
                    ? `${state.price_min.toLocaleString()}~`
                    : state.price_max != null
                        ? `~${state.price_max.toLocaleString()}`
                        : null;
        const mood = (state.target_moods && state.target_moods[0]) || (state.current_moods && state.current_moods[0]) || null;
        return {
            ...raw,
            id,
            title: raw.title || '새 채팅',
            messages,
            state: {
                ...state,
                budget: budget || state.budget,
                mood: mood || state.mood,
                mode: state.mode || state.last_intent || raw.mode,
            },
            context: raw.context || {},
        };
    }

    // Pending message helpers (persist across reloads)
    function loadPendingFromStorage() {
        try {
            const data = JSON.parse(localStorage.getItem('pendingMessages') || '{}');
            if (data && typeof data === 'object') pendingMessages = data;
        } catch (e) {
            pendingMessages = {};
        }
    }

    function savePendingToStorage() {
        try {
            localStorage.setItem('pendingMessages', JSON.stringify(pendingMessages));
        } catch (e) { /* ignore */ }
    }

    function hasAnyPending() {
        return Object.values(pendingMessages).some(arr => Array.isArray(arr) && arr.length > 0);
    }

    function addPending(sessionId, msgs) {
        const key = String(sessionId);
        pendingMessages[key] = [...(pendingMessages[key] || []), ...msgs];
        savePendingToStorage();
    }

    function clearPending(sessionId) {
        const key = String(sessionId);
        if (pendingMessages[key]) {
            delete pendingMessages[key];
            savePendingToStorage();
        }
    }

    function getPendingCount(sessionId) {
        const key = String(sessionId);
        return (pendingMessages[key] || []).length;
    }

    function mergePending(session) {
        const key = String(session.id);
        if (!pendingMessages[key] || pendingMessages[key].length === 0) return session;

        const serverMessages = session.messages || [];
        const hasAssistant = serverMessages.some(m => (m.role === 'assistant' || m.sender === 'assistant'));
        const hasUser = serverMessages.some(m => (m.role === 'user' || m.sender === 'user'));

        // pending을 역할별로 필터링: user는 서버에 user가 있으면 제거, assistant는 서버에 assistant가 있으면 제거
        const filteredPending = (pendingMessages[key] || []).filter(m => {
            const isAssistant = m.role === 'assistant' || m.sender === 'assistant';
            const isUser = m.role === 'user' || m.sender === 'user';
            if (isAssistant) return !hasAssistant; // 서버 assistant 없을 때만 표시
            if (isUser) return !hasUser;           // 서버 user 없을 때만 표시
            return false;
        });

        if (filteredPending.length === 0) {
            clearPending(session.id);
            return session;
        }

        const merged = { ...session };
        merged.messages = sortMessagesByCreatedAt([...(merged.messages || []), ...filteredPending]);
        return merged;
    }

    function stopPendingPolling() {
        if (pendingPollTimer) {
            clearInterval(pendingPollTimer);
            pendingPollTimer = null;
        }
    }

    async function pollPending() {
        if (!hasAnyPending() || !currentSessionId) {
            stopPendingPolling();
            return;
        }
        try {
            await loadSessionDetail(currentSessionId);
            if (!hasAnyPending()) stopPendingPolling();
        } catch (e) {
            // ignore polling errors
        }
    }

    function startPendingPolling() {
        stopPendingPolling();
        if (!hasAnyPending()) return;
        pendingPollTimer = setInterval(pollPending, 3000);
    }

    function getCurrentSession() {
        return sessions.find(s => Number(s.id) === Number(currentSessionId));
    }

    function pushMessageToSession(sessionId, msg) {
        const s = sessions.find(x => Number(x.id) === Number(sessionId));
        if (!s) return;
        s.messages = [...(s.messages || []), msg];
    }

    function removePendingMessage(sessionId, pendingId) {
        const s = sessions.find(x => Number(x.id) === Number(sessionId));
        if (!s || !s.messages) return;
        s.messages = s.messages.filter(m => m.id !== pendingId);
    }

    function formatTimestamp(raw) {
        if (!raw) return '';
        const d = new Date(raw);
        if (isNaN(d.getTime())) return '';
        const y = d.getFullYear();
        const m = String(d.getMonth() + 1).padStart(2, '0');
        const day = String(d.getDate()).padStart(2, '0');
        const hh = String(d.getHours()).padStart(2, '0');
        const mm = String(d.getMinutes()).padStart(2, '0');
        return `${y}-${m}-${day} ${hh}:${mm}`;
    }

    function sortMessagesByCreatedAt(list = []) {
        return [...list].sort((a, b) => {
            const da = new Date(a.created_at || a.timestamp || a.createdAt || 0).getTime();
            const db = new Date(b.created_at || b.timestamp || b.createdAt || 0).getTime();
            return da - db;
        });
    }

    // --------------- Init ---------------
    async function init() {
        try {
            loadPendingFromStorage();
            const synced = await Auth.syncSession();
            isLoggedIn = synced || Auth.isLoggedIn();
            if (!isLoggedIn) {
                window.location.href = '/login/?next=/chat/';
                return;
            }
            updateSidebarVisibility();
            renderHeaderNav();
            renderExampleQuestions();
            await loadSessions();
            if (hasAnyPending()) startPendingPolling();
        } catch (e) {
            console.error('초기화 중 오류', e);
            window.location.href = '/login/?next=/chat/';
        }
    }
    init();

    // --------------- Event Listeners ---------------
    document.getElementById('btn-toggle-sidebar').addEventListener('click', () => {
        sidebarOpen = !sidebarOpen;
        sidebar.style.marginLeft = sidebarOpen ? '0' : '-18rem';
    });
    document.getElementById('btn-new-chat').addEventListener('click', createNewSession);
    document.getElementById('btn-toggle-history').addEventListener('click', () => toggleSidebarSection('history'));
    document.getElementById('btn-toggle-favorites').addEventListener('click', () => toggleSidebarSection('favorites'));
    document.getElementById('btn-reset-context').addEventListener('click', resetContext);
    document.getElementById('btn-confirm-delete').addEventListener('click', confirmDeleteSession);

    chatInput.addEventListener('input', (e) => {
        e.target.style.height = 'auto';
        e.target.style.height = Math.min(e.target.scrollHeight, 200) + 'px';
        charCount.textContent = `${e.target.value.length}/200`;
        updateAttachmentLock();
    });
    chatInput.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            handleSend();
        }
    });
    btnSend.addEventListener('click', () => handleSend());

    btnUploadImage.addEventListener('click', () => {
        if (!Auth.requireLogin()) return;
        // 같은 파일을 연속 선택해도 change 이벤트가 발생하도록 리셋
        fileInput.value = '';
        fileInput.click();
    });
    fileInput.addEventListener('change', handleImageUpload);
    btnRemoveImage.addEventListener('click', () => {
        uploadedImage = null;
        uploadedFile = null;
        imagePreviewContainer.classList.add('hidden');
        btnUploadImage.disabled = false;
        chatInput.disabled = false;
        updateAttachmentLock();
    });
    const imageTypeSelect = document.getElementById('image-type-select');
    imageTypeSelect.addEventListener('change', (e) => {
        selectedImageType = e.target.value || 'current';
    });

    document.getElementById('btn-show-guidelines-link').addEventListener('click', () => {
        document.getElementById('popup-guidelines').classList.remove('hidden');
    });
    document.getElementById('btn-show-guidelines-badge').addEventListener('click', () => {
        document.getElementById('popup-guidelines').classList.remove('hidden');
    });

    // --------------- API + Data ---------------
    async function ensureSession() {
        if (currentSessionId) return currentSessionId;
        try {
            await createNewSession();
            return currentSessionId || null;
        } catch (e) {
            console.error('세션 생성 실패', e);
            showAlert('새 채팅 세션을 생성하지 못했습니다. 다시 시도해주세요.');
            return null;
        }
    }

    async function loadSessions() {
        try {
            const list = await fetchJson('/api/chat/sessions/');
            sessions = (list || [])
                .map(normalizeSession)
                .filter(Boolean);
            // 초기 진입 시에는 웰컴 화면 유지
            currentSessionId = null;
            showEmptyState();
            renderSidebar();
        } catch (error) {
            console.error('세션 목록 조회 실패', error);
            showEmptyState();
        }
    }

    async function loadSessionDetail(id) {
        const numericId = Number(id);
        if (!Number.isFinite(numericId)) {
            showAlert('세션을 불러오지 못했습니다.');
            return;
        }
        try {
            const detailRaw = await fetchJson(`/api/chat/sessions/${numericId}/`);
            let detail = normalizeSession(detailRaw);
            if (detail) {
                detail = mergePending(detail);
            }
            if (!detail) {
                showAlert('세션 정보를 불러오지 못했습니다.');
                return;
            }
            let replaced = false;
            sessions = sessions.map(s => {
                if (s.id === detail.id) {
                    replaced = true;
                    return detail;
                }
                return s;
            });
            if (!replaced) {
                sessions.unshift(detail);
            }
            currentSessionId = detail.id;
            if (getPendingCount(detail.id) > 0) {
                isSending = true;
                toggleInputDisabled(true);
                startPendingPolling();
            } else {
                isSending = false;
                toggleInputDisabled(false);
                stopPendingPolling();
            }
            excludedProductIds = new Set();
            renderSidebar();
            renderMessages();
        } catch (error) {
            console.error('세션 상세 조회 실패', error);
            showAlert(error.message || '세션을 불러오지 못했습니다.');
        }
    }

    async function createNewSession() {
        if (!Auth.requireLogin()) return;
        try {
            const raw = await fetchJson('/api/chat/sessions/', { method: 'POST' });
            const newId = Number(typeof raw === 'number' ? raw : (raw.id ?? raw.session_id ?? raw.pk ?? raw));
            if (!Number.isFinite(newId)) throw new Error('유효하지 않은 세션 ID입니다.');

            const detailRaw = await fetchJson(`/api/chat/sessions/${newId}/`);
            const sessionObj = normalizeSession(detailRaw) || { id: newId, title: '새 채팅', messages: [], state: {}, context: {} };

            sessions = [sessionObj, ...sessions.filter(s => s.id !== sessionObj.id)];
            currentSessionId = sessionObj.id;
            renderSidebar();
            renderMessages();
        } catch (error) {
            showAlert(error.message || '새 채팅 생성에 실패했습니다.');
            throw error;
        }
    }

    async function deleteSession(id) {
        try {
            const numericId = Number(id);
            await fetchJson(`/api/chat/sessions/${numericId}/`, { method: 'DELETE' });
            sessions = sessions.filter(s => Number(s.id) !== numericId);
            if (Number(currentSessionId) === numericId) {
                currentSessionId = sessions.length ? sessions[0].id : null;
                if (currentSessionId) {
                    await loadSessionDetail(currentSessionId);
                } else {
                    showEmptyState();
                    renderSidebar();
                }
            } else {
                renderSidebar();
            }
        } catch (error) {
            showAlert(error.message || '세션 삭제에 실패했습니다.');
        }
    }

    async function resetContext() {
        if (!currentSessionId) return;
        try {
            await fetchJson(`/api/chat/sessions/${currentSessionId}/reset/`, { method: 'POST' });
            await loadSessionDetail(currentSessionId);
            showAlert('세션을 초기화했습니다.');
        } catch (error) {
            showAlert(error.message || '세션 초기화에 실패했습니다.');
        }
    }

    // --------------- UI Helpers ---------------
    function toggleSidebarSection(sectionName) {
        const isHistory = sectionName === 'history';
        if (isHistory) {
            historyExpanded = !historyExpanded;
            if (historyExpanded) favoritesExpanded = false;
        } else {
            favoritesExpanded = !favoritesExpanded;
            if (favoritesExpanded) historyExpanded = false;
        }
        renderSidebar();
    }

    function updateSidebarVisibility() {
        isLoggedIn = Auth.isLoggedIn();
        const btnToggleSidebar = document.getElementById('btn-toggle-sidebar');
        if (isLoggedIn) {
            sidebar.classList.remove('hidden');
            btnToggleSidebar.classList.remove('hidden');
            sidebarLoggedOut.classList.add('hidden');
            sidebarLoggedIn.classList.remove('hidden');
            sessionContext.classList.remove('hidden');
            chatInput.disabled = false;
            chatInput.placeholder = '인테리어 고민을 물어보세요...';
            btnSend.disabled = false;
            btnSend.classList.remove('bg-gray-300', 'text-gray-500', 'cursor-not-allowed');
            btnSend.classList.add('bg-gradient-to-r', 'from-blue-500', 'to-blue-400', 'text-white');
            btnUploadImage.disabled = false;
            btnUploadImage.classList.remove('bg-gray-100', 'text-gray-400', 'cursor-not-allowed');
            btnUploadImage.classList.add('bg-gradient-to-r', 'from-blue-100', 'to-yellow-100', 'text-blue-600');
            imageTypeSelect.classList.remove('hidden');
            document.getElementById('welcome-auth-buttons').classList.add('hidden');
        } else {
            sidebar.classList.add('hidden');
            btnToggleSidebar.classList.add('hidden');
            sidebarLoggedOut.classList.remove('hidden');
            sidebarLoggedIn.classList.add('hidden');
            sessionContext.classList.add('hidden');
            document.getElementById('welcome-auth-buttons').classList.remove('hidden');
            document.getElementById('input-warning').classList.add('hidden');
            imageTypeSelect.classList.add('hidden');
        }
    }

    function renderHeaderNav() {
        const isLoggedIn = Auth.isLoggedIn();
        headerNav.innerHTML = `
            <button onclick="${isLoggedIn ? "window.location.href='/user/mypage/'" : "Auth.navigate('/user/mypage/')"}" class="px-4 py-2 text-[15px] font-normal text-gray-700 hover:text-blue-600 hover:bg-blue-50 rounded-lg transition-all leading-none">마이페이지</button>
            <button onclick="${isLoggedIn ? "window.location.href='/favorites/reference-board/'" : "Auth.navigate('/favorites/reference-board/')"}" class="px-4 py-2 text-[15px] font-normal text-gray-700 hover:text-blue-600 hover:bg-blue-50 rounded-lg transition-all leading-none">레퍼런스 보드</button>
            <button onclick="${isLoggedIn ? "window.location.href='/favorites/preference/'" : "Auth.navigate('/favorites/preference/')"}" class="px-4 py-2 text-[15px] font-normal text-gray-700 hover:text-blue-600 hover:bg-blue-50 rounded-lg transition-all leading-none">취향분석</button>
            ${isLoggedIn ? `<button onclick="Auth.logout()" class="px-4 py-2 text-[15px] font-normal text-gray-700 hover:text-blue-600 hover:bg-blue-50 rounded-lg transition-all leading-none">로그아웃</button>` : ``}
        `;
    }

    function renderExampleQuestions() {
        exampleQuestionsContainer.innerHTML = exampleQuestions.map(q => `
            <button onclick="handleExampleClick('${q}')" class="text-left px-5 py-3.5 bg-white/90 backdrop-blur border-2 border-blue-200 rounded-xl hover:border-blue-400 hover:shadow-lg transition-all transform hover:-translate-y-1 text-sm">
                <span class="text-blue-600 mr-2">💡</span>
                <span class="text-gray-700">${q}</span>
            </button>
        `).join('');
    }
    window.handleExampleClick = (q) => { if (Auth.requireLogin()) handleSend(q); };

    function renderSidebar() {
        const historySection = document.getElementById('history-section');
        const historyList = document.getElementById('history-list');
        const historyCount = document.getElementById('history-count');
        const iconHistory = document.getElementById('icon-history-toggle');

        historyCount.textContent = sessions.length;
        iconHistory.setAttribute('data-lucide', historyExpanded ? 'chevron-up' : 'chevron-down');

        if (historyExpanded) {
            historySection.classList.remove('flex-shrink-0');
            historySection.classList.add('flex-1', 'min-h-0');
            historyList.classList.remove('hidden');
        } else {
            historySection.classList.add('flex-shrink-0');
            historySection.classList.remove('flex-1', 'min-h-0');
            historyList.classList.add('hidden');
        }

        const favoritesSection = document.getElementById('favorites-section');
        const favoritesList = document.getElementById('favorites-list');
        const favoritesCount = document.getElementById('favorites-count');
        const iconFavorites = document.getElementById('icon-favorites-toggle');

        favoritesCount.textContent = favoriteProducts.length;
        iconFavorites.setAttribute('data-lucide', favoritesExpanded ? 'chevron-up' : 'chevron-down');

        if (favoritesExpanded) {
            favoritesSection.classList.remove('flex-shrink-0');
            favoritesSection.classList.add('flex-1', 'min-h-0');
            favoritesList.classList.remove('hidden');
        } else {
            favoritesSection.classList.add('flex-shrink-0');
            favoritesSection.classList.remove('flex-1', 'min-h-0');
            favoritesList.classList.add('hidden');
        }

        historyList.innerHTML = sessions.length === 0 ? `
            <div class="text-center py-7 text-gray-400 text-xs">
                <p>채팅 히스토리가 없어요</p>
                <p class="text-xs mt-1">새 채팅을 시작해보세요!</p>
            </div>
        ` : sessions
            .filter(s => Number.isFinite(Number(s.id)))
            .map(s => {
                const id = Number(s.id);
                const title = s.title || '새 채팅';
                const messageCount = Array.isArray(s.messages) ? s.messages.length : (s.message_count || 0);
                return `
            <div class="relative group">
                <button onclick="switchSession('${id}')" class="w-full text-left px-3.5 py-2.5 rounded-lg mb-2 transition-all text-sm ${id === Number(currentSessionId) ? 'bg-gradient-to-r from-blue-100 to-yellow-100 shadow-md' : 'hover:bg-blue-50'}">
                    <p class="truncate">${title}</p>
                    <p class="text-xs text-gray-500 mt-1">💬 ${messageCount}개의 메시지</p>
                </button>
                <button onclick="deleteSession('${id}')" class="absolute right-2 top-1/2 -translate-y-1/2 p-2 opacity-0 group-hover:opacity-100 hover:bg-red-100 rounded-lg transition-all">
                    <i data-lucide="trash-2" class="text-red-500 w-[15px] h-[15px]"></i>
                </button>
            </div>
            `;
        }).join('');

        favoritesList.innerHTML = favoriteProducts.length === 0 ? `
            <div class="text-center py-7 text-gray-400 text-xs">
                <i data-lucide="heart" class="mx-auto mb-2 opacity-30 w-[26px] h-[26px]"></i>
                <p>아직 관심 상품이 없어요</p>
                <p class="text-xs mt-1">채팅에서 상품을 추천받아보세요!</p>
            </div>
        ` : favoriteProducts.map(p => `
            <div class="bg-white rounded-lg overflow-hidden shadow-sm">
                <img src="${p.image}" alt="${p.name}" class="w-full h-28 object-cover">
                <div class="p-2.5">
                    <p class="text-xs mb-1 truncate">${p.name}</p>
                    <p class="text-xs text-blue-600 mb-2">${p.price}</p>
                    <div class="flex gap-2">
                        <a href="${p.link}" target="_blank" class="flex-1 text-center px-2.5 py-1.5 bg-blue-500 text-white rounded-md hover:bg-blue-600 transition-colors text-xs">구매하기</a>
                        <button onclick="removeFavorite('${p.id}')" class="p-1.5 hover:bg-red-100 rounded-md transition-colors" title="관심 상품 해제">
                            <i data-lucide="x" class="text-red-500 w-[15px] h-[15px]"></i>
                        </button>
                    </div>
                </div>
            </div>
        `).join('');

        const currentSession = sessions.find(s => s.id === currentSessionId);
        if (currentSession) {
            document.getElementById('ctx-category').textContent = currentSession.state?.category || currentSession.context?.category || '(미설정)';
            document.getElementById('ctx-mood').textContent = currentSession.state?.mood || currentSession.context?.mood || '(미설정)';
            document.getElementById('ctx-budget').textContent = currentSession.state?.budget || currentSession.context?.budget || '(미설정)';
            document.getElementById('ctx-space').textContent = currentSession.state?.space || currentSession.context?.space || '(미설정)';
            const modeEl = document.getElementById('ctx-mode');
            const mode = currentSession.state?.mode || currentSession.context?.mode || 'SMALL TALK';
            modeEl.textContent = mode;
            modeEl.className = `text-xs px-2 py-0.5 rounded-full text-white ${mode === 'SURVEY' ? 'bg-gradient-to-r from-purple-500 to-pink-500' :
                mode === 'RECOMMEND' ? 'bg-gradient-to-r from-green-500 to-emerald-500' :
                    'bg-gradient-to-r from-blue-500 to-cyan-500'
                }`;
        }

        lucide.createIcons();
    }

    window.switchSession = async (id) => { await loadSessionDetail(Number(id)); };
    window.deleteSession = (id) => {
        sessionToDelete = id;
        document.getElementById('popup-delete-confirm').classList.remove('hidden');
    };
    async function confirmDeleteSession() {
        if (sessionToDelete) {
            await deleteSession(sessionToDelete);
            document.getElementById('popup-delete-confirm').classList.add('hidden');
            sessionToDelete = null;
        }
    }

    function showEmptyState() {
        emptyState.classList.remove('hidden');
        messagesContainer.classList.add('hidden');
        document.getElementById('input-warning').classList.add('hidden');
    }

    // --------------- Messages Rendering ---------------
    function renderMessages() {
        if (!currentSessionId) {
            showEmptyState();
            return;
        }
        const session = sessions.find(s => s.id === currentSessionId);
        if (!session) {
            showEmptyState();
            return;
        }

        emptyState.classList.add('hidden');
        messagesContainer.classList.remove('hidden');
        document.getElementById('input-warning').classList.remove('hidden');

        messagesList.innerHTML = session.messages.map(msg => {
            const isUser = msg.role === 'user' || msg.sender === 'user';
            const time = formatTimestamp(msg.created_at || msg.timestamp || msg.createdAt);
            const imageLabel = msg.image_type === 'reference' ? '레퍼런스' : (msg.image_type === 'current' ? '방 사진' : null);
            const imgSrc = msg.image || msg.image_url || msg.imageUrl;
            const isPending = msg._pending;
            const pendingSpinner = isPending ? `
                <div class="flex items-center gap-2 text-sm text-gray-500">
                    <span class="spinner-circle"></span>
                    <span>응답 생성 중...</span>
                </div>
            ` : '';

            const products = msg.recommended_products || msg.products || [];
            let productsHtml = '';
            if (products.length > 0) {
                productsHtml = `
                    <div class="mt-3 grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
                        ${products.map(p => `
                            <div class="bg-white rounded-2xl border border-gray-200 shadow-sm hover:shadow-md transition-all overflow-hidden">
                                <div class="aspect-square bg-gray-50">
                                    <img src="${p.image_url || p.image || 'https://via.placeholder.com/300'}" alt="${p.product_name || p.name || '상품'}" class="w-full h-full object-cover">
                                </div>
                                <div class="p-3">
                                    <p class="text-sm font-semibold text-gray-800 truncate">${p.product_name || p.name || '상품명'}</p>
                                    <p class="text-xs text-gray-500 mb-2 truncate">${p.brand_name || p.brand || '브랜드'}</p>
                                    <p class="text-blue-600 font-semibold mb-3">${p.price || ''}</p>
                                    <div class="flex gap-2">
                                        <a href="${p.link_url || p.link || '#'}" target="_blank" class="flex-1 text-center px-3 py-2 bg-blue-500 text-white rounded-lg hover:bg-blue-600 transition-colors text-xs">구매하기</a>
                                        <button onclick="addFavorite(${JSON.stringify({
                                            id: msg.id + '_' + (p.product_id || p.id || ''),
                                            name: p.product_name || p.name || '상품명',
                                            price: p.price || '',
                                            brand: p.brand_name || p.brand || '',
                                            link: p.link_url || p.link || '#',
                                            image: p.image_url || p.image || '/static/img/placeholder.png'
                                        }).replace(/"/g, '&quot;')})" class="px-2 py-2 border border-pink-300 text-pink-500 rounded-lg hover:bg-pink-50 transition-colors text-xs">
                                            ♥
                                        </button>
                                    </div>
                                </div>
                            </div>
                        `).join('')}
                    </div>
                `;
            }

            return `
                <div class="flex ${isUser ? 'justify-end' : 'justify-start'}">
                    <div class="max-w-[70%] px-5 py-3.5 rounded-2xl shadow-md text-sm ${isUser ? 'bg-gradient-to-r from-blue-500 to-blue-400 text-white' : 'bg-white text-gray-800 border border-blue-100'}">
                        ${imgSrc ? `<div class="mb-2.5">
                            ${imageLabel ? `<span class="inline-block mb-1 text-[11px] px-2 py-1 rounded-full bg-blue-100 text-blue-700">${imageLabel}</span>` : ''}
                            <img src="${imgSrc}" class="rounded-xl max-w-full shadow-md">
                        </div>` : ''}
                        ${isPending ? pendingSpinner : (msg.text ? `<p class="leading-relaxed">${msg.text}</p>` : '')}
                        ${time ? `<p class="text-xs mt-2 ${isUser ? 'text-blue-100' : 'text-gray-400'}">${time}</p>` : ''}
                    </div>
                </div>
                ${productsHtml}
            `;
        }).join('') + '<div class="h-4"></div>';

        lucide.createIcons();
        messagesContainer.scrollTop = messagesContainer.scrollHeight;
    }

    // --------------- Messaging ---------------
    async function handleSend(customText) {
        if (!Auth.requireLogin() || isSending) return;

        // ✅ 중복 클릭/엔터 방지를 위해 최대한 앞단에서 바로 잠금
        isSending = true;
        toggleInputDisabled(true);

        const text = customText || chatInput.value.trim();
        if (!text && !uploadedImage) {
            isSending = false;
            toggleInputDisabled(false);
            return;
        }
        if (text.length > 200) {
            showAlert('질문은 최대 200자 이내로 입력해주세요.');
            isSending = false;
            toggleInputDisabled(false);
            return;
        }

        const sessionId = await ensureSession();
        if (!sessionId) {
            isSending = false;
            toggleInputDisabled(false);
            return;
        }

        // preserve current image before clearing
        const previewImage = uploadedImage;
        const fileToSend = uploadedFile;
        const imageTypeToSend = previewImage ? selectedImageType : null;

        chatInput.value = '';
        chatInput.style.height = '44px';
        charCount.textContent = '0/200';
        uploadedImage = null;
        btnUploadImage.disabled = false;
        imagePreviewContainer.classList.add('hidden');
        chatInput.disabled = false;
        chatInput.placeholder = '인테리어 고민을 물어보세요...';

        // Optimistic UI: 사용자 메시지 + 응답 대기 표시
        const now = Date.now();
        const tempUserId = `temp-user-${now}`;
        const tempAssistantId = `temp-assistant-${now}`;
        const userCreatedAt = new Date(now).toISOString();
        const assistantCreatedAt = new Date(now + 1000).toISOString(); // 보조 버블이 사용자 메시지 아래에 오도록 +1초
        pushMessageToSession(sessionId, {
            id: tempUserId,
            role: 'user',
            text,
            created_at: userCreatedAt,
            image: previewImage,
            image_type: imageTypeToSend,
        });
        pushMessageToSession(sessionId, {
            id: tempAssistantId,
            role: 'assistant',
            text: '응답 생성 중...',
            created_at: assistantCreatedAt,
            _pending: true,
        });
        addPending(sessionId, [
            {
                id: tempUserId,
                role: 'user',
                text,
                created_at: userCreatedAt,
                image: previewImage,
                image_type: imageTypeToSend,
            },
            {
                id: tempAssistantId,
                role: 'assistant',
                text: '응답 생성 중...',
                created_at: assistantCreatedAt,
                _pending: true,
            },
        ]);
        renderMessages();
        toggleInputDisabled(true);
        startPendingPolling();

        const formData = new FormData();
        formData.append('session_id', sessionId);
        formData.append('text', text);
        formData.append('more_like_this', 'false');
        if (fileToSend) {
            formData.append('image', fileToSend);
            formData.append('image_type', imageTypeToSend || 'current');
        }

        try {
            const res = await fetch('/api/chat/messages/', {
                method: 'POST',
                credentials: 'include',
                headers: { 'X-CSRFToken': getCsrfToken() },
                body: formData,
            });
            const data = await res.json().catch(() => ({}));
            if (!res.ok) {
                throw new Error(data.detail || '메시지 전송에 실패했습니다.');
            }
            const newSessionId = Number(data?.session?.id || sessionId);
            if (Number.isFinite(newSessionId)) {
                currentSessionId = newSessionId;
                await loadSessionDetail(newSessionId);
            } else {
                await loadSessionDetail(sessionId);
            }
            uploadedFile = null;
            clearPending(sessionId);
        } catch (error) {
            removePendingMessage(sessionId, tempAssistantId);
            await loadSessionDetail(sessionId);
            showAlert(error.message || '메시지 전송에 실패했습니다.');
        } finally {
            isSending = false;
            toggleInputDisabled(getPendingCount(sessionId) > 0);
        }
    }

    function toggleInputDisabled(disabled) {
        chatInput.disabled = disabled;
        btnSend.disabled = disabled;
        btnUploadImage.disabled = disabled;
        if (imageTypeSelect) imageTypeSelect.disabled = disabled;
        if (disabled) {
            btnSend.classList.add('opacity-50', 'cursor-not-allowed');
            btnUploadImage.classList.add('opacity-50', 'cursor-not-allowed');
        } else {
            btnSend.classList.remove('opacity-50', 'cursor-not-allowed');
            btnUploadImage.classList.remove('opacity-50', 'cursor-not-allowed');
            updateAttachmentLock();
        }
    }

    function handleImageUpload(e) {
        const file = e.target.files[0];
        if (file) {
            if (!file.type.match(/^image\/(jpeg|png)$/)) {
                showAlert('JPG 또는 PNG 파일만 업로드 가능합니다.');
                return;
            }
            if (file.size > 10 * 1024 * 1024) {
                showAlert('이미지 크기는 10MB를 초과할 수 없습니다.');
                return;
            }
            uploadedFile = file;
            const reader = new FileReader();
            reader.onload = (ev) => {
                uploadedImage = ev.target.result;
                imagePreview.src = uploadedImage;
                imagePreviewContainer.classList.remove('hidden');
                btnUploadImage.disabled = false;
            };
            reader.readAsDataURL(file);
        }
        updateAttachmentLock();
    }

    // --------------- Favorites & Feedback ---------------
    window.removeFavorite = (id) => {
        favoriteProducts = favoriteProducts.filter(p => p.id !== id);
        State.set('favoriteProducts', favoriteProducts);
        renderSidebar();
        renderMessages();
    };

    window.addFavorite = (product) => {
        if (!favoriteProducts.find(p => p.id === product.id)) {
            favoriteProducts.push(product);
            State.set('favoriteProducts', favoriteProducts);
            renderSidebar();
            renderMessages();
        }
    };

    window.handleLike = (msgId, liked) => {
        const session = sessions.find(s => s.id === currentSessionId);
        const msg = session?.messages?.find(m => m.id === msgId);
        if (!session || !msg) return;
        msg.liked = liked;
        renderMessages();
    };

    window.handleRequestMore = () => {
        showAlert('추가 추천 요청은 추후 API 연동 시 지원됩니다.');
    };

    // --------------- Alerts ---------------
    function showAlert(msg) {
        const el = document.getElementById('alert-message');
        const popup = document.getElementById('popup-alert');
        if (el && popup) {
            el.textContent = msg;
            popup.classList.remove('hidden');
        } else {
            alert(msg);
        }
    }
});
