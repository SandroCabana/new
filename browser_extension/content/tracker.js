/**
 * LTI Learning Tracker - Content Script
 * Extracts page metadata and monitors user engagement
 */

// ===== Page Metadata Extraction =====
function extractPageMetadata() {
    const metadata = {
        title: document.title,
        url: window.location.href,
        keywords: [],
        description: '',
        type: 'webpage',
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

    return metadata;
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
// Send metadata when page loads
if (document.readyState === 'complete') {
    sendMetadata();
} else {
    window.addEventListener('load', sendMetadata);
}

function sendMetadata() {
    try {
        const metadata = extractPageMetadata();
        chrome.runtime.sendMessage({ action: 'pageData', data: metadata }).catch(() => {
            // Extension context may be invalidated, ignore
        });
    } catch (e) {
        // Ignore errors when extension context is invalid
    }
}
