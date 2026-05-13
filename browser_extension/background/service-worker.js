/**
 * LTI Learning Tracker - Background Service Worker
 * Handles page tracking, time measurement, and data persistence
 */

// ===== State =====
let trackedTabs = new Map(); // tabId -> { url, title, startTime, metadata... }
let trackingEnabled = false;

// ===== Initialization =====
chrome.runtime.onInstalled.addListener(() => {
    console.log('LTI Learning Tracker installed');

    // Initialize storage
    chrome.storage.local.get(['isTracking', 'pendingData'], (result) => {
        trackingEnabled = result.isTracking || false;
        if (!result.pendingData) {
            chrome.storage.local.set({ pendingData: [] });
        }
    });
});

// ===== Message Handling =====
chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
    switch (message.action) {
        case 'startTracking':
            trackingEnabled = true;
            console.log('Tracking started');
            break;

        case 'stopTracking':
            // Save all current tabs before stopping
            for (const [tabId, data] of trackedTabs) {
                savePageData(tabId, data);
            }
            trackingEnabled = false;
            trackedTabs.clear();
            console.log('Tracking stopped');
            break;

        case 'pageData':
            // Receive page metadata from content script
            const tabId = sender.tab?.id;
            if (trackingEnabled && message.data && tabId) {
                updateTabMetadata(tabId, message.data);
            }
            break;

        case 'ltiPairingReceived':
            handleLtiPairing(message);
            break;
    }
});

// ===== Tab Tracking =====
chrome.tabs.onActivated.addListener(async (activeInfo) => {
    if (!trackingEnabled) return;

    // Start tracking new tab if not already tracked
    try {
        const tab = await chrome.tabs.get(activeInfo.tabId);
        if (isTrackableUrl(tab.url) && !trackedTabs.has(activeInfo.tabId)) {
            trackedTabs.set(activeInfo.tabId, {
                url: tab.url,
                title: tab.title,
                startTime: Date.now(),
                engagement: { scroll_depth: 0, active_time: 0 }
            });

            // Request metadata from content script
            chrome.tabs.sendMessage(activeInfo.tabId, { action: 'getPageData' }).catch(() => { });
        }
    } catch (error) {
        console.error('Error tracking tab:', error);
    }
});

chrome.tabs.onUpdated.addListener((tabId, changeInfo, tab) => {
    if (!trackingEnabled) return;

    // Track URL changes (navigation)
    if (changeInfo.status === 'complete' && tab.url) {
        const existing = trackedTabs.get(tabId);
        
        if (existing && existing.url !== tab.url) {
            // URL changed, save previous state and start new tracking for this tab
            savePageData(tabId, existing);
            
            if (isTrackableUrl(tab.url)) {
                trackedTabs.set(tabId, {
                    url: tab.url,
                    title: tab.title,
                    startTime: Date.now(),
                    engagement: { scroll_depth: 0, active_time: 0 }
                });
                chrome.tabs.sendMessage(tabId, { action: 'getPageData' }).catch(() => { });
            } else {
                trackedTabs.delete(tabId);
            }
        } else if (!existing && isTrackableUrl(tab.url)) {
            // New trackable tab
            trackedTabs.set(tabId, {
                url: tab.url,
                title: tab.title,
                startTime: Date.now(),
                engagement: { scroll_depth: 0, active_time: 0 }
            });
            chrome.tabs.sendMessage(tabId, { action: 'getPageData' }).catch(() => { });
        }
    }
});

// Tab closed
chrome.tabs.onRemoved.addListener((tabId) => {
    const data = trackedTabs.get(tabId);
    if (data && trackingEnabled) {
        savePageData(tabId, data);
    }
    trackedTabs.delete(tabId);
});

// ===== URL Filtering =====
function isTrackableUrl(url) {
    if (!url) return false;

    // Skip internal pages
    if (url.startsWith('chrome://') ||
        url.startsWith('chrome-extension://') ||
        url.startsWith('about:') ||
        url.startsWith('edge://') ||
        url.startsWith('file://')) {
        return false;
    }

    return true;
}

// ===== LTI Auto-Pairing Handler =====
async function handleLtiPairing({ tokens, user, context_id }) {
    try {
        await chrome.storage.local.set({
            // JWT tokens
            jwtAccess: tokens.access,
            jwtRefresh: tokens.refresh,
            // Fallback: keep authToken pointing to the access token so
            // existing fetch calls that read authToken still work temporarily
            authToken: tokens.access,
            // User identity
            globalUserId: user?.global_user_id || '',
            userName: user?.name || '',
            userEmail: user?.email || '',
            // Context
            contextId: context_id || '',
            // Flag so popup knows this session was auto-paired
            ltiPaired: true,
        });

        console.log('[LTI Tracker] Pairing stored. GlobalUser:', user?.global_user_id);

        // Notify popup (if open) so it can update the UI
        chrome.runtime.sendMessage({ action: 'ltiPairingStored', user, context_id })
            .catch(() => { /* popup may be closed, ignore */ });

    } catch (err) {
        console.error('[LTI Tracker] Error storing pairing:', err);
    }
}

// ===== Page Data Handling =====
function updateTabMetadata(tabId, metadata) {
    const tabData = trackedTabs.get(tabId);
    if (tabData) {
        tabData.title = metadata.title || tabData.title;
        tabData.keywords = metadata.keywords || [];
        tabData.description = metadata.description || '';
        tabData.type = metadata.type || 'webpage';
        tabData.contentSummary = metadata.contentSummary || '';
        tabData.engagement = metadata.engagement || { scroll_depth: 0, active_time: 0 };
        tabData.videoData = metadata.videoData || null;
    }
}

async function savePageData(tabId, data) {
    const timeSpent = (Date.now() - data.startTime) / 1000;

    // Only save if meaningful time spent (more than 5 seconds)
    if (timeSpent < 5) return;

    const pageData = {
        url: data.url,
        title: data.title || new URL(data.url).hostname,
        startTime: data.startTime,
        endTime: Date.now(),
        timeSpent: timeSpent,
        activeTime: data.engagement?.active_time || timeSpent,
        scrollDepth: data.engagement?.scroll_depth || 0,
        contentSummary: data.contentSummary || '',
        videoData: data.videoData || null,
        keywords: data.keywords || [],
        type: data.type || 'webpage',
        domains: [new URL(data.url).hostname],
    };


    // Add to pending data
    const storage = await chrome.storage.local.get(['pendingData']);
    const pendingData = storage.pendingData || [];

    // Check for duplicate URLs and merge time
    const existingIndex = pendingData.findIndex(p => p.url === pageData.url);
    if (existingIndex >= 0) {
        pendingData[existingIndex].timeSpent += pageData.timeSpent;
        pendingData[existingIndex].endTime = pageData.endTime;
    } else {
        pendingData.push(pageData);
    }

    await chrome.storage.local.set({ pendingData });

    // Notify popup if open
    chrome.runtime.sendMessage({ action: 'pendingDataUpdated' }).catch(() => { });

    console.log('Saved page:', pageData.url, 'Time:', timeSpent.toFixed(1), 's');
}

// ===== Periodic Save (Alarm) =====
chrome.alarms.create('periodicSave', { periodInMinutes: 1 });

chrome.alarms.onAlarm.addListener((alarm) => {
    if (alarm.name === 'periodicSave' && trackingEnabled) {
        const currentTime = Date.now();

        for (const [tabId, data] of trackedTabs) {
            const timeSpent = (currentTime - data.startTime) / 1000;

            if (timeSpent >= 30) {
                // Save accumulated time for this specific tab
                savePageData(tabId, data);
                // Reset start time for this tab
                data.startTime = currentTime;
            }
        }
    }
});
