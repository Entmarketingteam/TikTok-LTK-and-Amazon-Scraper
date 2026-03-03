// State
let currentVideos = [];
let currentProfiles = [];

// Elements
const tabs = document.querySelectorAll('.tab');
const tabContents = document.querySelectorAll('.tab-content');
const statusBar = document.getElementById('status-bar');
const statusText = document.getElementById('status-text');
const resultsSection = document.getElementById('results-section');
const resultsTitle = document.getElementById('results-title');
const videoGrid = document.getElementById('video-grid');
const profileResult = document.getElementById('profile-result');
const profilesList = document.getElementById('profiles-list');
const profilesGrid = document.getElementById('profiles-grid');
const emailResults = document.getElementById('email-results');
const emailTableBody = document.getElementById('email-table-body');
const scanEmailsBtn = document.getElementById('scan-emails-btn');
const exportCsvBtn = document.getElementById('export-csv');
const modal = document.getElementById('video-modal');
const modalBody = document.getElementById('modal-body');

// Tab switching
tabs.forEach(tab => {
    tab.addEventListener('click', () => {
        tabs.forEach(t => t.classList.remove('active'));
        tabContents.forEach(tc => tc.classList.remove('active'));
        tab.classList.add('active');
        document.getElementById(tab.dataset.tab).classList.add('active');
    });
});

// Video search
document.getElementById('video-search-form').addEventListener('submit', async (e) => {
    e.preventDefault();
    const keyword = document.getElementById('keyword').value.trim();
    const dateRange = parseInt(document.getElementById('date-range').value);
    const maxVideos = parseInt(document.getElementById('max-videos').value);

    if (!keyword) return;

    showStatus(`Searching TikTok for "${keyword}"... This may take 1-2 minutes.`);
    hideResults();

    try {
        const resp = await fetch('/api/search', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ keyword, date_range: dateRange, max_videos: maxVideos }),
        });

        if (!resp.ok) {
            const err = await resp.json();
            throw new Error(err.detail || 'Search failed');
        }

        const data = await resp.json();
        currentVideos = data.videos;
        currentProfiles = data.profiles;

        renderVideoResults(data.videos, keyword);
        renderProfilesList(data.profiles);
    } catch (err) {
        alert('Error: ' + err.message);
    } finally {
        hideStatus();
    }
});

// Profile search
document.getElementById('profile-search-form').addEventListener('submit', async (e) => {
    e.preventDefault();
    const username = document.getElementById('username').value.trim().replace('@', '');
    const deepSearch = document.getElementById('deep-search').checked;

    if (!username) return;

    showStatus(`Scraping @${username}'s profile... This may take 1-2 minutes.`);
    hideResults();

    try {
        const resp = await fetch('/api/profile', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ username, deep_search: deepSearch }),
        });

        if (!resp.ok) {
            const err = await resp.json();
            throw new Error(err.detail || 'Profile scrape failed');
        }

        const data = await resp.json();
        renderProfileResult(data);
    } catch (err) {
        alert('Error: ' + err.message);
    } finally {
        hideStatus();
    }
});

// Scan all profiles for emails
scanEmailsBtn.addEventListener('click', async () => {
    if (currentProfiles.length === 0) return;

    const usernames = currentProfiles.map(p => p.username);
    showStatus(`Scanning ${usernames.length} profiles for emails... This may take several minutes.`);
    scanEmailsBtn.disabled = true;

    try {
        const resp = await fetch('/api/scan-emails', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ usernames, deep_search: true }),
        });

        if (!resp.ok) {
            const err = await resp.json();
            throw new Error(err.detail || 'Email scan failed');
        }

        const data = await resp.json();
        renderEmailResults(data.profiles);
    } catch (err) {
        alert('Error: ' + err.message);
    } finally {
        hideStatus();
        scanEmailsBtn.disabled = false;
    }
});

// Export CSV
exportCsvBtn.addEventListener('click', async () => {
    try {
        let endpoint = '/api/export/videos';
        let filename = 'tiktok_videos.csv';

        // If email results are visible, export those instead
        if (!emailResults.classList.contains('hidden')) {
            endpoint = '/api/export/emails';
            filename = 'tiktok_emails.csv';
        }

        const resp = await fetch(endpoint);
        if (!resp.ok) throw new Error('Export failed');

        const blob = await resp.blob();
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = filename;
        a.click();
        URL.revokeObjectURL(url);
    } catch (err) {
        alert('Export error: ' + err.message);
    }
});

// Render video results
function renderVideoResults(videos, keyword) {
    resultsSection.classList.remove('hidden');
    videoGrid.classList.remove('hidden');
    resultsTitle.textContent = `${videos.length} videos for "${keyword}"`;
    scanEmailsBtn.classList.remove('hidden');

    videoGrid.innerHTML = videos.map((v, i) => `
        <div class="video-card" onclick="openVideoModal(${i})">
            <div class="cover">
                ${v.cover_url
                    ? `<img src="${v.cover_url}" alt="cover" loading="lazy">`
                    : '<span class="no-cover">&#9654;</span>'
                }
            </div>
            <div class="info">
                <div class="author">
                    ${v.author_avatar
                        ? `<img src="${v.author_avatar}" alt="${v.author_username}">`
                        : ''
                    }
                    <div>
                        <div class="author-name">${escapeHtml(v.author_name)}</div>
                        <div class="author-handle">@${escapeHtml(v.author_username)}</div>
                    </div>
                </div>
                <div class="description">${escapeHtml(v.text)}</div>
                <div class="stats">
                    <span>&#9654; ${formatNumber(v.play_count)}</span>
                    <span>&#10084; ${formatNumber(v.like_count)}</span>
                    <span>&#128172; ${formatNumber(v.comment_count)}</span>
                    <span>&#8618; ${formatNumber(v.share_count)}</span>
                </div>
            </div>
        </div>
    `).join('');
}

// Render unique profiles sidebar
function renderProfilesList(profiles) {
    if (profiles.length === 0) return;
    profilesList.classList.remove('hidden');

    profilesGrid.innerHTML = profiles.map(p => `
        <div class="profile-mini-card">
            ${p.avatar_url
                ? `<img src="${p.avatar_url}" alt="${p.username}">`
                : '<img src="" alt="">'
            }
            <div class="mini-info">
                <a href="${p.profile_url}" target="_blank">@${escapeHtml(p.username)}</a>
                <div class="mini-name">${escapeHtml(p.display_name)}</div>
            </div>
        </div>
    `).join('');
}

// Render single profile result
function renderProfileResult(profile) {
    resultsSection.classList.remove('hidden');
    profileResult.classList.remove('hidden');
    resultsTitle.textContent = `Profile: @${profile.username}`;

    const allEmails = [...(profile.emails || []), ...(profile.linktree_emails || [])];

    profileResult.innerHTML = `
        <div class="profile-card">
            ${profile.avatar_url
                ? `<img class="avatar" src="${profile.avatar_url}" alt="${profile.username}">`
                : ''
            }
            <div class="profile-info">
                <div class="display-name">${escapeHtml(profile.display_name || profile.username)}</div>
                <a class="username-link" href="${profile.profile_url}" target="_blank">@${escapeHtml(profile.username)}</a>
                <div class="bio">${escapeHtml(profile.bio)}</div>
                <div class="profile-stats">
                    <div class="stat">
                        <div class="stat-value">${formatNumber(profile.follower_count)}</div>
                        <div class="stat-label">Followers</div>
                    </div>
                    <div class="stat">
                        <div class="stat-value">${formatNumber(profile.following_count)}</div>
                        <div class="stat-label">Following</div>
                    </div>
                    <div class="stat">
                        <div class="stat-value">${formatNumber(profile.like_count)}</div>
                        <div class="stat-label">Likes</div>
                    </div>
                    <div class="stat">
                        <div class="stat-value">${formatNumber(profile.video_count)}</div>
                        <div class="stat-label">Videos</div>
                    </div>
                </div>
                ${profile.bio_link ? `<div style="margin-bottom:0.75rem"><a href="${escapeHtml(profile.bio_link)}" target="_blank" style="color:#25f4ee">${escapeHtml(profile.bio_link)}</a></div>` : ''}
                ${allEmails.length > 0 ? `
                    <div class="email-badges">
                        ${(profile.emails || []).map(e => `<span class="email-badge">${escapeHtml(e)} <span class="email-source">(bio)</span></span>`).join('')}
                        ${(profile.linktree_emails || []).map(e => `<span class="email-badge linktree">${escapeHtml(e)} <span class="email-source">(linktree)</span></span>`).join('')}
                    </div>
                ` : '<div style="color:#888;margin-top:0.5rem">No emails found</div>'}
            </div>
        </div>
    `;
}

// Render email scan results table
function renderEmailResults(profiles) {
    emailResults.classList.remove('hidden');

    const withEmails = profiles.filter(p =>
        (p.emails && p.emails.length > 0) || (p.linktree_emails && p.linktree_emails.length > 0)
    );

    if (withEmails.length === 0) {
        emailTableBody.innerHTML = '<tr><td colspan="4" style="text-align:center;color:#888">No emails found across scanned profiles</td></tr>';
        return;
    }

    emailTableBody.innerHTML = withEmails.map(p => `
        <tr>
            <td>@${escapeHtml(p.username)}</td>
            <td>${(p.emails || []).join(', ') || '-'}</td>
            <td>${(p.linktree_emails || []).join(', ') || '-'}</td>
            <td><a href="${p.profile_url}" target="_blank">View</a></td>
        </tr>
    `).join('');
}

// Video modal
function openVideoModal(index) {
    const v = currentVideos[index];
    if (!v) return;

    modalBody.innerHTML = `
        <div class="modal-video-info">
            <div class="author" style="display:flex;align-items:center;gap:0.75rem;margin-bottom:1rem">
                ${v.author_avatar ? `<img src="${v.author_avatar}" style="width:48px;height:48px;border-radius:50%">` : ''}
                <div>
                    <div style="font-weight:700">${escapeHtml(v.author_name)}</div>
                    <div style="color:#888">@${escapeHtml(v.author_username)}</div>
                </div>
            </div>
            <div class="modal-description">${escapeHtml(v.text)}</div>
            <div class="modal-stats">
                <div class="stat"><div class="stat-value">${formatNumber(v.play_count)}</div><div class="stat-label">Views</div></div>
                <div class="stat"><div class="stat-value">${formatNumber(v.like_count)}</div><div class="stat-label">Likes</div></div>
                <div class="stat"><div class="stat-value">${formatNumber(v.comment_count)}</div><div class="stat-label">Comments</div></div>
                <div class="stat"><div class="stat-value">${formatNumber(v.share_count)}</div><div class="stat-label">Shares</div></div>
            </div>
            ${v.music_title ? `<div style="color:#888;margin-bottom:1rem">&#9835; ${escapeHtml(v.music_title)}</div>` : ''}
            ${v.created_at ? `<div style="color:#666;margin-bottom:1rem;font-size:0.85rem">${new Date(v.created_at).toLocaleDateString()}</div>` : ''}
            <a class="modal-link" href="${v.url}" target="_blank">Watch on TikTok</a>
        </div>
    `;

    modal.classList.remove('hidden');
}

// Close modal
document.querySelector('.modal-close').addEventListener('click', () => modal.classList.add('hidden'));
document.querySelector('.modal-overlay').addEventListener('click', () => modal.classList.add('hidden'));
document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') modal.classList.add('hidden');
});

// Helpers
function showStatus(text) {
    statusBar.classList.remove('hidden');
    statusText.textContent = text;
}

function hideStatus() {
    statusBar.classList.add('hidden');
}

function hideResults() {
    videoGrid.classList.add('hidden');
    profileResult.classList.add('hidden');
    profilesList.classList.add('hidden');
    emailResults.classList.add('hidden');
    scanEmailsBtn.classList.add('hidden');
    videoGrid.innerHTML = '';
    profileResult.innerHTML = '';
    profilesGrid.innerHTML = '';
    emailTableBody.innerHTML = '';
}

function formatNumber(n) {
    if (!n) return '0';
    if (n >= 1_000_000) return (n / 1_000_000).toFixed(1) + 'M';
    if (n >= 1_000) return (n / 1_000).toFixed(1) + 'K';
    return n.toString();
}

function escapeHtml(str) {
    if (!str) return '';
    const div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
}
