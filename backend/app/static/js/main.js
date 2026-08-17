// Global Helper Script for Flask Application Frontend

const API_BASE = '/api';

// ==========================================
// Theme Management (Light / Dark Mode)
// ==========================================
function getSavedTheme() {
  return localStorage.getItem('app-theme') || 'dark';
}

function applyTheme(theme) {
  const root = document.documentElement;
  const isLight = theme === 'light';
  if (isLight) {
    root.classList.remove('dark');
    root.classList.add('light');
    root.setAttribute('data-theme', 'light');
  } else {
    root.classList.remove('light');
    root.classList.add('dark');
    root.setAttribute('data-theme', 'dark');
  }
  localStorage.setItem('app-theme', theme);
  updateThemeToggleIcons(isLight);
}

function toggleTheme() {
  const currentTheme = document.documentElement.classList.contains('light') ? 'light' : 'dark';
  const newTheme = currentTheme === 'light' ? 'dark' : 'light';
  applyTheme(newTheme);
}

function updateThemeToggleIcons(isLight) {
  const toggleBtns = document.querySelectorAll('.theme-toggle-btn, [data-theme-toggle]');
  toggleBtns.forEach(btn => {
    btn.setAttribute('title', isLight ? 'Switch to Dark Mode' : 'Switch to Light Mode');
    btn.setAttribute('aria-label', isLight ? 'Switch to Dark Mode' : 'Switch to Light Mode');
    btn.innerHTML = isLight
      ? '<i data-lucide="moon" class="w-4 h-4 text-indigo-600"></i>'
      : '<i data-lucide="sun" class="w-4 h-4 text-amber-400"></i>';
  });
  if (window.lucide) {
    lucide.createIcons();
  }
}

// Initialize theme immediately
(function initTheme() {
  const savedTheme = getSavedTheme();
  applyTheme(savedTheme);
})();

function getToken() {
  return localStorage.getItem('talent_sphere_token') || getCookie('access_token');
}

function getAuthToken() {
  return localStorage.getItem('talent_sphere_token') || getCookie('access_token') || '';
}

function getCookie(name) {
  const value = `; ${document.cookie}`;
  const parts = value.split(`; ${name}=`);
  if (parts.length === 2) return parts.pop().split(';').shift();
  return '';
}

function getUser() {
  const u = localStorage.getItem('talent_sphere_user');
  try {
    return u ? JSON.parse(u) : null;
  } catch {
    return null;
  }
}

function setAuthSession(token, user, rememberEmail = null) {
  localStorage.setItem('talent_sphere_token', token);
  localStorage.setItem('talent_sphere_user', JSON.stringify(user));
  document.cookie = `access_token=${token}; max-age=86400; path=/; SameSite=Lax`;

  if (rememberEmail) {
    localStorage.setItem('talent_sphere_remember_email', rememberEmail);
  } else if (rememberEmail === false) {
    localStorage.removeItem('talent_sphere_remember_email');
  }
}

function logout() {
  try {
    localStorage.removeItem('talent_sphere_token');
    localStorage.removeItem('talent_sphere_user');
  } catch (e) {}
  document.cookie = 'access_token=; max-age=0; path=/; SameSite=Lax; expires=Thu, 01 Jan 1970 00:00:00 UTC;';
  window.location.href = '/logout';
}

// Fetch wrapper with automatic JWT header injection
async function apiFetch(endpoint, options = {}) {
  const token = getToken();
  const headers = options.headers || {};
  
  if (token && !(options.body instanceof FormData)) {
    headers['Content-Type'] = 'application/json';
  }
  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }

  const response = await fetch(`${API_BASE}${endpoint}`, {
    ...options,
    headers
  });

  if (response.status === 401 && window.location.pathname !== '/login') {
    logout();
    throw new Error('Unauthorized');
  }

  return response;
}

// Notifications Polling & Toggling
let notifPollInterval = null;

function toggleNotifDropdown() {
  const menu = document.getElementById('notif-dropdown-menu');
  if (menu) {
    const isHidden = menu.classList.contains('hidden');
    menu.classList.toggle('hidden');
    if (isHidden) {
      fetchNotifications();
    }
  }
}

async function fetchNotifications() {
  const notifContainer = document.getElementById('notif-list-container');
  const badgeCount = document.getElementById('notif-badge-count');
  if (!notifContainer) return;

  try {
    const res = await apiFetch('/notifications');
    if (!res.ok) return;
    const notifs = await res.json();
    
    const countRes = await apiFetch('/notifications/unread-count');
    const { unread_count } = await countRes.json();

    if (badgeCount) {
      if (unread_count > 0) {
        badgeCount.innerText = unread_count > 9 ? '9+' : unread_count;
        badgeCount.classList.remove('hidden');
      } else {
        badgeCount.classList.add('hidden');
      }
    }

    if (notifs.length === 0) {
      notifContainer.innerHTML = '<div class="p-6 text-center text-slate-400 text-xs">No notifications yet</div>';
      return;
    }

    notifContainer.innerHTML = notifs.map(n => `
      <div onclick="markNotifRead('${n.id}')" class="p-3.5 transition-colors cursor-pointer flex gap-3 ${n.is_read ? 'opacity-70 bg-slate-900/30' : 'bg-slate-800/40 hover:bg-slate-800/80'}">
        <div class="p-2 rounded-lg bg-slate-800 border border-slate-700 shrink-0 self-start">
          <i data-lucide="bell" class="w-4 h-4 text-indigo-400"></i>
        </div>
        <div class="flex-1 min-w-0">
          <div class="flex items-center justify-between gap-2">
            <p class="text-xs font-semibold text-white truncate">${n.title}</p>
            ${!n.is_read ? '<span class="w-2 h-2 rounded-full bg-indigo-500 shrink-0"></span>' : ''}
          </div>
          <p class="text-xs text-slate-300 mt-1 line-clamp-2">${n.message}</p>
          <p class="text-[10px] text-slate-500 mt-1">${new Date(n.created_at).toLocaleString()}</p>
        </div>
      </div>
    `).join('');

    if (window.lucide) lucide.createIcons();
  } catch (e) {
    console.error(e);
  }
}

async function markNotifRead(id) {
  try {
    await apiFetch(`/notifications/${id}/read`, { method: 'POST' });
    fetchNotifications();
  } catch (e) {
    console.error(e);
  }
}

async function markAllNotifsRead() {
  try {
    await apiFetch('/notifications/read-all', { method: 'POST' });
    fetchNotifications();
  } catch (e) {
    console.error(e);
  }
}

// Modal Trigger Functions with Voice Assistant state safety
function openModal(id) {
  const el = document.getElementById(id);
  if (el) el.classList.remove('hidden');
  if (id === 'voice-assistant-modal' && typeof resetVoiceAssistantState === 'function') {
    resetVoiceAssistantState();
  }
}

function closeModal(id) {
  const el = document.getElementById(id);
  if (el) el.classList.add('hidden');
  if (id === 'voice-assistant-modal' && typeof stopVoiceSpeech === 'function') {
    stopVoiceSpeech();
  }
}

document.addEventListener('DOMContentLoaded', () => {
  if (getToken() && window.location.pathname !== '/login') {
    fetchNotifications();
    notifPollInterval = setInterval(fetchNotifications, 15000);
  }

  // Close notifications dropdown on outside click
  document.addEventListener('click', (event) => {
    const menu = document.getElementById('notif-dropdown-menu');
    if (!menu || menu.classList.contains('hidden')) return;

    const notifBtn = event.target.closest('button[onclick*="toggleNotifDropdown"]');
    if (!menu.contains(event.target) && !notifBtn) {
      menu.classList.add('hidden');
    }
  });
});
