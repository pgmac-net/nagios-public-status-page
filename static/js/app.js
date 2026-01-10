// API base URL - can be configured
const API_BASE = '/api';
const AUTO_REFRESH_INTERVAL = 60000; // 60 seconds

// State
let currentIncidentFilter = 'active';
let autoRefreshTimer = null;

// Initialize on page load
document.addEventListener('DOMContentLoaded', () => {
    loadAllData();
    startAutoRefresh();
});

// Load all data
async function loadAllData() {
    await Promise.all([
        loadStatusSummary(),
        loadIncidents(),
        loadHosts(),
        loadServices(),
        checkStaleness()
    ]);
}

// Refresh data manually
function refreshData() {
    loadAllData();
}

// Trigger manual poll
async function triggerManualPoll() {
    const button = document.querySelector('.btn-poll');
    if (!button) return;

    // Disable button and show loading state
    button.disabled = true;
    button.textContent = 'Polling...';

    try {
        const response = await fetch(`${API_BASE}/poll`, {
            method: 'POST'
        });

        if (!response.ok) {
            throw new Error('Poll failed');
        }

        const data = await response.json();

        // Show success message briefly
        button.textContent = 'Poll Complete!';

        // Reload all data to reflect updates
        await loadAllData();

        // Reset button after 2 seconds
        setTimeout(() => {
            button.disabled = false;
            button.textContent = '🔄 Poll Now';
        }, 2000);

    } catch (error) {
        console.error('Error triggering poll:', error);
        button.textContent = 'Poll Failed';
        setTimeout(() => {
            button.disabled = false;
            button.textContent = '🔄 Poll Now';
        }, 2000);
    }
}

// Start auto-refresh
function startAutoRefresh() {
    if (autoRefreshTimer) {
        clearInterval(autoRefreshTimer);
    }
    autoRefreshTimer = setInterval(loadAllData, AUTO_REFRESH_INTERVAL);
}

// Check for data staleness
async function checkStaleness() {
    try {
        const response = await fetch(`${API_BASE}/health`);
        const data = await response.json();

        const warningEl = document.getElementById('staleness-warning');
        const stalenessTimeEl = document.getElementById('staleness-time');

        if (data.data_is_stale) {
            const ageMinutes = Math.floor(data.status_dat_age_seconds / 60);
            stalenessTimeEl.textContent = `${ageMinutes} minutes`;
            warningEl.style.display = 'block';
        } else {
            warningEl.style.display = 'none';
        }

        // Update last update time
        if (data.last_poll_time) {
            const lastUpdate = parseUTCDate(data.last_poll_time);
            document.getElementById('last-update').textContent =
                `Last updated: ${formatDateTime(lastUpdate)}`;
        }
    } catch (error) {
        console.error('Error checking staleness:', error);
    }
}

// Load status summary
async function loadStatusSummary() {
    try {
        const response = await fetch(`${API_BASE}/status`);
        const data = await response.json();

        // Update hosts
        document.getElementById('hosts-up').textContent = data.hosts_up;
        document.getElementById('hosts-down').textContent = data.hosts_down;
        document.getElementById('hosts-unreachable').textContent = data.hosts_unreachable;

        // Update services
        document.getElementById('services-ok').textContent = data.services_ok;
        document.getElementById('services-warning').textContent = data.services_warning;
        document.getElementById('services-critical').textContent = data.services_critical;
        document.getElementById('services-unknown').textContent = data.services_unknown;

        // Update active incidents
        document.getElementById('active-incidents').textContent = data.active_incidents;
    } catch (error) {
        console.error('Error loading status summary:', error);
    }
}

// Load incidents with safe DOM methods
async function loadIncidents() {
    const listEl = document.getElementById('incidents-list');
    listEl.textContent = 'Loading incidents...';
    listEl.className = 'incidents-list loading';

    try {
        let url = `${API_BASE}/incidents?`;
        if (currentIncidentFilter === 'active') {
            url += 'active_only=true';
        } else if (currentIncidentFilter === 'recent') {
            url += 'hours=24';
        } else {
            url += 'hours=168'; // 7 days
        }

        const response = await fetch(url);
        const incidents = await response.json();

        listEl.className = 'incidents-list';
        listEl.textContent = '';

        if (incidents.length === 0) {
            const p = document.createElement('p');
            p.style.textAlign = 'center';
            p.style.color = '#a0aec0';
            p.textContent = 'No incidents found';
            listEl.appendChild(p);
            return;
        }

        incidents.forEach(incident => {
            const item = createIncidentElement(incident);
            listEl.appendChild(item);
        });
    } catch (error) {
        console.error('Error loading incidents:', error);
        listEl.className = 'incidents-list';
        const p = document.createElement('p');
        p.style.color = '#f56565';
        p.textContent = 'Error loading incidents';
        listEl.appendChild(p);
    }
}

// Create incident element safely
function createIncidentElement(incident) {
    const div = document.createElement('div');
    div.className = `incident-item ${incident.is_active ? 'active' : 'resolved'}`;
    div.onclick = () => showIncidentDetail(incident.id);

    const header = document.createElement('div');
    header.className = 'incident-header';

    const title = document.createElement('div');
    title.className = 'incident-title';
    title.textContent = incident.host_name + (incident.service_description ? ' / ' + incident.service_description : '');
    header.appendChild(title);

    const state = document.createElement('span');
    state.className = `incident-state state-${incident.state.toLowerCase()}`;
    state.textContent = incident.state;
    header.appendChild(state);

    // Show acknowledgement badge if incident is acknowledged
    if (incident.acknowledged) {
        const ackBadge = document.createElement('span');
        ackBadge.className = 'ack-badge';
        ackBadge.textContent = '✓ Acknowledged';
        ackBadge.title = 'This incident has been acknowledged';
        header.appendChild(ackBadge);
    }

    div.appendChild(header);

    const info = document.createElement('div');
    info.className = 'incident-info';
    info.textContent = `${incident.incident_type.toUpperCase()} incident`;
    div.appendChild(info);

    if (incident.plugin_output) {
        const output = document.createElement('div');
        output.className = 'plugin-output';
        output.textContent = incident.plugin_output;
        div.appendChild(output);
    }

    const times = document.createElement('div');
    times.className = 'incident-times';
    const startText = 'Started: ' + formatDateTime(parseUTCDate(incident.started_at));
    const endText = incident.ended_at
        ? ' | Ended: ' + formatDateTime(parseUTCDate(incident.ended_at))
        : ' | Still Active';
    times.textContent = startText + endText;
    div.appendChild(times);

    return div;
}

// Load hosts
async function loadHosts() {
    const listEl = document.getElementById('hosts-list');
    listEl.textContent = 'Loading hosts...';
    listEl.className = 'hosts-list loading';

    try {
        const response = await fetch(`${API_BASE}/hosts`);
        const hosts = await response.json();

        listEl.className = 'hosts-list';
        listEl.textContent = '';

        if (hosts.length === 0) {
            const p = document.createElement('p');
            p.style.textAlign = 'center';
            p.style.color = '#a0aec0';
            p.textContent = 'No hosts found';
            listEl.appendChild(p);
            return;
        }

        hosts.forEach(host => {
            const item = createHostElement(host);
            listEl.appendChild(item);
        });
    } catch (error) {
        console.error('Error loading hosts:', error);
        listEl.className = 'hosts-list';
        const p = document.createElement('p');
        p.style.color = '#f56565';
        p.textContent = 'Error loading hosts';
        listEl.appendChild(p);
    }
}

// Create host element safely
function createHostElement(host) {
    const div = document.createElement('div');
    div.className = 'host-item';

    const header = document.createElement('div');
    header.className = 'host-header';

    const name = document.createElement('div');
    name.className = 'host-name';
    name.textContent = host.host_name;
    header.appendChild(name);

    const state = document.createElement('span');
    state.className = `host-state state-${host.state_name.toLowerCase()}`;
    state.textContent = host.state_name;
    header.appendChild(state);

    div.appendChild(header);

    if (host.plugin_output) {
        const output = document.createElement('div');
        output.className = 'plugin-output';
        output.textContent = host.plugin_output;
        div.appendChild(output);
    }

    if (host.last_check) {
        const check = document.createElement('div');
        check.style.fontSize = '0.85rem';
        check.style.color = '#a0aec0';
        check.style.marginTop = '8px';
        check.textContent = `Last check: ${formatDateTime(parseUTCDate(host.last_check))}`;
        div.appendChild(check);
    }

    return div;
}

// Load services
async function loadServices() {
    const listEl = document.getElementById('services-list');
    listEl.textContent = 'Loading services...';
    listEl.className = 'services-list loading';

    try {
        const response = await fetch(`${API_BASE}/services`);
        const services = await response.json();

        listEl.className = 'services-list';
        listEl.textContent = '';

        if (services.length === 0) {
            const p = document.createElement('p');
            p.style.textAlign = 'center';
            p.style.color = '#a0aec0';
            p.textContent = 'No services found';
            listEl.appendChild(p);
            return;
        }

        services.forEach(service => {
            const item = createServiceElement(service);
            listEl.appendChild(item);
        });
    } catch (error) {
        console.error('Error loading services:', error);
        listEl.className = 'services-list';
        const p = document.createElement('p');
        p.style.color = '#f56565';
        p.textContent = 'Error loading services';
        listEl.appendChild(p);
    }
}

// Create service element safely
function createServiceElement(service) {
    const div = document.createElement('div');
    div.className = 'service-item';

    const header = document.createElement('div');
    header.className = 'service-header';

    const name = document.createElement('div');
    name.className = 'service-name';
    name.textContent = `${service.host_name} / ${service.service_description}`;
    header.appendChild(name);

    const state = document.createElement('span');
    state.className = `service-state state-${service.state_name.toLowerCase()}`;
    state.textContent = service.state_name;
    header.appendChild(state);

    div.appendChild(header);

    if (service.plugin_output) {
        const output = document.createElement('div');
        output.className = 'plugin-output';
        output.textContent = service.plugin_output;
        div.appendChild(output);
    }

    if (service.last_check) {
        const check = document.createElement('div');
        check.style.fontSize = '0.85rem';
        check.style.color = '#a0aec0';
        check.style.marginTop = '8px';
        check.textContent = `Last check: ${formatDateTime(parseUTCDate(service.last_check))}`;
        div.appendChild(check);
    }

    return div;
}

// Filter incidents
function filterIncidents() {
    const selected = document.querySelector('input[name="incident-filter"]:checked').value;
    currentIncidentFilter = selected;
    loadIncidents();
}

// Show incident detail modal
async function showIncidentDetail(incidentId) {
    const modal = document.getElementById('incident-modal');
    const detailEl = document.getElementById('incident-detail');

    modal.style.display = 'flex';
    detailEl.textContent = 'Loading incident details...';
    detailEl.className = 'loading';

    // Set incident ID for comment form
    document.getElementById('comment-incident-id').value = incidentId;

    try {
        const response = await fetch(`${API_BASE}/incidents/${incidentId}`);
        const data = await response.json();
        const incident = data.incident;

        detailEl.className = '';
        detailEl.textContent = '';

        // Create incident detail elements
        const section1 = document.createElement('div');
        section1.className = 'incident-detail-section';

        const h3 = document.createElement('h3');
        h3.textContent = incident.host_name + (incident.service_description ? ' / ' + incident.service_description : '');
        section1.appendChild(h3);

        const stateSpan = document.createElement('span');
        stateSpan.className = `incident-state state-${incident.state.toLowerCase()}`;
        stateSpan.textContent = incident.state;
        section1.appendChild(stateSpan);

        // Show acknowledgement badge if incident is acknowledged
        if (incident.acknowledged) {
            const ackBadge = document.createElement('span');
            ackBadge.className = 'ack-badge';
            ackBadge.textContent = '✓ Acknowledged';
            ackBadge.title = 'This incident has been acknowledged';
            section1.appendChild(ackBadge);
        }

        detailEl.appendChild(section1);

        // Create info section
        const section2 = document.createElement('div');
        section2.className = 'incident-detail-section';

        const typeP = document.createElement('p');
        const typeBold = document.createElement('strong');
        typeBold.textContent = 'Type: ';
        typeP.appendChild(typeBold);
        typeP.appendChild(document.createTextNode(incident.incident_type.toUpperCase()));
        section2.appendChild(typeP);

        const startedP = document.createElement('p');
        const startedBold = document.createElement('strong');
        startedBold.textContent = 'Started: ';
        startedP.appendChild(startedBold);
        startedP.appendChild(document.createTextNode(formatDateTime(parseUTCDate(incident.started_at))));
        section2.appendChild(startedP);

        if (incident.ended_at) {
            const endedP = document.createElement('p');
            const endedBold = document.createElement('strong');
            endedBold.textContent = 'Ended: ';
            endedP.appendChild(endedBold);
            endedP.appendChild(document.createTextNode(formatDateTime(parseUTCDate(incident.ended_at))));
            section2.appendChild(endedP);
        } else {
            const statusP = document.createElement('p');
            const statusBold = document.createElement('strong');
            statusBold.textContent = 'Status: ';
            statusP.appendChild(statusBold);
            statusP.appendChild(document.createTextNode('Still Active'));
            section2.appendChild(statusP);
        }

        if (incident.last_check) {
            const checkP = document.createElement('p');
            const checkBold = document.createElement('strong');
            checkBold.textContent = 'Last Check: ';
            checkP.appendChild(checkBold);
            checkP.appendChild(document.createTextNode(formatDateTime(parseUTCDate(incident.last_check))));
            section2.appendChild(checkP);
        }

        detailEl.appendChild(section2);

        // Post-Incident Review Link
        if (incident.post_incident_review_url) {
            const pirSection = document.createElement('div');
            pirSection.className = 'incident-detail-section';

            const pirH3 = document.createElement('h3');
            pirH3.textContent = 'Post-Incident Review';
            pirSection.appendChild(pirH3);

            const pirLink = document.createElement('a');
            pirLink.href = incident.post_incident_review_url;
            pirLink.target = '_blank';
            pirLink.rel = 'noopener noreferrer';
            pirLink.className = 'pir-link';
            pirLink.textContent = '\uD83D\uDCC4 View Post-Incident Review Document';
            pirSection.appendChild(pirLink);

            detailEl.appendChild(pirSection);
        }

        // Plugin output
        if (incident.plugin_output) {
            const section3 = document.createElement('div');
            section3.className = 'incident-detail-section';

            const h3Output = document.createElement('h3');
            h3Output.textContent = 'Output';
            section3.appendChild(h3Output);

            const outputDiv = document.createElement('div');
            outputDiv.className = 'plugin-output';
            outputDiv.textContent = incident.plugin_output;
            section3.appendChild(outputDiv);

            detailEl.appendChild(section3);
        }

        // Comments
        if (data.comments.length > 0 || data.nagios_comments.length > 0) {
            const section4 = document.createElement('div');
            section4.className = 'incident-detail-section';

            const h3Comments = document.createElement('h3');
            h3Comments.textContent = 'Comments';
            section4.appendChild(h3Comments);

            const commentsList = document.createElement('div');
            commentsList.className = 'comments-list';

            // Nagios comments
            data.nagios_comments.forEach(comment => {
                const commentDiv = createCommentElement(comment, true);
                commentsList.appendChild(commentDiv);
            });

            // Regular comments
            data.comments.forEach(comment => {
                const commentDiv = createCommentElement(comment, false);
                commentsList.appendChild(commentDiv);
            });

            section4.appendChild(commentsList);
            detailEl.appendChild(section4);
        }

    } catch (error) {
        console.error('Error loading incident detail:', error);
        detailEl.className = '';
        const p = document.createElement('p');
        p.style.color = '#f56565';
        p.textContent = 'Error loading incident details';
        detailEl.appendChild(p);
    }
}

// Create comment element safely
function createCommentElement(comment, isNagios) {
    const div = document.createElement('div');
    div.className = isNagios ? 'comment nagios-comment' : 'comment';

    const header = document.createElement('div');
    header.className = 'comment-header';

    const author = document.createElement('span');
    author.className = 'comment-author';
    author.textContent = comment.author + (isNagios ? ' (Nagios)' : '');
    header.appendChild(author);

    const date = document.createElement('span');
    date.className = 'comment-date';
    // Nagios comments use entry_time, regular comments use created_at
    const commentDate = isNagios ? comment.entry_time : comment.created_at;
    date.textContent = formatDateTime(parseUTCDate(commentDate));
    header.appendChild(date);

    div.appendChild(header);

    const text = document.createElement('div');
    text.className = 'comment-text';
    // Nagios comments use comment_data, regular comments use comment_text
    text.textContent = isNagios ? comment.comment_data : comment.comment_text;
    div.appendChild(text);

    return div;
}

// Close incident modal
function closeIncidentModal() {
    const modal = document.getElementById('incident-modal');
    modal.style.display = 'none';

    // Reset form
    document.getElementById('comment-form').reset();
}

// Submit comment
async function submitComment(event) {
    event.preventDefault();

    const incidentId = document.getElementById('comment-incident-id').value;
    const author = document.getElementById('comment-author').value;
    const commentText = document.getElementById('comment-text').value;

    try {
        const response = await fetch(`${API_BASE}/incidents/${incidentId}/comments`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                author: author,
                comment_text: commentText
            })
        });

        if (!response.ok) {
            throw new Error('Failed to submit comment');
        }

        // Reload incident detail
        await showIncidentDetail(incidentId);

        // Show success message
        alert('Comment submitted successfully!');

        // Reset form
        document.getElementById('comment-form').reset();

    } catch (error) {
        console.error('Error submitting comment:', error);
        alert('Error submitting comment. Please try again.');
    }
}

// Utility: Parse UTC date string
function parseUTCDate(dateString) {
    // Backend returns naive datetime strings without timezone
    // Treat them as UTC by appending 'Z' if not present
    if (dateString && !dateString.endsWith('Z') && dateString.includes('T')) {
        return new Date(dateString + 'Z');
    }
    return new Date(dateString);
}

// Utility: Format date/time in ISO 8601 format with local timezone
function formatDateTime(date) {
    // Get ISO string in local timezone (not UTC)
    const year = date.getFullYear();
    const month = String(date.getMonth() + 1).padStart(2, '0');
    const day = String(date.getDate()).padStart(2, '0');
    const hours = String(date.getHours()).padStart(2, '0');
    const minutes = String(date.getMinutes()).padStart(2, '0');
    const seconds = String(date.getSeconds()).padStart(2, '0');

    // Get timezone offset in format +HH:MM or -HH:MM
    const offset = -date.getTimezoneOffset();
    const offsetHours = String(Math.floor(Math.abs(offset) / 60)).padStart(2, '0');
    const offsetMinutes = String(Math.abs(offset) % 60).padStart(2, '0');
    const offsetSign = offset >= 0 ? '+' : '-';

    return `${year}-${month}-${day}T${hours}:${minutes}:${seconds}${offsetSign}${offsetHours}:${offsetMinutes}`;
}

// Close modal when clicking outside
window.onclick = function(event) {
    const modal = document.getElementById('incident-modal');
    if (event.target === modal) {
        closeIncidentModal();
    }
};

// Close modal when pressing Escape key
document.addEventListener('keydown', function(event) {
    if (event.key === 'Escape' || event.key === 'Esc') {
        const modal = document.getElementById('incident-modal');
        if (modal && modal.style.display === 'flex') {
            closeIncidentModal();
        }
    }
});
