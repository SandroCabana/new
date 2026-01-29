/**
 * LTI Learning Tracker - Popup JavaScript
 * Handles UI interactions and communication with background service worker
 */

// ===== State Management =====
let isTracking = false;
let pendingData = [];

// ===== DOM Elements =====
const elements = {
    // Status
    statusIndicator: document.getElementById('status-indicator'),
    statusText: document.getElementById('status-text'),

    // Tabs
    tabs: document.querySelectorAll('.tab'),
    panels: document.querySelectorAll('.panel'),

    // Track panel
    toggleBtn: document.getElementById('toggle-tracking'),
    toggleText: document.getElementById('toggle-text'),
    sessionInfo: document.getElementById('session-info'),
    pagesCount: document.getElementById('pages-count'),
    sessionTime: document.getElementById('session-time'),
    pendingData: document.getElementById('pending-data'),
    pendingList: document.getElementById('pending-list'),
    previewBtn: document.getElementById('preview-btn'),
    sendBtn: document.getElementById('send-btn'),

    // History panel
    refreshHistory: document.getElementById('refresh-history'),
    totalInteractions: document.getElementById('total-interactions'),
    totalResources: document.getElementById('total-resources'),
    totalTime: document.getElementById('total-time'),
    historyList: document.getElementById('history-list'),

    // Settings panel
    apiUrl: document.getElementById('api-url'),
    contextId: document.getElementById('context-id'),
    // Login form
    loginForm: document.getElementById('login-form'),
    loginEmail: document.getElementById('login-email'),
    loginPassword: document.getElementById('login-password'),
    loginBtn: document.getElementById('login-btn'),
    loginError: document.getElementById('login-error'),
    userInfo: document.getElementById('user-info'),
    userName: document.getElementById('user-name'),
    disconnect: document.getElementById('disconnect'),
    saveSettings: document.getElementById('save-settings'),
    clearLocal: document.getElementById('clear-local'),

    // Modal
    previewModal: document.getElementById('preview-modal'),
    closeModal: document.getElementById('close-modal'),
    previewSummary: document.getElementById('preview-summary'),
    previewItems: document.getElementById('preview-items'),
    cancelSend: document.getElementById('cancel-send'),
    confirmSend: document.getElementById('confirm-send'),
};

// ===== Initialization =====
document.addEventListener('DOMContentLoaded', init);

async function init() {
    // Load saved settings
    await loadSettings();

    // Load current state from background
    await loadState();

    // Setup event listeners
    setupEventListeners();
}

async function loadSettings() {
    const settings = await chrome.storage.local.get(['apiUrl', 'contextId', 'authToken', 'userName']);

    if (settings.apiUrl) {
        elements.apiUrl.value = settings.apiUrl;
    }
    if (settings.contextId) {
        elements.contextId.value = settings.contextId;
    }
    if (settings.authToken && settings.userName) {
        showUserConnected(settings.userName);
    }
}

async function loadState() {
    const state = await chrome.storage.local.get(['isTracking', 'pendingData', 'sessionStartTime']);

    isTracking = state.isTracking || false;
    pendingData = state.pendingData || [];

    updateTrackingUI();
    updatePendingDataUI();

    if (isTracking && state.sessionStartTime) {
        updateSessionTime(state.sessionStartTime);
    }
}

// ===== Event Listeners =====
function setupEventListeners() {
    // Tab switching
    elements.tabs.forEach(tab => {
        tab.addEventListener('click', () => switchTab(tab.dataset.tab));
    });

    // Tracking controls
    elements.toggleBtn.addEventListener('click', toggleTracking);
    elements.previewBtn.addEventListener('click', showPreview);
    elements.sendBtn.addEventListener('click', () => showPreview());

    // History
    elements.refreshHistory.addEventListener('click', loadHistory);

    // Settings
    elements.saveSettings.addEventListener('click', saveSettings);
    elements.loginBtn.addEventListener('click', handleLogin);
    elements.disconnect.addEventListener('click', handleLogout);
    elements.clearLocal.addEventListener('click', clearLocalData);

    // Modal
    elements.closeModal.addEventListener('click', hideModal);
    elements.cancelSend.addEventListener('click', hideModal);
    elements.confirmSend.addEventListener('click', confirmAndSend);
}

// ===== Tab Navigation =====
function switchTab(tabName) {
    elements.tabs.forEach(t => t.classList.remove('active'));
    elements.panels.forEach(p => p.classList.remove('active'));

    document.querySelector(`[data-tab="${tabName}"]`).classList.add('active');
    document.getElementById(`${tabName}-panel`).classList.add('active');

    // Load data when switching to history
    if (tabName === 'history') {
        loadHistory();
    }
}

// ===== Tracking Controls =====
async function toggleTracking() {
    isTracking = !isTracking;

    if (isTracking) {
        // Start tracking session
        await chrome.storage.local.set({
            isTracking: true,
            sessionStartTime: Date.now(),
        });

        // Notify background script
        chrome.runtime.sendMessage({ action: 'startTracking' });
    } else {
        // Stop tracking session
        await chrome.storage.local.set({ isTracking: false });
        chrome.runtime.sendMessage({ action: 'stopTracking' });
    }

    updateTrackingUI();
}

function updateTrackingUI() {
    if (isTracking) {
        elements.statusIndicator.classList.add('active');
        elements.statusText.textContent = 'Activo';
        elements.toggleBtn.innerHTML = '<span class="btn-icon">⏸</span><span id="toggle-text">Pausar Sesión</span>';
        elements.toggleBtn.classList.remove('btn-primary');
        elements.toggleBtn.classList.add('btn-danger');
        elements.sessionInfo.classList.remove('hidden');
    } else {
        elements.statusIndicator.classList.remove('active');
        elements.statusText.textContent = 'Desactivado';
        elements.toggleBtn.innerHTML = '<span class="btn-icon">▶</span><span id="toggle-text">Iniciar Sesión</span>';
        elements.toggleBtn.classList.remove('btn-danger');
        elements.toggleBtn.classList.add('btn-primary');
        elements.sessionInfo.classList.add('hidden');
    }
}

function updateSessionTime(startTime) {
    const elapsed = Math.floor((Date.now() - startTime) / 1000);
    const minutes = Math.floor(elapsed / 60);
    const seconds = elapsed % 60;
    elements.sessionTime.textContent = `${String(minutes).padStart(2, '0')}:${String(seconds).padStart(2, '0')}`;
}

// ===== Pending Data =====
function updatePendingDataUI() {
    if (pendingData.length > 0) {
        elements.pendingData.classList.remove('hidden');
        elements.pagesCount.textContent = pendingData.length;

        elements.pendingList.innerHTML = pendingData.map((item, index) => `
      <div class="pending-item">
        <span class="url" title="${item.url}">${new URL(item.url).hostname}</span>
        <span class="time">${formatDuration(item.timeSpent)}</span>
        <button class="remove" data-index="${index}">×</button>
      </div>
    `).join('');

        // Add remove handlers
        elements.pendingList.querySelectorAll('.remove').forEach(btn => {
            btn.addEventListener('click', (e) => removePendingItem(parseInt(e.target.dataset.index)));
        });
    } else {
        elements.pendingData.classList.add('hidden');
    }
}

async function removePendingItem(index) {
    pendingData.splice(index, 1);
    await chrome.storage.local.set({ pendingData });
    updatePendingDataUI();
}

function formatDuration(seconds) {
    if (seconds < 60) return `${Math.round(seconds)}s`;
    return `${Math.floor(seconds / 60)}m ${Math.round(seconds % 60)}s`;
}

// ===== Preview & Send =====
async function showPreview() {
    const settings = await chrome.storage.local.get(['apiUrl', 'authToken', 'contextId']);

    if (!settings.apiUrl || !settings.authToken) {
        alert('Por favor configura la URL del API y conecta con Moodle primero.');
        switchTab('settings');
        return;
    }

    if (pendingData.length === 0) {
        alert('No hay datos pendientes para enviar.');
        return;
    }

    // Call preview API
    try {
        const payload = {
            userID: 1, // Will be set by server from token
            associatedPLE: settings.contextId || 'default',
            trackedDataList: pendingData.map(item => ({
                activityType: item.type || 'webpage',
                associatedURL: item.url,
                associatedDomains: item.domains || [],
                associatedKeywords: item.keywords || [],
                startTime: new Date(item.startTime).toISOString(),
                endTime: new Date(item.endTime).toISOString(),
            }))
        };

        const response = await fetch(`${settings.apiUrl}/interactions/preview/`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Token ${settings.authToken}`,
            },
            body: JSON.stringify(payload),
        });

        if (!response.ok) {
            throw new Error(`HTTP ${response.status}`);
        }

        const preview = await response.json();
        showPreviewModal(preview);

    } catch (error) {
        console.error('Preview error:', error);
        alert(`Error al obtener vista previa: ${error.message}`);
    }
}

function showPreviewModal(preview) {
    elements.previewSummary.innerHTML = `
    <p><strong>Resumen de datos a enviar:</strong></p>
    <ul>
      <li>📄 ${preview.summary.total_items} página(s) visitadas</li>
      <li>🆕 ${preview.summary.new_resources} recurso(s) nuevos</li>
      <li>🔄 ${preview.summary.existing_resources} recurso(s) existentes</li>
      <li>⏱️ Tiempo total: ${preview.summary.total_time_formatted}</li>
    </ul>
  `;

    elements.previewItems.innerHTML = preview.interactions_to_create.map(item => `
    <div class="pending-item">
      <span class="url">${new URL(item.resource_url).hostname}</span>
      <span class="time">${formatDuration(item.time_spent)}</span>
    </div>
  `).join('');

    elements.previewModal.classList.remove('hidden');
}

function hideModal() {
    elements.previewModal.classList.add('hidden');
}

async function confirmAndSend() {
    const settings = await chrome.storage.local.get(['apiUrl', 'authToken', 'contextId']);

    try {
        const payload = {
            userID: 1,
            associatedPLE: settings.contextId || 'default',
            trackedDataList: pendingData.map(item => ({
                activityType: item.type || 'webpage',
                associatedURL: item.url,
                associatedDomains: item.domains || [],
                associatedKeywords: item.keywords || [],
                startTime: new Date(item.startTime).toISOString(),
                endTime: new Date(item.endTime).toISOString(),
            }))
        };

        const response = await fetch(`${settings.apiUrl}/interactions/tracked-data-batch/`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Token ${settings.authToken}`,
            },
            body: JSON.stringify(payload),
        });

        if (!response.ok) {
            throw new Error(`HTTP ${response.status}`);
        }

        // Clear pending data
        pendingData = [];
        await chrome.storage.local.set({ pendingData: [] });

        hideModal();
        updatePendingDataUI();
        alert('✓ Datos enviados correctamente');

    } catch (error) {
        console.error('Send error:', error);
        alert(`Error al enviar datos: ${error.message}`);
    }
}

// ===== History =====
async function loadHistory() {
    const settings = await chrome.storage.local.get(['apiUrl', 'authToken']);

    if (!settings.apiUrl || !settings.authToken) {
        elements.historyList.innerHTML = '<p class="placeholder">Conecta con Moodle para ver tu historial</p>';
        return;
    }

    try {
        // Load stats
        const statsResponse = await fetch(`${settings.apiUrl}/interactions/user-stats/`, {
            headers: { 'Authorization': `Token ${settings.authToken}` }
        });

        if (statsResponse.ok) {
            const stats = await statsResponse.json();
            elements.totalInteractions.textContent = stats.total_interactions;
            elements.totalResources.textContent = stats.total_resources;
            elements.totalTime.textContent = formatDuration(stats.total_time_spent || 0);
        }

        // Load recent history
        const historyResponse = await fetch(`${settings.apiUrl}/interactions/user-history/?page_size=10`, {
            headers: { 'Authorization': `Token ${settings.authToken}` }
        });

        if (historyResponse.ok) {
            const history = await historyResponse.json();

            if (history.results.length === 0) {
                elements.historyList.innerHTML = '<p class="placeholder">No hay interacciones registradas</p>';
            } else {
                elements.historyList.innerHTML = history.results.map(item => `
          <div class="history-item">
            <div class="title">${item.resource.title}</div>
            <div class="meta">
              ${item.interaction_type} • ${formatDuration(item.time_spent || 0)} • 
              ${new Date(item.timestamp).toLocaleDateString()}
            </div>
          </div>
        `).join('');
            }
        }

    } catch (error) {
        console.error('History error:', error);
        elements.historyList.innerHTML = '<p class="placeholder">Error al cargar historial</p>';
    }
}

// ===== Settings =====
async function saveSettings() {
    await chrome.storage.local.set({
        apiUrl: elements.apiUrl.value,
        contextId: elements.contextId.value,
    });
    alert('✓ Configuración guardada');
}

async function handleLogin() {
    const apiUrl = elements.apiUrl.value;
    const email = elements.loginEmail.value.trim();
    const password = elements.loginPassword.value;

    // Hide previous errors
    elements.loginError.classList.add('hidden');

    if (!apiUrl) {
        showLoginError('Por favor ingresa la URL del API primero');
        return;
    }

    if (!email || !password) {
        showLoginError('Ingresa tu email y contraseña');
        return;
    }

    // Disable button during login
    elements.loginBtn.disabled = true;
    elements.loginBtn.textContent = '⏳ Iniciando sesión...';

    try {
        const response = await fetch(`${apiUrl}/auth/login/`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ email, password })
        });

        const data = await response.json();

        if (response.ok) {
            await chrome.storage.local.set({
                authToken: data.token,
                userName: data.display_name,
                userEmail: data.email,
            });
            showUserConnected(data.display_name);
            // Clear password field
            elements.loginPassword.value = '';
        } else {
            showLoginError(data.error || 'Credenciales inválidas');
        }
    } catch (error) {
        showLoginError(`Error de conexión: ${error.message}`);
    } finally {
        elements.loginBtn.disabled = false;
        elements.loginBtn.textContent = '🔐 Iniciar Sesión';
    }
}

function showLoginError(message) {
    elements.loginError.textContent = message;
    elements.loginError.classList.remove('hidden');
}

function showUserConnected(name) {
    elements.loginForm.classList.add('hidden');
    elements.userInfo.classList.remove('hidden');
    elements.userName.textContent = name;
}

async function handleLogout() {
    const apiUrl = elements.apiUrl.value;
    const settings = await chrome.storage.local.get(['authToken']);

    // Call logout endpoint if we have a token
    if (settings.authToken && apiUrl) {
        try {
            await fetch(`${apiUrl}/auth/logout/`, {
                method: 'POST',
                headers: { 'Authorization': `Token ${settings.authToken}` }
            });
        } catch (error) {
            console.error('Logout error:', error);
        }
    }

    await chrome.storage.local.remove(['authToken', 'userName', 'userEmail']);
    elements.loginForm.classList.remove('hidden');
    elements.userInfo.classList.add('hidden');
}

async function clearLocalData() {
    if (confirm('¿Borrar todos los datos locales? Esto eliminará datos pendientes no enviados.')) {
        pendingData = [];
        await chrome.storage.local.set({ pendingData: [] });
        updatePendingDataUI();
        alert('✓ Datos locales borrados');
    }
}

// ===== Listen for updates from background =====
chrome.runtime.onMessage.addListener((message) => {
    if (message.action === 'pendingDataUpdated') {
        loadState();
    }
});
