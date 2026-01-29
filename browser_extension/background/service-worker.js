/**
 * LTI Learning Tracker - Background Service Worker
 * Handles page tracking, time measurement, and data persistence
 */

// ===== State =====
let activeTab = null;
let tabStartTime = null;
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
            // Save current page before stopping
            if (activeTab && tabStartTime) {
                savePageData(activeTab, tabStartTime);
            }
            trackingEnabled = false;
            activeTab = null;
            tabStartTime = null;
            console.log('Tracking stopped');
            break;

        case 'pageData':
            // Receive page metadata from content script
            if (trackingEnabled && message.data) {
                updateActiveTabMetadata(message.data);
            }
            break;
    }
    return true;
});

// ===== Tab Tracking =====
chrome.tabs.onActivated.addListener(async (activeInfo) => {
    if (!trackingEnabled) return;

    // Save time for previous tab
    if (activeTab && tabStartTime) {
        await savePageData(activeTab, tabStartTime);
    }

    // Start tracking new tab
    try {
        const tab = await chrome.tabs.get(activeInfo.tabId);
        if (isTrackableUrl(tab.url)) {
            activeTab = {
                id: activeInfo.tabId,
                url: tab.url,
                title: tab.title,
            };
            tabStartTime = Date.now();

            // Request metadata from content script
            chrome.tabs.sendMessage(activeInfo.tabId, { action: 'getPageData' }).catch(() => { });
        } else {
            activeTab = null;
            tabStartTime = null;
        }
    } catch (error) {
        console.error('Error tracking tab:', error);
    }
});

chrome.tabs.onUpdated.addListener((tabId, changeInfo, tab) => {
    if (!trackingEnabled) return;

    // Track URL changes (navigation)
    if (changeInfo.status === 'complete' && tab.active) {
        if (activeTab && activeTab.id === tabId && activeTab.url !== tab.url) {
            // URL changed, save previous and start new
            savePageData(activeTab, tabStartTime);

            if (isTrackableUrl(tab.url)) {
                activeTab = {
                    id: tabId,
                    url: tab.url,
                    title: tab.title,
                };
                tabStartTime = Date.now();

                // Request metadata
                chrome.tabs.sendMessage(tabId, { action: 'getPageData' }).catch(() => { });
            } else {
                activeTab = null;
                tabStartTime = null;
            }
        }
    }
});

// Tab closed
chrome.tabs.onRemoved.addListener((tabId) => {
    if (activeTab && activeTab.id === tabId) {
        if (trackingEnabled && tabStartTime) {
            savePageData(activeTab, tabStartTime);
        }
        activeTab = null;
        tabStartTime = null;
    }
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

// ===== Page Data Handling =====
function updateActiveTabMetadata(metadata) {
    if (activeTab) {
        activeTab.title = metadata.title || activeTab.title;
        activeTab.keywords = metadata.keywords || [];
        activeTab.description = metadata.description || '';
        activeTab.type = metadata.type || 'webpage';
    }
}

async function savePageData(tab, startTime) {
    const timeSpent = (Date.now() - startTime) / 1000;

    // Only save if meaningful time spent (more than 5 seconds)
    if (timeSpent < 5) return;

    const pageData = {
        url: tab.url,
        title: tab.title || new URL(tab.url).hostname,
        startTime: startTime,
        endTime: Date.now(),
        timeSpent: timeSpent,
        keywords: tab.keywords || [],
        type: tab.type || 'webpage',
        domains: [new URL(tab.url).hostname],
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
    if (alarm.name === 'periodicSave' && trackingEnabled && activeTab && tabStartTime) {
        // Save current state periodically without resetting
        const currentTime = Date.now();
        const timeSpent = (currentTime - tabStartTime) / 1000;

        if (timeSpent >= 30) {
            // Save accumulated time
            savePageData(activeTab, tabStartTime);
            // Reset start time
            tabStartTime = currentTime;
        }
    }
});
