/**
 * Shared Logic for MOOD ON (Vanilla JS)
 */

// State Management
const State = {
  get(key, defaultValue) {
    const value = localStorage.getItem(`moodon_${key}`);
    if (value === null) return defaultValue;
    try {
      return JSON.parse(value);
    } catch (e) {
      return value;
    }
  },
  set(key, value) {
    if (typeof value === 'object') {
      localStorage.setItem(`moodon_${key}`, JSON.stringify(value));
    } else {
      localStorage.setItem(`moodon_${key}`, value);
    }
  },
  remove(key) {
    localStorage.removeItem(`moodon_${key}`);
  }
};

// CSRF & Fetch Helper (always read from cookie)
function getCookie(name) {
  const value = `; ${document.cookie}`;
  const parts = value.split(`; ${name}=`);
  if (parts.length === 2) {
    return decodeURIComponent(parts.pop().split(';').shift());
  }
  return null;
}

function getCsrfToken() {
  return getCookie('csrftoken') || '';
}

async function fetchJson(url, options = {}) {
  const csrfToken = getCsrfToken();
  const { body, headers = {}, method = 'GET' } = options;

  const mergedHeaders = {
    'Content-Type': 'application/json',
    ...headers,
  };
  if (csrfToken && !('X-CSRFToken' in mergedHeaders)) {
    mergedHeaders['X-CSRFToken'] = csrfToken;
  }

  const fetchOptions = {
    method,
    credentials: 'include',
    headers: mergedHeaders,
  };

  if (body !== undefined) {
    fetchOptions.body = typeof body === 'string' ? body : JSON.stringify(body);
  }

  const res = await fetch(url, fetchOptions);
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    const error = new Error(data.detail || '요청 처리 중 오류가 발생했습니다.');
    error.status = res.status;
    error.data = data;
    throw error;
  }
  return data;
}

// Auth Helper (session + localStorage 호환)
let sessionAuthenticated = false;
const Auth = {
  isLoggedIn() {
    if (sessionAuthenticated) return true;
    const local = State.get('isLoggedIn', false);
    return local === 'true' || local === true;
  },
  async login(email, password) {
    // If password is provided, perform actual login request; otherwise just mark state.
    if (typeof password !== 'undefined') {
      const body = password ? { email, password } : { email };
      await fetchJson('/api/accounts/login/', {
        method: 'POST',
        body,
      });
      sessionAuthenticated = true;
    }
    State.set('isLoggedIn', 'true');
    if (email) State.set('userEmail', email);
    return true;
  },
  async logout() {
    try {
      await fetchJson('/api/accounts/logout/', { method: 'POST' });
    } catch (e) {
      // ignore logout error to avoid blocking UX
    } finally {
      State.remove('isLoggedIn');
      State.remove('userEmail');
      State.remove('userPreferences');
      State.remove('favoriteProducts');
      State.remove('chat_sessions');
      window.location.href = '/login/';
    }
  },
  requireLogin() {
    if (!this.isLoggedIn()) {
      this.showLoginPopup();
      return false;
    }
    return true;
  },
  navigate(url) {
    if (this.requireLogin()) {
      window.location.href = url;
    } else {
      window.location.href = `/login/?next=${encodeURIComponent(url)}`;
    }
  },
  async syncSession() {
    try {
      const res = await fetchJson('/api/accounts/session/', { method: 'GET' });
      if (res && res.is_authenticated) {
        sessionAuthenticated = true;
        State.set('isLoggedIn', 'true');
        if (res.email) State.set('userEmail', res.email);
        return true;
      }
      sessionAuthenticated = false;
      State.remove('isLoggedIn');
      return false;
    } catch (e) {
      sessionAuthenticated = false;
      return false;
    }
  },
  showLoginPopup() {
    // Prevent duplicate popups
    if (document.getElementById('login-required-popup')) return;

    const popupHtml = `
        <div id="login-required-popup" class="fixed inset-0 bg-black/50 backdrop-blur-sm flex items-center justify-center z-50 p-4 transition-opacity opacity-0 mx-auto">
          <div class="bg-white rounded-3xl p-8 max-w-md w-full shadow-2xl transform scale-95 transition-transform">
            <div class="text-center mb-6">
              <div class="w-20 h-20 bg-gradient-to-br from-blue-400 to-blue-300 rounded-full flex items-center justify-center mx-auto mb-4 shadow-lg">
                <span class="text-4xl">🔒</span>
              </div>
              <h2 class="text-2xl mb-3 text-gray-800">로그인이 필요합니다</h2>
              <p class="text-gray-600">해당 서비스를 이용하시려면<br/>먼저 로그인해주세요.</p>
            </div>
            <div class="flex gap-3">
              <button onclick="const el=document.getElementById('login-required-popup'); el.style.opacity='0'; setTimeout(()=>el.remove(), 300);" class="flex-1 py-4 border-2 border-gray-300 rounded-2xl hover:bg-gray-50 transition-all text-gray-700">취소</button>
              <button onclick="window.location.href='/login/'" class="flex-1 py-4 bg-gradient-to-r from-blue-500 to-blue-400 text-white rounded-2xl hover:from-blue-600 hover:to-blue-500 transition-all shadow-lg">로그인하기</button>
            </div>
          </div>
        </div>
        `;
    document.body.insertAdjacentHTML('beforeend', popupHtml);

    // Animation
    requestAnimationFrame(() => {
      const el = document.getElementById('login-required-popup');
      if (el) {
        el.style.opacity = '1';
        el.querySelector('div').style.transform = 'scale(1)';
      }
    });
  }
};

// Expose to window for inline event handlers
window.State = State;
window.Auth = Auth;

// Header Component
function renderHeader(currentPage) {
  const isLoggedIn = Auth.isLoggedIn();

  // Always show nav items, but check auth for restricted ones
  const navItems = `
        <button onclick="${isLoggedIn ? "window.location.href='/user/mypage/'" : "Auth.navigate('/user/mypage/')"}" class="px-5 py-2 text-[15px] font-normal text-gray-700 hover:text-blue-600 leading-none transition-colors">마이페이지</button>
        <button onclick="${isLoggedIn ? "window.location.href='/favorites/reference-board/'" : "Auth.navigate('/favorites/reference-board/')"}" class="px-5 py-2 text-[15px] font-normal text-gray-700 hover:text-blue-600 leading-none transition-colors">레퍼런스 보드</button>
        <button onclick="${isLoggedIn ? "window.location.href='/favorites/preference/'" : "Auth.navigate('/favorites/preference/')"}" class="px-5 py-2 text-[15px] font-normal text-gray-700 hover:text-blue-600 leading-none transition-colors">취향분석</button>
        ${isLoggedIn ?
      `<button onclick="Auth.logout()" class="px-5 py-2 text-[15px] bg-gradient-to-r from-blue-500 to-blue-400 text-white rounded-full hover:from-blue-600 hover:to-blue-500 transition-all shadow-md leading-none">로그아웃</button>`
      :
      `` // No Login/Signup buttons in header per new design (they are in body empty state)
    }
    `;

  const headerHtml = `
    <header class="fixed top-0 left-0 right-0 z-50 bg-white/85 backdrop-blur-md border-b border-blue-100 shadow-sm">
      <div class="max-w-7xl mx-auto px-6 py-[14px] flex items-center justify-between">
        <button onclick="window.location.href='/chat/'" class="flex items-center gap-2.5 hover:opacity-80 transition-opacity whitespace-nowrap">
          <div class="w-9 h-9 bg-gradient-to-br from-blue-400 to-blue-300 rounded-full flex items-center justify-center shadow-md">
            <i data-lucide="lamp" class="text-white w-[18px] h-[18px]"></i>
          </div>
          <span class="text-[20px] font-medium leading-none bg-gradient-to-r from-blue-600 to-blue-400 bg-clip-text text-transparent select-none">MOOD ON</span>
        </button>
        <nav class="flex items-center gap-[10px] whitespace-nowrap">
          ${navItems}
        </nav>
      </div>
    </header>
    `;

  // Insert header at the beginning of body
  document.body.insertAdjacentHTML('afterbegin', headerHtml);

  // Initialize icons
  if (window.lucide) {
    lucide.createIcons();
  }
}

// Initialize on load
document.addEventListener('DOMContentLoaded', () => {
  // Icons are initialized in renderHeader or manually if header is not used
  if (window.lucide) lucide.createIcons();
});

// Export helpers
window.fetchJson = fetchJson;
window.getCsrfToken = getCsrfToken;
