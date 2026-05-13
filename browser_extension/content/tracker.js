// ===== LTI Auto-Pairing =====
// Listens for the JWT pairing message sent by the Moodle LTI dashboard.
// When the user opens the recommender inside Moodle, the dashboard page emits
// a LTI_RECOMMENDER_PAIRING event via window.postMessage.  The content script
// captures it and forwards the tokens to the service worker so the extension
// is authenticated without any manual login step.
window.addEventListener('message', (event) => {
    // Accept messages from any origin (the Moodle server URL varies per deployment)
    if (!event.data || event.data.type !== 'LTI_RECOMMENDER_PAIRING') return;

    const { tokens, user, context_id } = event.data.payload || {};
    if (!tokens || !tokens.access) return;

    console.log('[LTI Tracker] Auto-pairing received for user:', user?.name);

    // Forward to service worker to persist credentials
    chrome.runtime.sendMessage({
        action: 'ltiPairingReceived',
        tokens,
        user,
        context_id,
    }).catch(() => { /* popup/SW may not be open yet */ });
});

// ===== Advanced Engagement Tracking =====
let startTime = Date.now();
let lastActivityTime = Date.now();
let activeTimeSeconds = 0;
let maxScrollDepth = 0;
let isTabActive = true;

// Track active time vs idle time
function updateActiveTime() {
    if (isTabActive && (Date.now() - lastActivityTime < 30000)) { // 30s idle threshold
        activeTimeSeconds += 1;
    }
}
setInterval(updateActiveTime, 1000);

// Listen for activity
['mousemove', 'keydown', 'scroll', 'click'].forEach(event => {
    window.addEventListener(event, () => {
        lastActivityTime = Date.now();
    }, { passive: true });
});

// Listen for visibility changes
document.addEventListener('visibilitychange', () => {
    isTabActive = !document.hidden;
});

// Track scroll depth
window.addEventListener('scroll', () => {
    const windowHeight = window.innerHeight;
    const fullHeight = document.documentElement.scrollHeight;
    const scrollTop = window.pageYOffset || document.documentElement.scrollTop;
    const currentDepth = Math.round(((scrollTop + windowHeight) / fullHeight) * 100);
    maxScrollDepth = Math.max(maxScrollDepth, currentDepth);
}, { passive: true });

// ===== Page Metadata & Content Extraction =====
function extractPageMetadata() {
    const metadata = {
        title: document.title,
        url: window.location.href,
        keywords: [],
        description: '',
        type: 'webpage',
        contentSummary: extractContentSummary(),
        engagement: {
            scroll_depth: Math.min(maxScrollDepth, 100),
            active_time: activeTimeSeconds,
        }
    };

    // Extract meta description
    const descriptionMeta = document.querySelector('meta[name="description"]');
    if (descriptionMeta) {
        metadata.description = descriptionMeta.content;
    }

    // Extract keywords
    const keywordsMeta = document.querySelector('meta[name="keywords"]');
    if (keywordsMeta) {
        metadata.keywords = keywordsMeta.content.split(',').map(k => k.trim()).filter(k => k);
    }

    // Detect page type
    metadata.type = detectPageType();

    // YouTube specific data
    if (metadata.type === 'video' && window.location.href.includes('youtube.com')) {
        metadata.videoData = extractYouTubeData();
    }

    return metadata;
}

function extractContentSummary() {
    // Try to find the main content area
    const mainSelectors = ['article', 'main', '.content', '#content', '.post-content', '.article-body'];
    let mainElement = null;
    
    for (const selector of mainSelectors) {
        mainElement = document.querySelector(selector);
        if (mainElement) break;
    }

    if (!mainElement) mainElement = document.body;

    // Extract text and clean it up
    const text = mainElement.innerText || '';
    return text.substring(0, 500).replace(/\s+/g, ' ').trim();
}

function extractYouTubeData() {
    const videoId = new URLSearchParams(window.location.search).get('v');
    const videoTitle = document.querySelector('h1.ytd-video-primary-info-renderer')?.innerText;
    const channelName = document.querySelector('#channel-name a')?.innerText;
    
    return {
        videoId,
        videoTitle,
        channelName,
    };
}

function detectPageType() {
    const url = window.location.href.toLowerCase();
    const contentType = document.contentType || '';

    // Video platforms
    if (url.includes('youtube.com') ||
        url.includes('vimeo.com') ||
        url.includes('dailymotion.com') ||
        document.querySelector('video')) {
        return 'video';
    }

    // PDF
    if (url.endsWith('.pdf') || contentType.includes('pdf')) {
        return 'pdf';
    }

    // Educational platforms
    if (url.includes('coursera.org') ||
        url.includes('edx.org') ||
        url.includes('udemy.com') ||
        url.includes('khan') ||
        url.includes('moodle')) {
        return 'course';
    }

    // Documentation
    if (url.includes('docs.') ||
        url.includes('documentation') ||
        url.includes('wiki') ||
        url.includes('readme')) {
        return 'documentation';
    }

    // Articles
    if (document.querySelector('article') ||
        document.querySelector('[role="article"]') ||
        url.includes('blog') ||
        url.includes('article')) {
        return 'article';
    }

    return 'webpage';
}

// ===== Message Handling =====
chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
    if (message.action === 'getPageData') {
        const metadata = extractPageMetadata();
        chrome.runtime.sendMessage({ action: 'pageData', data: metadata });
    }
    return true;
});

// ===== Initial Load =====
// Send metadata when page loads and periodically
function sendMetadata() {
    try {
        const metadata = extractPageMetadata();
        chrome.runtime.sendMessage({ action: 'pageData', data: metadata }).catch(() => {
            // Extension context may be invalidated, ignore
        });
    } catch (e) {
        // Ignore errors
    }
}

if (document.readyState === 'complete') {
    sendMetadata();
} else {
    window.addEventListener('load', sendMetadata);
}

// Periodically send updates for active sessions
setInterval(() => {
    sendMetadata();
}, 10000); // Every 10 seconds

