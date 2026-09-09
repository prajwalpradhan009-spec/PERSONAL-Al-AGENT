/**
 * AI Voice Agent HUD - Main Application Orchestrator
 */

document.addEventListener('DOMContentLoaded', () => {
    // Core Instances
    const visualizer = new NeuralOrbVisualizer('neuralOrbCanvas');
    const audioCtrl = new AudioController();

    // DOM Elements - Header
    const agentStatusPill = document.getElementById('agentStatusPill');
    const agentStatusLabel = document.getElementById('agentStatusLabel');
    const ollamaStatusPill = document.getElementById('ollamaStatusPill');
    const ollamaStatusText = document.getElementById('ollamaStatusText');
    const personaSelect = document.getElementById('personaSelect');
    const voiceMuteBtn = document.getElementById('voiceMuteBtn');
    const telemetryToggleBtn = document.getElementById('telemetryToggleBtn');
    const settingsBtn = document.getElementById('settingsBtn');
    
    // View Switcher
    const viewSplitBtn = document.getElementById('viewSplitBtn');
    const viewOrbBtn = document.getElementById('viewOrbBtn');
    const viewChatBtn = document.getElementById('viewChatBtn');
    const mainWorkspace = document.getElementById('mainWorkspace');

    // Sidebar & Telemetry
    const sidebarPanel = document.getElementById('sidebarPanel');
    const collapseSidebarBtn = document.getElementById('collapseSidebarBtn');
    const newChatBtn = document.getElementById('newChatBtn');
    const sessionsList = document.getElementById('sessionsList');
    const telemetryPanel = document.getElementById('telemetryPanel');
    const closeTelemetryBtn = document.getElementById('closeTelemetryBtn');

    // Stage HUD & Waveform
    const liveTranscriptText = document.getElementById('liveTranscriptText');
    const waveformBarContainer = document.getElementById('waveformBarContainer');
    const hudLatency = document.getElementById('hudLatency');

    // Messages & Feed
    const messagesContainer = document.getElementById('messagesContainer');
    const clearChatBtn = document.getElementById('clearChatBtn');
    const exportChatBtn = document.getElementById('exportChatBtn');

    // Telemetry Elements
    const telemetryCpuVal = document.getElementById('telemetryCpuVal');
    const telemetryCpuBar = document.getElementById('telemetryCpuBar');
    const telemetryCpuSub = document.getElementById('telemetryCpuSub');
    const telemetryRamVal = document.getElementById('telemetryRamVal');
    const telemetryRamBar = document.getElementById('telemetryRamBar');
    const telemetryRamSub = document.getElementById('telemetryRamSub');
    const telemetryDiskVal = document.getElementById('telemetryDiskVal');
    const telemetryDiskBar = document.getElementById('telemetryDiskBar');
    const telemetryDiskSub = document.getElementById('telemetryDiskSub');
    const telemetryNetVal = document.getElementById('telemetryNetVal');
    const telemetryNetDown = document.getElementById('telemetryNetDown');
    const telemetryNetUp = document.getElementById('telemetryNetUp');
    const telemetryOs = document.getElementById('telemetryOs');
    const telemetryUptime = document.getElementById('telemetryUptime');
    const batteryRow = document.getElementById('batteryRow');
    const telemetryBattery = document.getElementById('telemetryBattery');
    const eventStreamLog = document.getElementById('eventStreamLog');

    // Bottom Controls
    const micBtn = document.getElementById('micBtn');
    const micBtnIcon = document.getElementById('micBtnIcon');
    const micStatusTag = document.getElementById('micStatusTag');
    const continuousListenBtn = document.getElementById('continuousListenBtn');
    const chatInput = document.getElementById('chatInput');
    const sendBtn = document.getElementById('sendBtn');
    const ttsSpeedSlider = document.getElementById('ttsSpeedSlider');
    const speedValText = document.getElementById('speedValText');

    // Settings Modal
    const settingsModal = document.getElementById('settingsModal');
    const closeSettingsBtn = document.getElementById('closeSettingsBtn');
    const cancelSettingsBtn = document.getElementById('cancelSettingsBtn');
    const saveSettingsBtn = document.getElementById('saveSettingsBtn');
    const refreshModelsBtn = document.getElementById('refreshModelsBtn');
    const settingPartnerIp = document.getElementById('settingPartnerIp');
    const settingOllamaPort = document.getElementById('settingOllamaPort');
    const settingOllamaModel = document.getElementById('settingOllamaModel');
    const settingVoice = document.getElementById('settingVoice');
    const settingAudioTarget = document.getElementById('settingAudioTarget');
    const settingAutoExecute = document.getElementById('settingAutoExecute');
    const detectedModelsChips = document.getElementById('detectedModelsChips');

    // State Variables
    let currentSessionId = 'default';
    let currentState = 'idle';
    let isContinuousListening = false;
    let ws = null;
    let pingInterval = null;

    // Build Waveform Spectrum Bars
    const waveBarCount = 28;
    const waveBars = [];
    waveformBarContainer.innerHTML = '';
    for (let i = 0; i < waveBarCount; i++) {
        const bar = document.createElement('div');
        bar.className = 'wave-bar';
        waveformBarContainer.appendChild(bar);
        waveBars.push(bar);
    }

    // Audio Controller Callbacks
    audioCtrl.onFrequencyData = (freqArray) => {
        visualizer.setAudioFrequencyData(freqArray);
        
        // Update Waveform bars
        const step = Math.floor(freqArray.length / waveBarCount) || 1;
        for (let i = 0; i < waveBarCount; i++) {
            const val = freqArray[i * step] || 0;
            const h = Math.max(3, (val / 255) * 24);
            waveBars[i].style.height = `${h}px`;
            if (currentState === 'listening') {
                waveBars[i].style.background = 'var(--neon-emerald)';
            } else if (currentState === 'speaking') {
                waveBars[i].style.background = 'var(--neon-cyan)';
            } else {
                waveBars[i].style.background = 'rgba(0, 240, 255, 0.4)';
            }
        }
    };

    audioCtrl.onSpeechResult = ({ final, interim }) => {
        if (interim) {
            liveTranscriptText.textContent = `🎙️ "${interim}..."`;
        }
        if (final && final.trim()) {
            liveTranscriptText.textContent = `🎤 "${final}"`;
            chatInput.value = final;
            submitPrompt(final);
        }
    };

    audioCtrl.onRecordingStateChange = (isRec) => {
        if (isRec) {
            setAgentState('listening');
            micBtn.classList.add('active');
            micBtnIcon.className = 'fa-solid fa-waveform-lines';
            micStatusTag.textContent = 'LISTENING...';
        } else {
            micBtn.classList.remove('active');
            micBtnIcon.className = 'fa-solid fa-microphone';
            micStatusTag.textContent = isContinuousListening ? 'AUTO LISTEN' : 'PUSH TO TALK';
            if (currentState === 'listening') {
                setAgentState('idle');
            }
        }
    };

    // Agent State Manager
    function setAgentState(state) {
        if (currentState === state) return;
        currentState = state;
        visualizer.setState(state);

        // Update Header Status Pill
        agentStatusPill.className = `status-pill status-${state}`;
        agentStatusLabel.textContent = state.toUpperCase();

        if (state === 'idle') {
            liveTranscriptText.textContent = 'AI Neural Assistant Standby. Click mic or type below...';
        } else if (state === 'listening') {
            liveTranscriptText.textContent = 'Listening to voice input...';
        } else if (state === 'thinking') {
            liveTranscriptText.textContent = 'Synthesizing neural response...';
        } else if (state === 'executing') {
            liveTranscriptText.textContent = 'Executing system tool action...';
        } else if (state === 'speaking') {
            liveTranscriptText.textContent = 'Speaking response...';
        }
    }

    // WebSocket Manager
    function connectWebSocket() {
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const wsUrl = `${protocol}//${window.location.host}/ws`;

        logEvent('[SYS] Connecting WebSocket to neural hub...', 'info');
        ws = new WebSocket(wsUrl);

        ws.onopen = () => {
            logEvent('[SYS] WebSocket connected.', 'info');
            if (pingInterval) clearInterval(pingInterval);
            pingInterval = setInterval(() => {
                if (ws && ws.readyState === WebSocket.OPEN) {
                    ws.send(JSON.stringify({ type: 'ping' }));
                }
            }, 10000);
        };

        ws.onmessage = (event) => {
            try {
                const msg = JSON.parse(event.data);
                handleWsMessage(msg);
            } catch (e) {
                console.error('Error parsing WS message:', e);
            }
        };

        ws.onclose = () => {
            logEvent('[SYS] WebSocket disconnected. Reconnecting in 3s...', 'warn');
            setTimeout(connectWebSocket, 3000);
        };

        ws.onerror = () => {
            ws.close();
        };
    }

    function handleWsMessage(msg) {
        switch (msg.type) {
            case 'init':
                applyConfig(msg.config);
                updateTelemetryUI(msg.telemetry);
                checkOllama();
                break;
            case 'telemetry':
                updateTelemetryUI(msg.data);
                break;
            case 'agent_state':
                setAgentState(msg.state);
                break;
            case 'new_message':
                if (msg.session_id === currentSessionId && msg.data) {
                    // Check if already rendered
                    if (!document.getElementById(msg.data.message_id)) {
                        renderMessageCard(msg.data, 'assistant');
                    }
                }
                break;
            case 'config_updated':
                applyConfig(msg.config);
                break;
        }
    }

    // Telemetry UI Updates
    function updateTelemetryUI(t) {
        if (!t) return;
        
        // CPU
        telemetryCpuVal.textContent = `${t.cpu.percent}%`;
        telemetryCpuBar.style.width = `${Math.min(100, t.cpu.percent)}%`;
        telemetryCpuSub.textContent = `Cores: ${t.cpu.cores} | Freq: ${t.cpu.freq_mhz} MHz`;

        // RAM
        telemetryRamVal.textContent = `${t.memory.percent}%`;
        telemetryRamBar.style.width = `${Math.min(100, t.memory.percent)}%`;
        telemetryRamSub.textContent = `${t.memory.used_gb} GB / ${t.memory.total_gb} GB`;

        // Disk
        telemetryDiskVal.textContent = `${t.disk.percent}%`;
        telemetryDiskBar.style.width = `${Math.min(100, t.disk.percent)}%`;
        telemetryDiskSub.textContent = `${t.disk.free_gb} GB free of ${t.disk.total_gb} GB`;

        // Network
        const totalNet = t.network.download_speed_kb + t.network.upload_speed_kb;
        telemetryNetVal.textContent = `${totalNet.toFixed(1)} KB/s`;
        telemetryNetDown.textContent = `${t.network.download_speed_kb} KB/s`;
        telemetryNetUp.textContent = `${t.network.upload_speed_kb} KB/s`;

        // OS & Uptime
        telemetryOs.textContent = `${t.os.system} (${t.os.machine})`;
        telemetryUptime.textContent = t.uptime.formatted;

        // Battery
        if (t.battery) {
            batteryRow.style.display = 'flex';
            const charging = t.battery.power_plugged ? '⚡' : '🔋';
            telemetryBattery.textContent = `${t.battery.percent}% ${charging}`;
        }
    }

    function logEvent(text, level = 'info') {
        const line = document.createElement('div');
        line.className = `log-line ${level}`;
        line.textContent = `[${new Date().toLocaleTimeString()}] ${text}`;
        eventStreamLog.appendChild(line);
        eventStreamLog.scrollTop = eventStreamLog.scrollHeight;
    }

    // Ollama Health Check
    async function checkOllama() {
        try {
            const res = await fetch('/api/models');
            const data = await res.json();
            if (data.online) {
                ollamaStatusPill.className = 'connection-pill online';
                ollamaStatusText.textContent = `Brain Online (${data.count} models)`;
                logEvent(`[OLLAMA] Connected. Found models: ${data.models.join(', ')}`, 'info');
            } else {
                ollamaStatusPill.className = 'connection-pill offline';
                ollamaStatusText.textContent = 'Brain Offline (Rule Engine Ready)';
                logEvent(`[OLLAMA] Unreachable. Rule-based offline engine active.`, 'warn');
            }
        } catch (e) {
            ollamaStatusPill.className = 'connection-pill offline';
            ollamaStatusText.textContent = 'Brain Offline';
        }
    }

    // Submit Prompt Flow
    async function submitPrompt(text) {
        const prompt = (text || chatInput.value).trim();
        if (!prompt) return;

        chatInput.value = '';
        const startTime = Date.now();

        // Render User Message
        const userMsgData = {
            id: `usr_${Date.now()}`,
            content: prompt,
            role: 'user',
            timestamp: new Date().toISOString()
        };
        renderMessageCard(userMsgData, 'user');

        setAgentState('thinking');
        logEvent(`[PROMPT] User: "${prompt}"`, 'info');

        const personaId = personaSelect.value;
        const autoExec = settingAutoExecute.checked;
        const audioTarget = settingAudioTarget ? settingAudioTarget.value : 'browser';

        try {
            const resp = await fetch('/api/chat', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    prompt: prompt,
                    session_id: currentSessionId,
                    persona_id: personaId,
                    generate_audio: !audioCtrl.isMuted,
                    speak_on_server: audioTarget === 'server' || audioTarget === 'both',
                    auto_execute: autoExec
                })
            });

            const latency = Date.now() - startTime;
            hudLatency.textContent = `${latency}ms`;

            if (!resp.ok) {
                throw new Error(`Server returned ${resp.status}`);
            }

            const data = await resp.json();
            renderMessageCard(data, 'assistant');

            if (data.actions && data.actions.length > 0) {
                logEvent(`[ACTION] Executed ${data.actions.length} tool(s).`, 'info');
            }

            // Play audio in browser if available and target includes browser
            if (data.audio_base64 && (audioTarget === 'browser' || audioTarget === 'both')) {
                setAgentState('speaking');
                await audioCtrl.playWavBase64(data.audio_base64, () => {
                    setAgentState('idle');
                    if (isContinuousListening) {
                        setTimeout(() => audioCtrl.startListening(), 400);
                    }
                });
            } else {
                setAgentState('idle');
                if (isContinuousListening) {
                    setTimeout(() => audioCtrl.startListening(), 400);
                }
            }

        } catch (err) {
            console.error('Chat error:', err);
            logEvent(`[ERROR] Chat error: ${err.message}`, 'err');
            setAgentState('idle');
            renderMessageCard({
                text: `Error communicating with agent: ${err.message}`,
                timestamp: new Date().toISOString()
            }, 'assistant');
        }
    }

    // Render Message Cards & Action Logs
    function renderMessageCard(msg, role = 'assistant') {
        const card = document.createElement('div');
        card.id = msg.message_id || `msg_${Date.now()}`;
        card.className = `message-card ${role}-message`;

        const isUser = role === 'user';
        const avatarIcon = isUser ? 'fa-user' : 'fa-robot';
        const authorName = isUser ? 'You' : (personaSelect.options[personaSelect.selectedIndex]?.text.split(' ')[1] || 'Agent');
        const timeStr = msg.timestamp ? new Date(msg.timestamp).toLocaleTimeString() : new Date().toLocaleTimeString();

        let formattedContent = '';
        if (typeof marked !== 'undefined' && marked.parse) {
            formattedContent = marked.parse(msg.text || msg.content || '');
        } else {
            formattedContent = `<p>${escapeHtml(msg.text || msg.content || '')}</p>`;
        }

        // Action Cards HTML
        let actionsHtml = '';
        if (msg.actions && msg.actions.length > 0) {
            actionsHtml = msg.actions.map(act => `
                <div class="action-card ${act.status || 'success'}">
                    <div class="action-card-header">
                        <div class="action-type-badge">
                            <i class="fa-solid fa-gear"></i>
                            <span>${act.action_type ? act.action_type.toUpperCase() : 'SYSTEM ACTION'}</span>
                        </div>
                        <span class="action-time">${act.execution_time_ms || 25}ms</span>
                    </div>
                    <div class="action-command-row">
                        <code>${escapeHtml(act.command || '')}</code>
                        <span class="status-badge">${act.status || 'OK'}</span>
                    </div>
                    ${act.output ? `<div class="action-terminal-output">${escapeHtml(act.output)}</div>` : ''}
                </div>
            `).join('');
        }

        // Inline Audio Player if base64 audio present
        let audioPlayerHtml = '';
        if (msg.audio_base64) {
            audioPlayerHtml = `
                <div class="audio-player-widget">
                    <button class="play-pause-btn" onclick="playAudioFromMsg('${msg.audio_base64}', this)">
                        <i class="fa-solid fa-play"></i>
                    </button>
                    <div class="audio-scrubber"><div class="audio-progress"></div></div>
                    <span class="audio-duration">Kokoro Voice</span>
                </div>
            `;
        }

        card.innerHTML = `
            <div class="message-avatar">
                <i class="fa-solid ${avatarIcon}"></i>
            </div>
            <div class="message-body">
                <div class="message-header">
                    <span class="message-author">${authorName}</span>
                    <span class="message-time">${timeStr}</span>
                    ${!isUser && msg.source ? `<span class="source-badge">${msg.source}</span>` : ''}
                </div>
                <div class="message-text">${formattedContent}</div>
                ${actionsHtml}
                ${audioPlayerHtml}
            </div>
        `;

        messagesContainer.appendChild(card);
        messagesContainer.scrollTop = messagesContainer.scrollHeight;
    }

    window.playAudioFromMsg = function(b64, btn) {
        audioCtrl.playWavBase64(b64, () => {
            btn.innerHTML = '<i class="fa-solid fa-play"></i>';
        });
        btn.innerHTML = '<i class="fa-solid fa-volume-high"></i>';
    };

    function escapeHtml(str) {
        return str
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/"/g, "&quot;")
            .replace(/'/g, "&#039;");
    }

    // Settings & Config
    function applyConfig(cfg) {
        if (!cfg) return;
        if (cfg.partner_ip) settingPartnerIp.value = cfg.partner_ip;
        if (cfg.ollama_port) settingOllamaPort.value = cfg.ollama_port;
        if (cfg.ollama_model) settingOllamaModel.value = cfg.ollama_model;
        if (cfg.tts_voice) settingVoice.value = cfg.tts_voice;
        if (cfg.tts_speed) {
            ttsSpeedSlider.value = cfg.tts_speed;
            speedValText.textContent = `${cfg.tts_speed}x`;
        }
        if (cfg.active_persona && personaSelect) {
            personaSelect.value = cfg.active_persona;
        }
        if (typeof cfg.auto_execute_actions === 'boolean') {
            settingAutoExecute.checked = cfg.auto_execute_actions;
        }
    }

    async function saveConfig() {
        const payload = {
            partner_ip: settingPartnerIp.value.trim(),
            ollama_port: parseInt(settingOllamaPort.value) || 11434,
            ollama_model: settingOllamaModel.value.trim(),
            tts_voice: settingVoice.value,
            tts_speed: parseFloat(ttsSpeedSlider.value) || 1.0,
            active_persona: personaSelect.value,
            auto_execute_actions: settingAutoExecute.checked
        };

        try {
            const res = await fetch('/api/config', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });
            if (res.ok) {
                logEvent('[CONFIG] Configuration saved successfully.', 'info');
                settingsModal.classList.remove('open');
                checkOllama();
            }
        } catch (e) {
            logEvent(`[ERROR] Failed to save config: ${e.message}`, 'err');
        }
    }

    async function detectModels() {
        detectedModelsChips.innerHTML = '<span class="model-tag">Scanning...</span>';
        try {
            const res = await fetch('/api/models');
            const data = await res.json();
            detectedModelsChips.innerHTML = '';
            if (data.online && data.models.length > 0) {
                data.models.forEach(model => {
                    const tag = document.createElement('span');
                    tag.className = 'model-tag';
                    tag.textContent = model;
                    tag.onclick = () => { settingOllamaModel.value = model; };
                    detectedModelsChips.appendChild(tag);
                });
            } else {
                detectedModelsChips.innerHTML = '<span class="model-tag">No models found or Ollama offline</span>';
            }
        } catch (e) {
            detectedModelsChips.innerHTML = '<span class="model-tag">Error connecting to server</span>';
        }
    }

    // Sessions Management
    async function loadSessions() {
        try {
            const res = await fetch('/api/sessions');
            const data = await res.json();
            sessionsList.innerHTML = '';
            (data.sessions || []).forEach(s => {
                const item = document.createElement('div');
                item.className = `session-item ${s.id === currentSessionId ? 'active' : ''}`;
                item.innerHTML = `
                    <i class="fa-solid fa-message"></i>
                    <span style="flex:1; overflow:hidden; text-overflow:ellipsis; white-space:nowrap;">${s.preview || s.id}</span>
                `;
                item.onclick = () => switchSession(s.id);
                sessionsList.appendChild(item);
            });
        } catch (e) {}
    }

    function switchSession(sessionId) {
        currentSessionId = sessionId;
        loadSessions();
        // Clear message view and load session messages
        fetch(`/api/sessions/${sessionId}`)
            .then(res => res.json())
            .then(data => {
                messagesContainer.innerHTML = '';
                (data.messages || []).forEach(m => renderMessageCard(m, m.role));
            });
    }

    // UI Event Listeners
    micBtn.addEventListener('click', () => {
        audioCtrl.toggleListening();
    });

    continuousListenBtn.addEventListener('click', () => {
        isContinuousListening = !isContinuousListening;
        continuousListenBtn.classList.toggle('active', isContinuousListening);
        if (isContinuousListening) {
            audioCtrl.startListening();
        } else {
            audioCtrl.stopListening();
        }
    });

    sendBtn.addEventListener('click', () => submitPrompt());
    chatInput.addEventListener('keydown', (e) => {
        if (e.key === 'Enter') submitPrompt();
    });

    // Quick Tool Chips
    document.querySelectorAll('.tool-chip').forEach(btn => {
        btn.addEventListener('click', () => {
            const p = btn.dataset.prompt;
            if (p) {
                chatInput.value = p;
                submitPrompt(p);
            }
        });
    });

    // View Switcher Handlers
    function setViewLayout(mode) {
        viewSplitBtn.classList.toggle('active', mode === 'split');
        viewOrbBtn.classList.toggle('active', mode === 'orb');
        viewChatBtn.classList.toggle('active', mode === 'chat');

        mainWorkspace.className = `hud-main layout-${mode === 'split' ? 'split' : mode + '-only'}`;
        visualizer.resize();
    }

    viewSplitBtn.addEventListener('click', () => setViewLayout('split'));
    viewOrbBtn.addEventListener('click', () => setViewLayout('orb'));
    viewChatBtn.addEventListener('click', () => setViewLayout('chat'));

    // Sidebar & Telemetry Toggles
    collapseSidebarBtn.addEventListener('click', () => {
        sidebarPanel.classList.toggle('collapsed');
        visualizer.resize();
    });

    telemetryToggleBtn.addEventListener('click', () => {
        telemetryPanel.classList.toggle('collapsed');
        telemetryToggleBtn.classList.toggle('active', !telemetryPanel.classList.contains('collapsed'));
        visualizer.resize();
    });

    closeTelemetryBtn.addEventListener('click', () => {
        telemetryPanel.classList.add('collapsed');
        telemetryToggleBtn.classList.remove('active');
        visualizer.resize();
    });

    voiceMuteBtn.addEventListener('click', () => {
        const isMuted = audioCtrl.toggleMute();
        voiceMuteBtn.innerHTML = isMuted ? '<i class="fa-solid fa-volume-xmark"></i>' : '<i class="fa-solid fa-volume-high"></i>';
        voiceMuteBtn.classList.toggle('active', !isMuted);
    });

    // Speed Slider
    ttsSpeedSlider.addEventListener('input', (e) => {
        speedValText.textContent = `${e.target.value}x`;
    });

    // Settings Modal
    settingsBtn.addEventListener('click', () => {
        settingsModal.classList.add('open');
        detectModels();
    });
    closeSettingsBtn.addEventListener('click', () => settingsModal.classList.remove('open'));
    cancelSettingsBtn.addEventListener('click', () => settingsModal.classList.remove('open'));
    saveSettingsBtn.addEventListener('click', saveConfig);
    refreshModelsBtn.addEventListener('click', detectModels);

    newChatBtn.addEventListener('click', () => {
        const newId = `session_${Date.now()}`;
        switchSession(newId);
    });

    clearChatBtn.addEventListener('click', () => {
        messagesContainer.innerHTML = '';
        logEvent('[SYS] Message view cleared.', 'info');
    });

    exportChatBtn.addEventListener('click', () => {
        const text = messagesContainer.innerText;
        const blob = new Blob([text], { type: 'text/plain' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `agent_chat_log_${Date.now()}.txt`;
        a.click();
        URL.revokeObjectURL(url);
    });

    // Initial Startup
    connectWebSocket();
    loadSessions();
});

