/**
 * LTI Learning Tracker - Popup JavaScript
 * Handles UI interactions and communication with background service worker
 */

// ===== State Management =====
let isTracking = false;
let pendingData = [];
let sessionTimer = null;

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

    // Tracking Views
    welcomeView: document.getElementById('welcome-view'),
    trackingView: document.getElementById('tracking-view'),

    // Settings
    connectionCard: document.getElementById('connection-status-card'),
    connTitle: document.getElementById('conn-title'),
    connDesc: document.getElementById('conn-desc'),
    userInfoCard: document.getElementById('user-info'),
    userEmailDisplay: document.getElementById('user-email-display'),
    courseSelectorGroup: document.getElementById('course-selector-group'),
    toggleAdvanced: document.getElementById('toggle-advanced'),
    advancedContent: document.getElementById('advanced-content'),

    apiUrl: document.getElementById('api-url'),
    contextId: document.getElementById('context-id'),
    contextSelector: document.getElementById('context-selector'),
    contextIdContainer: document.getElementById('context-id-container'),

    // Login form
    loginForm: document.getElementById('login-form'),
    loginEmail: document.getElementById('login-email'),
    loginPassword: document.getElementById('login-password'),
    loginBtn: document.getElementById('login-btn'),
    loginError: document.getElementById('login-error'),
    showRegister: document.getElementById('show-register'),

    // Register form
    registerForm: document.getElementById('register-form'),
    regUsername: document.getElementById('reg-username'),
    regEmail: document.getElementById('reg-email'),
    regPassword: document.getElementById('reg-password'),
    registerBtn: document.getElementById('register-btn'),
    registerError: document.getElementById('register-error'),
    showLogin: document.getElementById('show-login'),

    authSection: document.getElementById('auth-section'),
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

    // Listen for storage changes to update UI in real-time
    chrome.storage.onChanged.addListener((changes, area) => {
        if (area === 'local' && (changes.pendingData || changes.isTracking || changes.sessionStartTime)) {
            loadState();
        }
    });
}

async function loadSettings() {
    const results = await chrome.storage.local.get([
        'apiUrl', 'contextId', 'isTracking', 'authToken',
        'jwtAccess', 'userName', 'ltiPaired'
    ]);

    if (results.apiUrl) {
        elements.apiUrl.value = results.apiUrl;
    } else {
        elements.apiUrl.value = 'http://localhost:8080';
    }

    if (results.contextId) {
        elements.contextId.value = results.contextId;
    }

    // Support both legacy Token auth and new JWT auto-pairing
    const hasAuth = results.jwtAccess || results.authToken;
    if (hasAuth) {
        showUserConnected(results.userName, results.userEmail);
        updateConnectionStatus(true, results.userName);
        
        if (results.ltiPaired) {
            // Indicate auto-pairing success
            const nameEl = elements.userName;
            if (nameEl && !nameEl.textContent.includes('🔗')) {
                nameEl.textContent = '🔗 ' + (results.userName || 'LTI Usuario');
            }
        }
        loadUserContexts();
    } else {
        showUserDisconnected();
        updateConnectionStatus(false);
    }
}

// ===== API Helpers =====
async function getAuthSettings() {
    const settings = await chrome.storage.local.get(['authToken', 'jwtAccess', 'apiUrl', 'contextId']);
    const token = settings.jwtAccess || settings.authToken;
    
    if (!token) return null;
    
    // JWT tokens contain dots, legacy tokens don't
    const scheme = token.includes('.') ? 'Bearer' : 'Token';
    
    return {
        apiUrl: settings.apiUrl || 'http://localhost:8080',
        token: token,
        authHeader: `${scheme} ${token}`,
        contextId: settings.contextId
    };
}

async function loadUserContexts() {
    const settings = await getAuthSettings();
    if (!settings) return;

    try {
        const response = await fetch(`${settings.apiUrl}/auth/user-contexts/`, {
            headers: { 'Authorization': settings.authHeader }
        });

        if (response.ok) {
            const data = await response.json();
            const selector = elements.contextSelector;
            
            // Clear existing options except first
            selector.innerHTML = '<option value="">-- Selecciona un curso --</option>';
            
            if (data.contexts && data.contexts.length > 0) {
                // ... (populate options)
                data.contexts.forEach(ctx => {
                    const option = document.createElement('option');
                    option.value = ctx.context_id;
                    option.textContent = ctx.title || ctx.context_id;
                    if (ctx.context_id === settings.contextId) {
                        option.selected = true;
                    }
                    selector.appendChild(option);
                });
                
                const manualOption = document.createElement('option');
                manualOption.value = "__MANUAL__";
                manualOption.textContent = "➕ Ingresar ID manualmente...";
                selector.appendChild(manualOption);
            } else {
                const option = document.createElement('option');
                option.disabled = true;
                option.textContent = "No se encontraron cursos previos.";
                selector.appendChild(option);
                elements.contextIdContainer.classList.remove('hidden');
            }
        } else {
            console.error('Fetch error:', response.status);
            const selector = elements.contextSelector;
            selector.innerHTML = '<option value="">❌ Error al cargar cursos</option>';
        }
    } catch (error) {
        console.error('Error loading contexts:', error);
        const selector = elements.contextSelector;
        selector.innerHTML = '<option value="">⚠️ Error de conexión</option>';
    }
}


// Logic to show/hide manual input
document.getElementById('context-selector').addEventListener('change', (e) => {
    if (e.target.value === "__MANUAL__") {
        elements.contextIdContainer.classList.remove('hidden');
    } else {
        elements.contextIdContainer.classList.add('hidden');
        if (e.target.value) {
            elements.contextId.value = e.target.value;
        }
    }
});

async function saveSettings() {
    const apiUrlValue = elements.apiUrl.value.trim();
    let contextIdValue = elements.contextSelector.value;
    
    if (contextIdValue === "__MANUAL__" || !contextIdValue) {
        contextIdValue = elements.contextId.value.trim();
    }

    if (!apiUrlValue) {
        alert('Por favor ingresa la URL del API');
        return;
    }


    await chrome.storage.local.set({
        apiUrl: apiUrlValue,
        contextId: contextIdValue,
    });

    alert('✅ Configuración guardada');
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

    // Advanced settings toggle
    elements.toggleAdvanced.addEventListener('click', () => {
        const isOpen = elements.advancedContent.classList.toggle('hidden');
        elements.toggleAdvanced.classList.toggle('open', !isOpen);
    });

    // Settings
    elements.saveSettings.addEventListener('click', saveSettings);
    elements.loginBtn.addEventListener('click', handleLogin);
    elements.showRegister.addEventListener('click', (e) => {
        e.preventDefault();
        elements.loginForm.classList.add('hidden');
        elements.registerForm.classList.remove('hidden');
    });
    elements.showLogin.addEventListener('click', (e) => {
        e.preventDefault();
        elements.registerForm.classList.add('hidden');
        elements.loginForm.classList.remove('hidden');
    });
    elements.registerBtn.addEventListener('click', handleRegister);
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

    const tab = Array.from(elements.tabs).find(t => t.dataset.tab === tabName);
    const panel = document.getElementById(`${tabName}-panel`);

    if (tab && panel) {
        tab.classList.add('active');
        panel.classList.add('active');
    }

    if (tabName === 'settings') {
        loadUserContexts();
    }

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
    if (sessionTimer) clearTimeout(sessionTimer);
    
    const update = () => {
        if (!isTracking) return;
        const elapsed = Math.floor((Date.now() - startTime) / 1000);
        const minutes = Math.floor(elapsed / 60);
        const seconds = elapsed % 60;
        elements.sessionTime.textContent = `${String(minutes).padStart(2, '0')}:${String(seconds).padStart(2, '0')}`;
        sessionTimer = setTimeout(update, 1000);
    };
    
    update();
}

// ===== Pending Data =====
function updatePendingDataUI() {
    if (pendingData.length > 0) {
        elements.pendingData.classList.remove('hidden');
        elements.pagesCount.textContent = pendingData.length;

        elements.pendingList.innerHTML = pendingData.map((item, index) => `
      <div class="pending-item">
        <div class="item-main">
          <div class="title">${item.title || new URL(item.url).hostname}</div>
          <div class="url-path">${new URL(item.url).pathname}</div>
        </div>
        <div class="item-meta">
          <span class="time">${formatDuration(item.timeSpent)}</span>
          <button class="remove" data-index="${index}">×</button>
        </div>
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
    const settings = await getAuthSettings();
    if (!settings) {
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
            userID: settings.global_user_id,
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
                'Authorization': settings.authHeader
            },
            body: JSON.stringify(payload)
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
    const settings = await getAuthSettings();
    if (!settings || pendingData.length === 0) return;

    try {
        const payload = {
            userID: settings.global_user_id,
            associatedPLE: settings.contextId || 'default',
            trackedDataList: pendingData.map(item => ({
                activityType: item.type || 'webpage',
                associatedURL: item.url,
                associatedDomains: item.domains || [],
                associatedKeywords: item.keywords || [],
                startTime: new Date(item.startTime).toISOString(),
                endTime: new Date(item.endTime).toISOString(),
                activeTime: item.activeTime || item.timeSpent,
                scrollDepth: item.scrollDepth || 0,
                contentSummary: item.contentSummary || '',
                videoData: item.videoData || null,
            }))

        };

        const response = await fetch(`${settings.apiUrl}/interactions/tracked-data-batch/`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': settings.authHeader,
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
    const settings = await getAuthSettings();
    if (!settings) {
        elements.historyList.innerHTML = '<p class="placeholder">Conecta con Moodle para ver tu historial</p>';
        return;
    }

    try {
        // Load stats
        const statsResponse = await fetch(`${settings.apiUrl}/interactions/user-stats/`, {
            headers: { 'Authorization': settings.authHeader }
        });

        if (statsResponse.ok) {
            const stats = await statsResponse.json();
            elements.totalInteractions.textContent = stats.total_interactions;
            elements.totalResources.textContent = stats.total_resources;
            elements.totalTime.textContent = formatDuration(stats.total_time_spent || 0);
        }

        // Load recent history
        const historyResponse = await fetch(`${settings.apiUrl}/interactions/user-history/?page_size=10`, {
            headers: { 'Authorization': settings.authHeader }
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


// ===== Authentication =====
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
                apiUrl: apiUrl, // Save the apiUrl that worked
            });
            showUserConnected(data.display_name, data.email);
            updateConnectionStatus(true, data.display_name);
            loadUserContexts(); // Also load contexts immediately
            loadHistory(); // Load history too
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

function showUserConnected(name, email) {
    elements.welcomeView.classList.add('hidden');
    elements.trackingView.classList.remove('hidden');
    
    elements.userInfoCard.classList.remove('hidden');
    elements.userName.textContent = name || 'Usuario';
    elements.userEmailDisplay.textContent = email || '';
    elements.courseSelectorGroup.classList.remove('hidden');
    
    // Hide auth section within advanced settings since we are connected
    elements.authSection.classList.add('hidden');
}

function showUserDisconnected() {
    elements.welcomeView.classList.remove('hidden');
    elements.trackingView.classList.add('hidden');
    
    elements.userInfoCard.classList.add('hidden');
    elements.courseSelectorGroup.classList.add('hidden');
    elements.authSection.classList.remove('hidden');
}

function updateConnectionStatus(isConnected, name = '') {
    const card = elements.connectionCard;
    if (isConnected) {
        card.className = 'connection-card status-connected';
        elements.connTitle.textContent = '✓ Conectado';
        elements.connDesc.textContent = `Sincronizado correctamente como ${name}.`;
    } else {
        card.className = 'connection-card status-disconnected';
        elements.connTitle.textContent = '⚠️ Desconectado';
        elements.connDesc.textContent = 'Abre Moodle para activar la extensión automáticamente.';
    }
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

    await chrome.storage.remove(['authToken', 'userName', 'userEmail', 'ltiPaired', 'jwtAccess']);
    showUserDisconnected();
    updateConnectionStatus(false);
}

async function handleRegister() {
    const apiUrl = elements.apiUrl.value;
    const username = elements.regUsername.value.trim();
    const email = elements.regEmail.value.trim();
    const firstName = elements.regFirstName.value.trim();
    const lastName = elements.regLastName.value.trim();
    const password = elements.regPassword.value;
    const passwordConfirm = elements.regPasswordConfirm.value;

    elements.registerError.classList.add('hidden');

    if (!apiUrl) {
        showRegisterError('Configura la URL del API primero');
        return;
    }

    if (!username || !email || !password || !passwordConfirm || !firstName || !lastName) {
        showRegisterError('Todos los campos son obligatorios');
        return;
    }

    if (password !== passwordConfirm) {
        showRegisterError('Las contraseñas no coinciden');
        return;
    }

    elements.registerBtn.disabled = true;
    elements.registerBtn.textContent = '⏳ Creando cuenta...';

    try {
        const response = await fetch(`${apiUrl}/auth/register/`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                username,
                email,
                first_name: firstName,
                last_name: lastName,
                password,
                password_confirm: passwordConfirm
            })
        });

        const data = await response.json();

        if (response.ok) {
            await chrome.storage.local.set({
                authToken: data.token,
                userName: data.display_name,
                userEmail: data.email,
                apiUrl: apiUrl, // Save the apiUrl that worked
            });
            showUserConnected(data.display_name, data.email);
            updateConnectionStatus(true, data.display_name);
            loadUserContexts();
            loadHistory();
            // Clear password fields
            elements.regPassword.value = '';
            elements.regPasswordConfirm.value = '';
        } else {
            // Handle field errors
            let errorMsg = 'Error al registrar';
            if (typeof data === 'object') {
                errorMsg = Object.values(data).flat().join(' ');
            }
            showRegisterError(errorMsg);
        }
    } catch (error) {
        showRegisterError(`Error de conexión: ${error.message}`);
    } finally {
        elements.registerBtn.disabled = false;
        elements.registerBtn.textContent = '✨ Crear Cuenta';
    }
}

function showRegisterError(message) {
    elements.registerError.textContent = message;
    elements.registerError.classList.remove('hidden');
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

    // Auto-pairing: show connected state immediately
    if (message.action === 'ltiPairingStored') {
        const name = message.user?.name || 'LTI Usuario';
        const email = message.user?.email || '';
        showUserConnected(name, email);
        updateConnectionStatus(true, name);
        
        // Auto-fill context if provided
        if (message.context_id && elements.contextId) {
            elements.contextId.value = message.context_id;
        }
        loadUserContexts();
    }
});
