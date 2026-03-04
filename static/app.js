// ── State ───────────────────────────────────────────────────────
let currentVideos = [];
let currentProfiles = [];
let currentPipelineLeads = [];
let currentPipelineKeyword = '';
let activeTierFilter = 'all';

// ── Elements ────────────────────────────────────────────────────
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
const pipelineDashboard = document.getElementById('pipeline-dashboard');
const statsGrid = document.getElementById('stats-grid');
const nicheAnalysis = document.getElementById('niche-analysis');
const pipelineLeads = document.getElementById('pipeline-leads');
const leadsTableBody = document.getElementById('leads-table-body');
const reviewQueueSection = document.getElementById('review-queue-section');
const reviewTableBody = document.getElementById('review-table-body');

// ── Tab Switching ───────────────────────────────────────────────
tabs.forEach(tab => {
    tab.addEventListener('click', () => {
        tabs.forEach(t => t.classList.remove('active'));
        tabContents.forEach(tc => tc.classList.remove('active'));
        tab.classList.add('active');
        document.getElementById(tab.dataset.tab).classList.add('active');

        // Auto-load review queue when switching to that tab
        if (tab.dataset.tab === 'review-tab') {
            loadReviewQueue();
        }
    });
});

// ── Video Search ────────────────────────────────────────────────
document.getElementById('video-search-form').addEventListener('submit', async (e) => {
    e.preventDefault();
    const keyword = document.getElementById('keyword').value.trim();
    const dateRange = parseInt(document.getElementById('date-range').value);
    const maxVideos = parseInt(document.getElementById('max-videos').value);

    if (!keyword) return;

    showStatus(`Searching TikTok for "${keyword}"... This may take 1-2 minutes.`);
    hideAllResults();

    try {
        const resp = await fetch('/api/search', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ keyword, date_range: dateRange, max_videos: maxVideos }),
        });
        if (!resp.ok) throw new Error((await resp.json()).detail || 'Search failed');

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

// ── Profile Search ──────────────────────────────────────────────
document.getElementById('profile-search-form').addEventListener('submit', async (e) => {
    e.preventDefault();
    const username = document.getElementById('username').value.trim().replace('@', '');
    const deepSearch = document.getElementById('deep-search').checked;

    if (!username) return;

    showStatus(`Scraping @${username}'s profile...`);
    hideAllResults();

    try {
        const resp = await fetch('/api/profile', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ username, deep_search: deepSearch }),
        });
        if (!resp.ok) throw new Error((await resp.json()).detail || 'Profile scrape failed');

        const data = await resp.json();
        renderProfileResult(data);
    } catch (err) {
        alert('Error: ' + err.message);
    } finally {
        hideStatus();
    }
});

// ── Full Pipeline ───────────────────────────────────────────────
document.getElementById('pipeline-form').addEventListener('submit', async (e) => {
    e.preventDefault();
    const keyword = document.getElementById('pipe-keyword').value.trim();
    const dateRange = parseInt(document.getElementById('pipe-date-range').value);
    const maxVideos = parseInt(document.getElementById('pipe-max-videos').value);
    const bioKeywordsRaw = document.getElementById('pipe-bio-keywords').value.trim();
    const phantomId = document.getElementById('pipe-phantom-id').value.trim();
    const autoPush = document.getElementById('pipe-auto-push').checked;

    if (!keyword) return;

    const customBioKeywords = bioKeywordsRaw
        ? bioKeywordsRaw.split(',').map(k => k.trim()).filter(Boolean)
        : [];

    showStatus(`Running full pipeline for "${keyword}"... This may take several minutes.`);
    hideAllResults();

    try {
        const resp = await fetch('/api/pipeline/run', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                keyword,
                date_range: dateRange,
                max_videos: maxVideos,
                custom_bio_keywords: customBioKeywords,
                instagram_phantom_id: phantomId,
                auto_push_to_smartlead: autoPush,
            }),
        });
        if (!resp.ok) throw new Error((await resp.json()).detail || 'Pipeline failed');

        const data = await resp.json();
        currentPipelineLeads = data.leads;
        currentPipelineKeyword = data.keyword;

        renderPipelineDashboard(data);
        renderPipelineLeads(data.leads);
    } catch (err) {
        alert('Error: ' + err.message);
    } finally {
        hideStatus();
    }
});

// ── Scan Emails Button ──────────────────────────────────────────
scanEmailsBtn.addEventListener('click', async () => {
    if (currentProfiles.length === 0) return;

    const usernames = currentProfiles.map(p => p.username);
    showStatus(`Scanning ${usernames.length} profiles for emails...`);
    scanEmailsBtn.disabled = true;

    try {
        const resp = await fetch('/api/scan-emails', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ usernames, deep_search: true }),
        });
        if (!resp.ok) throw new Error((await resp.json()).detail || 'Scan failed');

        const data = await resp.json();
        renderEmailResults(data.profiles);
    } catch (err) {
        alert('Error: ' + err.message);
    } finally {
        hideStatus();
        scanEmailsBtn.disabled = false;
    }
});

// ── Export Buttons ───────────────────────────────────────────────
exportCsvBtn.addEventListener('click', () => downloadFile('/api/export/videos', 'tiktok_videos.csv'));

document.getElementById('export-pipeline-csv')?.addEventListener('click', () => {
    downloadFile('/api/export/pipeline', 'tiktok_pipeline_results.csv');
});

async function downloadFile(endpoint, filename) {
    try {
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
}

// ── Review Queue ────────────────────────────────────────────────
document.getElementById('refresh-queue')?.addEventListener('click', loadReviewQueue);

async function loadReviewQueue() {
    try {
        const resp = await fetch('/api/review-queue?status=pending');
        if (!resp.ok) throw new Error('Failed to load queue');
        const data = await resp.json();

        document.getElementById('queue-stats').textContent =
            `${data.stats.pending} pending | ${data.stats.approved} approved | ${data.stats.rejected} rejected`;

        renderReviewQueue(data.items);
    } catch (err) {
        console.error('Review queue error:', err);
    }
}

async function reviewAction(itemId, action) {
    try {
        const resp = await fetch(`/api/review-queue/${itemId}`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ action, niche: currentPipelineKeyword }),
        });
        if (!resp.ok) throw new Error((await resp.json()).detail || 'Action failed');
        loadReviewQueue();
    } catch (err) {
        alert('Error: ' + err.message);
    }
}

// ── Tier Filters ────────────────────────────────────────────────
document.querySelectorAll('.tier-btn').forEach(btn => {
    btn.addEventListener('click', () => {
        document.querySelectorAll('.tier-btn').forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
        activeTierFilter = btn.dataset.tier;
        renderPipelineLeads(currentPipelineLeads);
    });
});

// ══════════════════════════════════════════════════════════════════
// RENDER FUNCTIONS
// ══════════════════════════════════════════════════════════════════

function renderPipelineDashboard(data) {
    pipelineDashboard.classList.remove('hidden');

    const s = data.stats;
    statsGrid.innerHTML = `
        <div class="stat-card"><div class="stat-value">${s.videos_found}</div><div class="stat-label">Videos Found</div></div>
        <div class="stat-card"><div class="stat-value">${s.creators_found}</div><div class="stat-label">Creators</div></div>
        <div class="stat-card emails"><div class="stat-value">${s.emails_found}</div><div class="stat-label">Emails Found</div></div>
        <div class="stat-card auto-send"><div class="stat-value">${s.auto_send}</div><div class="stat-label">Auto-Send</div></div>
        <div class="stat-card review"><div class="stat-value">${s.review}</div><div class="stat-label">Review</div></div>
        <div class="stat-card discard"><div class="stat-value">${s.discard}</div><div class="stat-label">Discarded</div></div>
        <div class="stat-card pushed"><div class="stat-value">${s.pushed_to_smartlead}</div><div class="stat-label">Pushed to SmartLead</div></div>
    `;

    const na = data.niche_analysis;
    if (na && na.keyword) {
        nicheAnalysis.innerHTML = `
            <h3>Niche Analysis: "${escapeHtml(na.keyword)}"</h3>
            <div style="display:flex;gap:2rem;margin-bottom:0.75rem;flex-wrap:wrap">
                <span>Volume: <strong>${na.volume || 'N/A'}</strong></span>
                <span>CPC: <strong>$${(na.cpc || 0).toFixed(2)}</strong></span>
                <span>Competition: <strong>${((na.competition || 0) * 100).toFixed(0)}%</strong></span>
                <span>Viable: <strong style="color:${na.viable ? '#4ade80' : '#f87171'}">${na.viable ? 'Yes' : 'No'}</strong></span>
            </div>
            ${na.related_keywords && na.related_keywords.length > 0 ? `
                <div class="niche-tags">
                    ${na.related_keywords.map(k => `<span class="niche-tag">${escapeHtml(k)}</span>`).join('')}
                </div>
            ` : ''}
        `;
        nicheAnalysis.style.display = 'block';
    } else {
        nicheAnalysis.style.display = 'none';
    }
}

function renderPipelineLeads(leads) {
    pipelineLeads.classList.remove('hidden');

    const filtered = activeTierFilter === 'all'
        ? leads
        : leads.filter(l => l.tier === activeTierFilter);

    leadsTableBody.innerHTML = filtered.map(l => {
        const score = l.score ? l.score.total : 0;
        const scoreClass = score >= 75 ? 'high' : score >= 40 ? 'medium' : 'low';

        return `
        <tr>
            <td>
                <div style="display:flex;align-items:center;gap:0.5rem">
                    ${l.avatar_url ? `<img src="${l.avatar_url}" style="width:28px;height:28px;border-radius:50%">` : ''}
                    <div>
                        <div style="font-weight:600">${escapeHtml(l.display_name || l.username)}</div>
                        <a href="${l.profile_url}" target="_blank" style="font-size:0.8rem">@${escapeHtml(l.username)}</a>
                    </div>
                </div>
            </td>
            <td>${l.outreach_email ? `<span style="color:#25f4ee">${escapeHtml(l.outreach_email)}</span>` : '<span style="color:#666">none</span>'}</td>
            <td>
                <div class="score-bar"><div class="score-bar-fill ${scoreClass}" style="width:${score}%"></div></div>
                <span style="font-weight:600">${score.toFixed(1)}</span>
            </td>
            <td><span class="tier-badge ${l.tier}">${l.tier.replace('_', ' ')}</span></td>
            <td>${l.score ? l.score.engagement.toFixed(0) : '-'}</td>
            <td>${formatNumber(l.follower_count)}</td>
            <td style="font-size:0.8rem;color:#888;max-width:200px">${l.score ? escapeHtml(l.score.reasoning) : ''}</td>
            <td>${l.pushed_to_smartlead
                ? '<span style="color:#4ade80;font-size:0.8rem">Sent</span>'
                : l.tier === 'review'
                    ? '<span style="color:#fbbf24;font-size:0.8rem">In Review</span>'
                    : '<span style="color:#666;font-size:0.8rem">-</span>'
            }</td>
        </tr>`;
    }).join('');
}

function renderReviewQueue(items) {
    reviewQueueSection.classList.remove('hidden');

    if (items.length === 0) {
        reviewTableBody.innerHTML = '<tr><td colspan="5" style="text-align:center;color:#888">No leads in review queue</td></tr>';
        return;
    }

    reviewTableBody.innerHTML = items.map(item => {
        const l = item.lead;
        const score = l.score ? l.score.total : 0;

        return `
        <tr>
            <td>
                <div>
                    <div style="font-weight:600">${escapeHtml(l.display_name || l.username)}</div>
                    <a href="${l.profile_url}" target="_blank" style="font-size:0.8rem;color:#25f4ee">@${escapeHtml(l.username)}</a>
                </div>
            </td>
            <td>${l.outreach_email ? escapeHtml(l.outreach_email) : '<span style="color:#666">none</span>'}</td>
            <td><strong>${score.toFixed(1)}</strong></td>
            <td style="font-size:0.8rem;color:#888">${l.score ? escapeHtml(l.score.reasoning) : ''}</td>
            <td>
                <div class="review-actions">
                    <button class="btn-approve" onclick="reviewAction(${item.id}, 'approve')">Approve</button>
                    <button class="btn-reject" onclick="reviewAction(${item.id}, 'reject')">Reject</button>
                </div>
            </td>
        </tr>`;
    }).join('');
}

// ── Original Render Functions ────────────────────────────────────

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
                    ${v.author_avatar ? `<img src="${v.author_avatar}" alt="${v.author_username}">` : ''}
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

function renderProfilesList(profiles) {
    if (profiles.length === 0) return;
    profilesList.classList.remove('hidden');
    profilesGrid.innerHTML = profiles.map(p => `
        <div class="profile-mini-card">
            ${p.avatar_url ? `<img src="${p.avatar_url}" alt="${p.username}">` : '<img src="" alt="">'}
            <div class="mini-info">
                <a href="${p.profile_url}" target="_blank">@${escapeHtml(p.username)}</a>
                <div class="mini-name">${escapeHtml(p.display_name)}</div>
            </div>
        </div>
    `).join('');
}

function renderProfileResult(profile) {
    resultsSection.classList.remove('hidden');
    profileResult.classList.remove('hidden');
    resultsTitle.textContent = `Profile: @${profile.username}`;

    profileResult.innerHTML = `
        <div class="profile-card">
            ${profile.avatar_url ? `<img class="avatar" src="${profile.avatar_url}" alt="${profile.username}">` : ''}
            <div class="profile-info">
                <div class="display-name">${escapeHtml(profile.display_name || profile.username)}</div>
                <a class="username-link" href="${profile.profile_url}" target="_blank">@${escapeHtml(profile.username)}</a>
                <div class="bio">${escapeHtml(profile.bio)}</div>
                <div class="profile-stats">
                    <div class="stat"><div class="stat-value">${formatNumber(profile.follower_count)}</div><div class="stat-label">Followers</div></div>
                    <div class="stat"><div class="stat-value">${formatNumber(profile.following_count)}</div><div class="stat-label">Following</div></div>
                    <div class="stat"><div class="stat-value">${formatNumber(profile.like_count)}</div><div class="stat-label">Likes</div></div>
                    <div class="stat"><div class="stat-value">${formatNumber(profile.video_count)}</div><div class="stat-label">Videos</div></div>
                </div>
                ${profile.bio_link ? `<div style="margin-bottom:0.75rem"><a href="${escapeHtml(profile.bio_link)}" target="_blank" style="color:#25f4ee">${escapeHtml(profile.bio_link)}</a></div>` : ''}
                <div class="email-badges">
                    ${(profile.emails || []).map(e => `<span class="email-badge">${escapeHtml(e)} <span class="email-source">(bio)</span></span>`).join('')}
                    ${(profile.linktree_emails || []).map(e => `<span class="email-badge linktree">${escapeHtml(e)} <span class="email-source">(linktree)</span></span>`).join('')}
                </div>
                ${(profile.emails || []).length === 0 && (profile.linktree_emails || []).length === 0 ? '<div style="color:#888;margin-top:0.5rem">No emails found</div>' : ''}
            </div>
        </div>
    `;
}

function renderEmailResults(profiles) {
    emailResults.classList.remove('hidden');
    const withEmails = profiles.filter(p =>
        (p.emails && p.emails.length > 0) || (p.linktree_emails && p.linktree_emails.length > 0)
    );

    if (withEmails.length === 0) {
        emailTableBody.innerHTML = '<tr><td colspan="4" style="text-align:center;color:#888">No emails found</td></tr>';
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

// ── Video Modal ─────────────────────────────────────────────────
function openVideoModal(index) {
    const v = currentVideos[index];
    if (!v) return;

    modalBody.innerHTML = `
        <div class="modal-video-info">
            <div style="display:flex;align-items:center;gap:0.75rem;margin-bottom:1rem">
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

document.querySelector('.modal-close').addEventListener('click', () => modal.classList.add('hidden'));
document.querySelector('.modal-overlay').addEventListener('click', () => modal.classList.add('hidden'));
document.addEventListener('keydown', (e) => { if (e.key === 'Escape') modal.classList.add('hidden'); });

// ── Helpers ─────────────────────────────────────────────────────
function showStatus(text) {
    statusBar.classList.remove('hidden');
    statusText.textContent = text;
}

function hideStatus() {
    statusBar.classList.add('hidden');
}

function hideAllResults() {
    resultsSection.classList.add('hidden');
    videoGrid.classList.add('hidden');
    profileResult.classList.add('hidden');
    profilesList.classList.add('hidden');
    emailResults.classList.add('hidden');
    scanEmailsBtn.classList.add('hidden');
    pipelineDashboard.classList.add('hidden');
    pipelineLeads.classList.add('hidden');
    reviewQueueSection.classList.add('hidden');
    videoGrid.innerHTML = '';
    profileResult.innerHTML = '';
    profilesGrid.innerHTML = '';
    emailTableBody.innerHTML = '';
    leadsTableBody.innerHTML = '';
    reviewTableBody.innerHTML = '';
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

// Make functions global for inline onclick handlers
window.reviewAction = reviewAction;
window.openVideoModal = openVideoModal;
