document.addEventListener('DOMContentLoaded', () => {
    const streamContainer = document.getElementById('stream-container');
    const inspectorContent = document.getElementById('inspector-content');
    const inspectorTitle = document.getElementById('inspector-title');
    const inspectorCommand = document.getElementById('inspector-command');
    const connectionStatus = document.getElementById('connection-status');
    const connectionLine = document.getElementById('connection-line');
    const killSwitch = document.getElementById('kill-switch');

    // Layer mapping to HUD components
    const layerMap = {
        'policy': 'hud-l1',
        'risk_tier': 'hud-l2',
        'injection': 'hud-l3',
        'injection_dos': 'hud-l3', // Map both injection types to L3 HUD
        'rate_limit': 'hud-l4',
        'semantic': 'hud-l5',
        'drift': 'hud-l6',
        'trace': 'hud-l7'
    };

    let counter = 0;

    // Load initial history
    fetch('/api/traces')
        .then(res => res.json())
        .then(data => {
            if (data.traces && data.traces.length > 0) {
                streamContainer.innerHTML = '';
                // Render oldest to newest at bottom, or newest at top?
                // For terminal tail -f, we usually want newest at bottom.
                data.traces.forEach(trace => processTrace(trace, false));
            }
        });

    // Setup SSE
    const evtSource = new EventSource('/api/stream');
    evtSource.addEventListener('new_trace', (e) => {
        const trace = JSON.parse(e.data);
        processTrace(trace, true);
    });

    // Kill-Switch Logic (HUD Integrated)
    killSwitch.addEventListener('click', () => {
        const isSecure = !killSwitch.classList.contains('unsafe');
        const textEl = document.getElementById('kill-switch-text');
        
        if (isSecure) {
            killSwitch.classList.add('unsafe');
            if (textEl) textEl.innerText = 'UNSAFE';
        } else {
            killSwitch.classList.remove('unsafe');
            if (textEl) textEl.innerText = 'SECURE';
        }
        
        fetch('/api/toggle_security', { method: 'POST' }).catch(e => console.error("Kill-switch sync failed", e));
    });

    evtSource.onerror = (err) => {
        console.error("EventSource failed:", err);
        connectionStatus.innerText = 'Proxy Disconnected';
        connectionStatus.style.color = '#ff3b30';
    };

    function processTrace(trace, prepend = false) {
        if (!trace.tool || !trace.decision) return;

        // Drive the Sentinel HUD
        updateHUD(trace);
        
        // Remove empty state if present
        const emptyState = streamContainer.querySelector('.empty-state');
        if (emptyState) emptyState.remove();

        const card = document.createElement('div');
        const isDeny = trace.decision !== "ALLOWED";
        card.className = `trace-card ${isDeny ? 'deny' : 'allow'}`;
        
        // Use timestamp as ID
        const traceId = trace.timestamp || Date.now();
        card.dataset.id = traceId;

        // Format Date
        const dateObj = new Date((trace.timestamp || 0) * 1000);
        const timeStr = isNaN(dateObj.getTime()) ? "00:00:00" : dateObj.toLocaleTimeString('en-US', { hour12: false, hour: '2-digit', minute: '2-digit', second: '2-digit' }) + '.' + String(dateObj.getMilliseconds()).padStart(3, '0');

        const latencyStr = (trace.latency_ms !== undefined) ? `${trace.latency_ms}ms` : '';
        const isSpoofed = trace.raw_tool && (trace.raw_tool.toLowerCase().trim() !== trace.tool.toLowerCase().trim());

        card.innerHTML = `
            <div class="card-header">
                <span class="tool-name">
                    ${trace.tool}
                    ${isSpoofed ? `<span class="spoof-flag" title="Original: ${trace.raw_tool}">[FAKE]</span>` : ''}
                </span>
                <span class="decision-badge ${isDeny ? 'decision-deny' : 'decision-allow'}">
                    ${isDeny ? 'BLOCKED' : 'ALLOW'}
                </span>
            </div>
            <div class="card-meta">
                <span class="timestamp">${timeStr}</span>
                <span class="latency-badge">${latencyStr}</span>
            </div>
        `;

        card.addEventListener('click', () => {
            document.querySelectorAll('.trace-card').forEach(c => c.classList.remove('active'));
            card.classList.add('active');
            renderInspector(trace, isDeny);
        });

        if (prepend) {
            streamContainer.prepend(card);
            // Flash animation for new cards
            card.style.opacity = '0';
            card.style.transform = 'translateY(-10px)';
            setTimeout(() => {
                card.style.transition = 'all 0.4s ease';
                card.style.opacity = '1';
                card.style.transform = 'translateY(0)';
            }, 50);
        } else {
            streamContainer.appendChild(card);
        }
    }

    function renderInspector(trace, isDeny) {
        let html = '';
        
        if (isDeny) {
            html += `
                <div class="reason-box">
                    🚨 <strong>Intercepted:</strong> ${trace.reason || 'Blocked by Policy'}
                </div>
            `;
        }

        html += `
            <div class="inspector-section">
                <h3>Arguments Payload</h3>
                <pre class="code-block">${JSON.stringify(trace.arguments || {}, null, 2)}</pre>
            </div>
        `;

        if (trace.layer) {
            html += `
                <div class="inspector-section">
                    <h3>Interceptor Result</h3>
                    <div class="status-pill status-${isDeny ? 'deny' : 'allow'}">
                        LAYER: ${trace.layer.toUpperCase()} | LATENCY: ${trace.latency_ms || '0'}ms
                    </div>
                </div>
            `;
        }

        if (trace.raw_tool && trace.raw_tool !== trace.tool) {
            html += `
                <div class="inspector-section">
                    <h3>Identity Spoof Detected</h3>
                    <pre class="code-block danger-block">Raw Input Tool: "${trace.raw_tool}"\nPolicy Target:   "${trace.tool}"</pre>
                </div>
            `;
        }

        // Enterprise Context (v6.1.0)
        const storageLabel = trace.storage_mode === 'redis' ? '🔴 Redis (Distributed)' : '💾 Local (SQLite/JSON)';
        const webhookLabel = trace.webhook_enabled ? '✅ Webhook Active' : '⚫ Webhook Disabled';
        html += `
            <div class="inspector-section">
                <h3>Enterprise Context</h3>
                <div class="status-pill" style="background: #1a1a2e; border: 1px solid #333; margin-bottom: 0.5rem;">
                    STORAGE: ${storageLabel}
                </div>
                <div class="status-pill" style="background: #1a1a2e; border: 1px solid #333;">
                    APPROVALS: ${webhookLabel}
                </div>
            </div>
        `;
        
        // Render Full Raw JSON at bottom
        html += `
            <div class="inspector-section" style="margin-top: 3rem; opacity: 0.5;">
                <h3>Raw Trace Object</h3>
                <pre class="code-block" style="font-size: 0.7rem;">${JSON.stringify(trace, null, 2)}</pre>
            </div>
        `;

        inspectorContent.innerHTML = html;
        inspectorContent.scrollTop = 0;
    }

    function updateHUD(trace) {
        const layerId = layerMap[trace.layer];
        if (!layerId) return;

        const hudItem = document.getElementById(layerId);
        if (!hudItem) return;

        // Clear previous state
        hudItem.classList.remove('active', 'warn', 'block');

        // Apply new state
        const isDeny = trace.decision !== "ALLOWED";
        if (isDeny) {
            hudItem.classList.add('block');
        } else {
            hudItem.classList.add('active');
            // Brief pulse for allowed calls
            setTimeout(() => {
                hudItem.classList.remove('active');
            }, 800);
        }
    }
});
