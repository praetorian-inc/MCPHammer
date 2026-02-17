// Application state
let instances = [];
let queuedUpdates = {};
let currentInstanceLogs = null;

// Utility functions
function timeAgo(dateString) {
    const date = new Date(dateString);
    const now = new Date();
    const diffMs = now - date;
    const diffMins = Math.floor(diffMs / 60000);
    const diffHours = Math.floor(diffMins / 60);
    const diffDays = Math.floor(diffHours / 24);

    if (diffMins < 1) return 'Just now';
    if (diffMins < 60) return `${diffMins}m ago`;
    if (diffHours < 24) return `${diffHours}h ago`;
    return `${diffDays}d ago`;
}

function formatDate(dateString) {
    const date = new Date(dateString);
    return date.toLocaleString();
}

function isStale(lastSeen) {
    const date = new Date(lastSeen);
    const now = new Date();
    const diffMins = (now - date) / 60000;
    return diffMins > 10;
}

// API functions
async function loadInstances() {
    try {
        const response = await fetch('/manage/instances');
        const data = await response.json();
        instances = data.instances || [];
        
        renderInstances();
        renderInstanceSelector();
        renderUrlInstanceSelector();
        updateStatusBar();
    } catch (error) {
        document.getElementById('instances-container').innerHTML = 
            `<div class="alert alert-error">Error loading instances: ${error.message}</div>`;
    }
}

async function loadQueuedUpdates() {
    try {
        const response = await fetch('/manage/queued-updates');
        const data = await response.json();
        queuedUpdates = data.updates || {};
        
        renderQueuedUpdates();
        updateStatusBar();
    } catch (error) {
        console.error('Error loading queued updates:', error);
    }
}

// Rendering functions
function renderInstances() {
    const container = document.getElementById('instances-container');
    
    if (instances.length === 0) {
        container.innerHTML = `
            <div class="empty-state">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor">
                    <path d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"/>
                </svg>
                <p>No instances registered yet</p>
                <p style="font-size: 12px; margin-top: 8px;">Start MCPHammer instances with CONFIG_SYNC_URL configured</p>
            </div>
        `;
        return;
    }

    container.innerHTML = instances.map(instance => {
        const stale = isStale(instance.last_seen);
        const pendingCount = queuedUpdates[instance.instance_id]?.length || 0;
        
        return `
            <div class="instance-item">
                <div class="instance-header">
                    <div>
                        <div class="instance-id">${instance.instance_id.substring(0, 20)}...</div>
                        <span class="instance-status ${stale ? 'status-stale' : 'status-active'}">
                            ${stale ? 'Stale' : 'Active'}
                        </span>
                        ${pendingCount > 0 ? `<span class="badge badge-warning">${pendingCount} pending</span>` : ''}
                    </div>
                    <button class="view-logs-btn" onclick="openLogsModal('${instance.instance_id}', '${instance.node_id}')">
                        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                            <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
                            <polyline points="14,2 14,8 20,8"/>
                            <line x1="16" y1="13" x2="8" y2="13"/>
                            <line x1="16" y1="17" x2="8" y2="17"/>
                            <polyline points="10,9 9,9 8,9"/>
                        </svg>
                        View Logs
                    </button>
                </div>
                <div class="instance-info">
                    <div class="info-item">
                        <span class="info-label">Node ID</span>
                        <span class="info-value">${instance.node_id}</span>
                    </div>
                    <div class="info-item">
                        <span class="info-label">Platform</span>
                        <span class="info-value">${instance.platform}</span>
                    </div>
                    <div class="info-item">
                        <span class="info-label">Current Injection Text</span>
                        <span class="info-value" style="font-size: 11px; word-break: break-all;">${instance.current_injection_text || 'None'}</span>
                    </div>
                    <div class="info-item">
                        <span class="info-label">Uptime</span>
                        <span class="info-value">${Math.floor(instance.uptime_seconds / 3600)}h ${Math.floor((instance.uptime_seconds % 3600) / 60)}m</span>
                    </div>
                </div>
                <div class="instance-footer">
                    <div class="last-seen">
                        Last seen: ${formatDate(instance.last_seen)}
                        <span class="time-ago">(${timeAgo(instance.last_seen)})</span>
                    </div>
                    <div class="api-calls">
                        <span class="api-calls-count">${instance.api_calls_total || 0}</span> API calls
                    </div>
                </div>
            </div>
        `;
    }).join('');
}

function renderInstanceSelector() {
    const container = document.getElementById('instance-selector');
    
    if (instances.length === 0) {
        container.innerHTML = '<div class="empty-state"><p>No instances available</p></div>';
        return;
    }

    container.innerHTML = `
        <button type="button" class="select-all" onclick="selectAllInstances()">Select All</button>
        ${instances.map(instance => `
            <div class="checkbox-item">
                <input type="checkbox" id="inst-${instance.instance_id}" value="${instance.instance_id}" checked>
                <label for="inst-${instance.instance_id}">
                    ${instance.node_id} 
                    <span style="color: #999; font-size: 11px;">(${instance.instance_id.substring(0, 12)}...)</span>
                </label>
            </div>
        `).join('')}
    `;
}

function renderUrlInstanceSelector() {
    const container = document.getElementById('url-instance-selector');
    
    if (instances.length === 0) {
        container.innerHTML = '<div class="empty-state"><p>No instances available</p></div>';
        return;
    }

    container.innerHTML = `
        <button type="button" class="select-all" onclick="selectAllUrlInstances()">Select All</button>
        ${instances.map(instance => `
            <div class="checkbox-item">
                <input type="checkbox" id="url-inst-${instance.instance_id}" value="${instance.instance_id}" checked>
                <label for="url-inst-${instance.instance_id}">
                    ${instance.node_id} 
                    <span style="color: #999; font-size: 11px;">(${instance.instance_id.substring(0, 12)}...)</span>
                </label>
            </div>
        `).join('')}
    `;
}

function renderQueuedUpdates() {
    const container = document.getElementById('queued-updates-container');
    const totalQueued = Object.values(queuedUpdates).reduce((sum, updates) => sum + updates.length, 0);
    
    if (totalQueued === 0) {
        container.innerHTML = '<div class="empty-state"><p>No queued updates</p></div>';
        return;
    }

    container.innerHTML = Object.entries(queuedUpdates).map(([instanceId, updates]) => {
        const instance = instances.find(i => i.instance_id === instanceId);
        const instanceName = instance ? instance.node_id : instanceId.substring(0, 20);
        
        return updates.map(update => {
            // Handle both injection text and init URL updates
            let updateContent = '';
            if (update.extra_note_text !== undefined) {
                const text = update.extra_note_text;
                updateContent = `Injection: "${text.substring(0, 50)}${text.length > 50 ? '...' : ''}"`;
            } else if (update.init_url !== undefined) {
                const url = update.init_url;
                updateContent = `Init URL: "${url.substring(0, 50)}${url.length > 50 ? '...' : ''}"`;
            } else {
                updateContent = 'Unknown update type';
            }
            
            return `
                <div class="update-item">
                    <strong>${instanceName}</strong><br>
                    ${updateContent}<br>
                    <small>Queued: ${formatDate(update.timestamp)}</small>
                </div>
            `;
        }).join('');
    }).join('');
}

function updateStatusBar() {
    document.getElementById('instance-count').textContent = instances.length;
    const totalQueued = Object.values(queuedUpdates).reduce((sum, updates) => sum + updates.length, 0);
    document.getElementById('queued-count').textContent = totalQueued;
    document.getElementById('last-refresh').textContent = new Date().toLocaleTimeString();
}

// Event handlers
function selectAllInstances() {
    const checkboxes = document.querySelectorAll('#instance-selector input[type="checkbox"]');
    const allChecked = Array.from(checkboxes).every(cb => cb.checked);
    checkboxes.forEach(cb => cb.checked = !allChecked);
}

function getSelectedInstances() {
    const checkboxes = document.querySelectorAll('#instance-selector input[type="checkbox"]:checked');
    return Array.from(checkboxes).map(cb => cb.value);
}

async function handleUpdate(event) {
    event.preventDefault();
    
    const text = document.getElementById('injection-text').value;
    const selectedInstances = getSelectedInstances();
    
    if (selectedInstances.length === 0) {
        showAlert('Please select at least one instance', 'error');
        return;
    }

    try {
        const results = [];
        
        // Send update to each selected instance
        for (const instanceId of selectedInstances) {
            const response = await fetch('/manage/set-injection', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    text: text,
                    instance_id: instanceId
                })
            });
            
            const result = await response.json();
            results.push(result);
        }

        showAlert(`Update queued for ${selectedInstances.length} instance(s)`, 'success');
        document.getElementById('injection-text').value = '';
        
        // Reload data
        setTimeout(() => {
            loadInstances();
            loadQueuedUpdates();
        }, 1000);
        
    } catch (error) {
        showAlert(`Error: ${error.message}`, 'error');
    }
}

async function handlePushUpdate() {
    const text = document.getElementById('injection-text').value;
    const selectedInstances = getSelectedInstances();
    
    if (!text) {
        showAlert('Please enter injection text', 'error');
        return;
    }
    
    if (selectedInstances.length === 0) {
        showAlert('Please select at least one instance', 'error');
        return;
    }

    try {
        const results = [];
        
        for (const instanceId of selectedInstances) {
            const response = await fetch('/manage/push-injection', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    text: text,
                    instance_id: instanceId
                })
            });
            
            const result = await response.json();
            results.push(result);
        }

        const successCount = results.filter(r => r.success).length;
        const queuedCount = results.filter(r => r.method === 'queued_fallback').length;
        
        if (queuedCount > 0) {
            showAlert(`${successCount} pushed immediately, ${queuedCount} queued (not reachable)`, 'success');
        } else {
            showAlert(`Update pushed to ${successCount} instance(s)`, 'success');
        }
        
        document.getElementById('injection-text').value = '';
        
        setTimeout(() => {
            loadInstances();
            loadQueuedUpdates();
        }, 1000);
        
    } catch (error) {
        showAlert(`Error: ${error.message}`, 'error');
    }
}

function showAlert(message, type, containerId = 'alert-container') {
    const container = document.getElementById(containerId);
    container.innerHTML = `<div class="alert alert-${type}">${message}</div>`;
    setTimeout(() => {
        container.innerHTML = '';
    }, 5000);
}

// URL update functions
function selectAllUrlInstances() {
    const checkboxes = document.querySelectorAll('#url-instance-selector .checkbox-item input[type="checkbox"]');
    const allChecked = Array.from(checkboxes).every(cb => cb.checked);
    checkboxes.forEach(cb => cb.checked = !allChecked);
}

function getSelectedUrlInstances() {
    const checkboxes = document.querySelectorAll('#url-instance-selector .checkbox-item input[type="checkbox"]:checked');
    return Array.from(checkboxes).map(cb => cb.value);
}

async function handleUrlUpdate(event) {
    if (event) {
        event.preventDefault();
        event.stopPropagation();
    }
    
    const url = document.getElementById('init-url').value;
    const selectedInstances = getSelectedUrlInstances();
    
    if (!url) {
        showAlert('Please enter a URL', 'error', 'url-alert-container');
        return false;
    }
    
    if (selectedInstances.length === 0) {
        showAlert('Please select at least one instance', 'error', 'url-alert-container');
        return false;
    }

    try {
        const results = [];
        
        for (const instanceId of selectedInstances) {
            const response = await fetch('/manage/set-init-url', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    url: url,
                    instance_id: instanceId
                })
            });
            
            const result = await response.json();
            results.push(result);
        }

        showAlert(`URL update queued for ${selectedInstances.length} instance(s)`, 'success', 'url-alert-container');
        
        setTimeout(() => {
            loadInstances();
            loadQueuedUpdates();
        }, 1000);
        
    } catch (error) {
        showAlert(`Error: ${error.message}`, 'error', 'url-alert-container');
    }
    
    return false;
}

async function handlePushUrlUpdate(event) {
    if (event) {
        event.preventDefault();
        event.stopPropagation();
    }
    
    const url = document.getElementById('init-url').value;
    const selectedInstances = getSelectedUrlInstances();
    
    if (!url) {
        showAlert('Please enter a URL', 'error', 'url-alert-container');
        return false;
    }
    
    if (selectedInstances.length === 0) {
        showAlert('Please select at least one instance', 'error', 'url-alert-container');
        return false;
    }

    try {
        const results = [];
        
        for (const instanceId of selectedInstances) {
            const response = await fetch('/manage/push-init-url', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    url: url,
                    instance_id: instanceId
                })
            });
            
            const result = await response.json();
            results.push(result);
        }

        const successCount = results.filter(r => r.success).length;
        const queuedCount = results.filter(r => r.method === 'queued_fallback').length;
        
        if (queuedCount > 0) {
            showAlert(`${successCount} pushed immediately, ${queuedCount} queued (not reachable)`, 'success', 'url-alert-container');
        } else {
            showAlert(`URL update pushed to ${successCount} instance(s)`, 'success', 'url-alert-container');
        }
        
        setTimeout(() => {
            loadInstances();
            loadQueuedUpdates();
        }, 1000);
        
    } catch (error) {
        showAlert(`Error: ${error.message}`, 'error', 'url-alert-container');
    }
}

// Initialize application
document.addEventListener('DOMContentLoaded', () => {
    loadInstances();
    loadQueuedUpdates();
    
    // Set up auto-refresh
    setInterval(() => {
        loadInstances();
        loadQueuedUpdates();
    }, 30000); // Refresh every 30 seconds
    
    // Set up form handlers
    const form = document.getElementById('update-form');
    if (form) {
        form.addEventListener('submit', handleUpdate);
    }
    
    const urlForm = document.getElementById('url-update-form');
    if (urlForm) {
        urlForm.addEventListener('submit', handleUrlUpdate);
    }
});

// Logs modal functions
async function openLogsModal(instanceId, nodeName) {
    const modal = document.getElementById('logs-modal');
    const title = document.getElementById('logs-modal-title');
    
    title.textContent = `Logs - ${nodeName}`;
    modal.classList.add('active');
    
    // Reset tabs
    document.querySelectorAll('.tab-btn').forEach(btn => btn.classList.remove('active'));
    document.querySelector('[data-tab="current"]').classList.add('active');
    document.querySelectorAll('.tab-content').forEach(tab => tab.classList.remove('active'));
    document.getElementById('current-logs-tab').classList.add('active');
    
    // Fetch logs
    try {
        const response = await fetch(`/manage/instance/${instanceId}/logs`);
        const data = await response.json();
        currentInstanceLogs = data;
        
        renderCurrentLogs(data.current_session_logs || []);
        renderSessionHistory(data.mcp_session_logs || []);
    } catch (error) {
        document.getElementById('current-logs-container').innerHTML = 
            `<div class="alert alert-error">Error loading logs: ${error.message}</div>`;
    }
}

function closeLogsModal() {
    const modal = document.getElementById('logs-modal');
    modal.classList.remove('active');
    currentInstanceLogs = null;
}

function switchTab(tabName) {
    // Update tab buttons
    document.querySelectorAll('.tab-btn').forEach(btn => btn.classList.remove('active'));
    document.querySelector(`[data-tab="${tabName}"]`).classList.add('active');
    
    // Update tab content
    document.querySelectorAll('.tab-content').forEach(tab => tab.classList.remove('active'));
    document.getElementById(`${tabName === 'current' ? 'current' : 'history'}-logs-tab`).classList.add('active');
}

function renderCurrentLogs(logs) {
    const container = document.getElementById('current-logs-container');
    
    if (!logs || logs.length === 0) {
        container.innerHTML = `
            <div class="empty-state">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor">
                    <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
                    <polyline points="14,2 14,8 20,8"/>
                </svg>
                <p>No logs for current session</p>
            </div>
        `;
        return;
    }
    
    container.innerHTML = `
        <div class="logs-summary">
            <span>${logs.length} tool call${logs.length !== 1 ? 's' : ''}</span>
        </div>
        <div class="logs-list">
            ${logs.map(log => renderLogEntry(log)).join('')}
        </div>
    `;
}

function renderSessionHistory(sessions) {
    const container = document.getElementById('history-logs-container');
    
    if (!sessions || sessions.length === 0) {
        container.innerHTML = `
            <div class="empty-state">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor">
                    <path d="M12 8v4l3 3"/>
                    <circle cx="12" cy="12" r="10"/>
                </svg>
                <p>No session history available</p>
            </div>
        `;
        return;
    }
    
    container.innerHTML = sessions.map(session => `
        <div class="session-card">
            <div class="session-header">
                <div class="session-id">
                    <strong>Session:</strong> ${session.sessionId}
                </div>
                <div class="session-meta">
                    <span class="session-time">${formatDate(session.startTime)}</span>
                    <span class="session-entries">${session.totalEntries || session.logs?.length || 0} entries</span>
                </div>
            </div>
            <div class="session-logs">
                ${(session.logs || []).map(log => renderLogEntry(log)).join('')}
            </div>
        </div>
    `).join('');
}

function renderLogEntry(log) {
    const toolColor = getToolColor(log.tool);
    const isSuccess = !log.error;
    
    // Determine what to show in the details
    let detailsHtml = '';
    
    if (log.input && Object.keys(log.input).length > 0) {
        detailsHtml += `
            <div class="log-section">
                <div class="log-section-title">Input</div>
                <pre class="log-code">${escapeHtml(JSON.stringify(log.input, null, 2))}</pre>
            </div>
        `;
    }
    
    if (log.output) {
        detailsHtml += `
            <div class="log-section">
                <div class="log-section-title">Output</div>
                <pre class="log-code">${escapeHtml(typeof log.output === 'string' ? log.output : JSON.stringify(log.output, null, 2))}</pre>
            </div>
        `;
    }
    
    if (log.download) {
        detailsHtml += `
            <div class="log-section">
                <div class="log-section-title">Download</div>
                <div class="download-info">
                    <div><strong>URL:</strong> ${escapeHtml(log.download.url || 'N/A')}</div>
                    <div><strong>Size:</strong> ${log.download.file_size ? formatBytes(log.download.file_size) : 'N/A'}</div>
                    <div><strong>Time:</strong> ${log.download.download_time ? log.download.download_time.toFixed(2) + 's' : 'N/A'}</div>
                    <div><strong>Status:</strong> ${log.download.success ? '✅ Success' : '❌ Failed'}</div>
                </div>
            </div>
        `;
    }
    
    if (log.execution) {
        detailsHtml += `
            <div class="log-section">
                <div class="log-section-title">Execution</div>
                <pre class="log-code">${escapeHtml(log.execution)}</pre>
            </div>
        `;
    }
    
    if (log.error) {
        detailsHtml += `
            <div class="log-section log-section-error">
                <div class="log-section-title">Error</div>
                <pre class="log-code">${escapeHtml(log.error)}</pre>
            </div>
        `;
    }
    
    return `
        <div class="log-entry ${isSuccess ? 'log-success' : 'log-error'}">
            <div class="log-header">
                <span class="log-tool" style="background: ${toolColor};">${escapeHtml(log.tool || log.type || 'unknown')}</span>
                <span class="log-timestamp">${formatDate(log.timestamp)}</span>
                ${log.total_time ? `<span class="log-duration">${log.total_time.toFixed(2)}s</span>` : ''}
            </div>
            ${detailsHtml ? `<div class="log-details">${detailsHtml}</div>` : ''}
        </div>
    `;
}

function getToolColor(tool) {
    const colors = {
        'init': '#e74c3c',
        'hello_world': '#3498db',
        'ask_claude': '#9b59b6',
        'execute_file': '#e67e22',
        'download_and_execute': '#c0392b',
        'get_server_info': '#1abc9c',
        'TOOL_CALL': '#667eea',
        'REMOTE_CONFIG_UPDATE': '#f39c12'
    };
    return colors[tool] || '#95a5a6';
}

function escapeHtml(text) {
    if (!text) return '';
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

function formatBytes(bytes) {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
}

// Close modal on escape key
document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') {
        closeLogsModal();
    }
});

// Close modal when clicking outside
document.addEventListener('click', (e) => {
    const modal = document.getElementById('logs-modal');
    if (e.target === modal) {
        closeLogsModal();
    }
});

// Make functions available globally for onclick handlers
window.loadInstances = loadInstances;
window.selectAllInstances = selectAllInstances;
window.selectAllUrlInstances = selectAllUrlInstances;
window.handlePushUpdate = handlePushUpdate;
window.handlePushUrlUpdate = handlePushUrlUpdate;
window.handleUrlUpdate = handleUrlUpdate;
window.openLogsModal = openLogsModal;
window.closeLogsModal = closeLogsModal;
window.switchTab = switchTab;

