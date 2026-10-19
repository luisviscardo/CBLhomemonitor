// CBLhomemonitor - Dashboard Frontend Logic

let trafficChart = null;
let historyChart = null;
let deviceDonutChart = null;
let hardwareHistoryChart = null;

const MAX_CHART_POINTS = 30;
let chartLabels = [];
let chartDownloadData = [];
let chartUploadData = [];
let isChartPaused = false;

let allDevices = [];
let currentDeviceFilter = 'all';
let currentSearchTerm = '';
let currentHistoryPeriod = 'daily';
let currentRankPeriod = 'month';
let currentHwTimeframe = '1h';
let currentHwMetric = 'cpu_ram';
let cachedHwData = null;

let ws = null;
let pollFallbackTimer = null;

// Inicialização
document.addEventListener('DOMContentLoaded', () => {
  initChart();
  setupEventListeners();
  connectWebSocket();
  loadCurrentSettings();
  loadHistoryData('daily');
  loadDeviceConsumption('month');
  loadHardwareHistory('1h');

  // Atualizar histórico de hardware a cada 15 segundos
  setInterval(() => {
    loadHardwareHistory(currentHwTimeframe);
  }, 15000);
});

// Inicialização do Gráfico Chart.js
function initChart() {
  const ctx = document.getElementById('trafficChart').getContext('2d');

  // Gradiente Download (Cyan)
  const gradientDl = ctx.createLinearGradient(0, 0, 0, 280);
  gradientDl.addColorStop(0, 'rgba(0, 240, 255, 0.35)');
  gradientDl.addColorStop(1, 'rgba(0, 240, 255, 0.0)');

  // Gradiente Upload (Violet)
  const gradientUl = ctx.createLinearGradient(0, 0, 0, 280);
  gradientUl.addColorStop(0, 'rgba(168, 85, 247, 0.30)');
  gradientUl.addColorStop(1, 'rgba(168, 85, 247, 0.0)');

  // Preencher pontos iniciais vazios
  for (let i = MAX_CHART_POINTS; i > 0; i--) {
    chartLabels.push('');
    chartDownloadData.push(0);
    chartUploadData.push(0);
  }

  trafficChart = new Chart(ctx, {
    type: 'line',
    data: {
      labels: chartLabels,
      datasets: [
        {
          label: 'Download (Mbps)',
          data: chartDownloadData,
          borderColor: '#00f0ff',
          backgroundColor: gradientDl,
          borderWidth: 2.2,
          fill: true,
          tension: 0.35,
          pointRadius: 0,
          pointHoverRadius: 4,
          pointHoverBackgroundColor: '#00f0ff'
        },
        {
          label: 'Upload (Mbps)',
          data: chartUploadData,
          borderColor: '#a855f7',
          backgroundColor: gradientUl,
          borderWidth: 2.2,
          fill: true,
          tension: 0.35,
          pointRadius: 0,
          pointHoverRadius: 4,
          pointHoverBackgroundColor: '#a855f7'
        }
      ]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      animation: { duration: 400 },
      interaction: {
        intersect: false,
        mode: 'index'
      },
      plugins: {
        legend: { display: false },
        tooltip: {
          backgroundColor: 'rgba(15, 22, 38, 0.9)',
          titleFont: { family: 'Outfit', size: 12 },
          bodyFont: { family: 'JetBrains Mono', size: 12 },
          borderColor: 'rgba(255, 255, 255, 0.1)',
          borderWidth: 1,
          padding: 10,
          callbacks: {
            label: function(context) {
              return `${context.dataset.label}: ${context.parsed.y.toFixed(2)} Mbps`;
            }
          }
        }
      },
      scales: {
        x: {
          grid: { display: false },
          ticks: { display: false }
        },
        y: {
          min: 0,
          grid: {
            color: 'rgba(255, 255, 255, 0.05)'
          },
          ticks: {
            color: '#64748b',
            font: { family: 'JetBrains Mono', size: 11 },
            callback: function(value) {
              return value + ' Mbps';
            }
          }
        }
      }
    }
  });
}

// Atualizar Gráfico com novo dado
function pushChartData(dlMbps, ulMbps) {
  if (isChartPaused || !trafficChart) return;

  const now = new Date();
  const timeStr = `${String(now.getHours()).padStart(2, '0')}:${String(now.getMinutes()).padStart(2, '0')}:${String(now.getSeconds()).padStart(2, '0')}`;

  chartLabels.push(timeStr);
  chartDownloadData.push(dlMbps);
  chartUploadData.push(ulMbps);

  if (chartLabels.length > MAX_CHART_POINTS) {
    chartLabels.shift();
    chartDownloadData.shift();
    chartUploadData.shift();
  }

  trafficChart.update('none'); // Update suave sem redesenho abrupto
}

// Conexão WebSocket para streaming em tempo real
function connectWebSocket() {
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
  const wsUrl = `${protocol}//${window.location.host}/ws/live`;

  try {
    ws = new WebSocket(wsUrl);

    ws.onopen = () => {
      console.log('WebSocket conectado com sucesso.');
      if (pollFallbackTimer) {
        clearInterval(pollFallbackTimer);
        pollFallbackTimer = null;
      }
    };

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        updateDashboard(data);
      } catch (err) {
        console.error('Erro ao processar dados recebidos do WebSocket:', err);
      }
    };

    ws.onclose = () => {
      console.warn('WebSocket desconectado. Tentando reconectar em 3 segundos...');
      startFallbackPolling();
      setTimeout(connectWebSocket, 3000);
    };

    ws.onerror = (err) => {
      console.error('Erro no WebSocket:', err);
      ws.close();
    };
  } catch (e) {
    startFallbackPolling();
  }
}

// Fallback HTTP caso o WebSocket falhe
function startFallbackPolling() {
  if (!pollFallbackTimer) {
    pollFallbackTimer = setInterval(async () => {
      try {
        const res = await fetch('/api/status');
        if (res.ok) {
          const data = await res.json();
          updateDashboard(data);
        }
      } catch (e) {
        console.warn('Erro na consulta HTTP de status:', e);
      }
    }, 2500);
  }
}

// Atualização de todos os componentes da UI com os dados do MikroTik
function updateDashboard(data) {
  if (!data) return;

  // 1. Status Pill & Demo Banner
  const statusPill = document.getElementById('connection-status-pill');
  const statusLabel = document.getElementById('connection-status-label');
  const demoBanner = document.getElementById('demo-banner');
  const demoBannerText = document.getElementById('demo-banner-text');

  if (data.mode === 'demo') {
    statusPill.className = 'status-pill mode-demo';
    statusLabel.textContent = 'Modo Simulação (Demo)';
    demoBanner.classList.remove('hidden');
    demoBannerText.innerHTML = 'Você está no <strong>Modo Simulação</strong> com dados realistas. Clique em <em>Conexão</em> para apontar para o seu roteador MikroTik.';
  } else if (data.mode === 'fallback') {
    statusPill.className = 'status-pill mode-error';
    statusLabel.textContent = 'Roteador Inacessível';
    demoBanner.classList.remove('hidden');
    demoBannerText.innerHTML = `<strong>Atenção:</strong> Não foi possível conectar ao MikroTik (${data.error || 'Verifique IP e porta'}). Exibindo dados simulados.`;
  } else {
    statusPill.className = 'status-pill';
    statusLabel.textContent = 'MikroTik Conectado';
    demoBanner.classList.add('hidden');
  }

  // 2. Sistema & Hardware
  const sys = data.system || {};
  document.getElementById('top-board-name').textContent = sys.board_name || 'MikroTik RouterBOARD';
  document.getElementById('top-uptime').textContent = sys.uptime || '--';
  document.getElementById('top-routeros-version').textContent = sys.version || 'v7';

  document.getElementById('spec-identity').textContent = sys.identity || 'MikroTik';
  document.getElementById('spec-model').textContent = sys.model || sys.board_name || 'RouterBOARD';
  document.getElementById('spec-firmware').textContent = sys.version || 'RouterOS v7';
  document.getElementById('spec-cpu').textContent = `${sys.cpu_count || 1} Core(s) @ ${sys.cpu_frequency || 'N/A'}`;
  document.getElementById('spec-arch').textContent = sys.architecture || 'arm / mips';
  document.getElementById('spec-temp').textContent = sys.temperature ? `${sys.temperature.toFixed(1)} °C` : 'Normal';

  // 3. KPIs
  const traffic = data.traffic || {};
  const dlMbps = traffic.rx_mbps || 0;
  const ulMbps = traffic.tx_mbps || 0;

  document.getElementById('kpi-download-val').textContent = dlMbps.toFixed(1);
  document.getElementById('kpi-upload-val').textContent = ulMbps.toFixed(1);
  document.getElementById('kpi-total-rx').textContent = `${traffic.total_rx_gb || 0} GB`;
  document.getElementById('kpi-total-tx').textContent = `${traffic.total_tx_gb || 0} GB`;
  document.getElementById('active-interface-label').textContent = traffic.wan_interface || 'ether1';

  // Barras de preenchimento dos KPIs
  document.getElementById('meter-dl').style.width = `${Math.min(100, (dlMbps / 200) * 100)}%`;
  document.getElementById('meter-ul').style.width = `${Math.min(100, (ulMbps / 60) * 100)}%`;

  // CPU
  const cpuLoad = sys.cpu_load || 0;
  document.getElementById('kpi-cpu-val').textContent = cpuLoad;
  document.getElementById('meter-cpu').style.width = `${cpuLoad}%`;
  document.getElementById('kpi-cpu-cores').textContent = `${sys.cpu_count || 1} Cores @ ${sys.cpu_frequency || '1400MHz'}`;

  // RAM
  const memPct = sys.memory_usage_pct || 0;
  document.getElementById('kpi-ram-val').textContent = Math.round(memPct);
  document.getElementById('meter-ram').style.width = `${memPct}%`;
  const freeMb = sys.free_memory ? Math.round(sys.free_memory / (1024 * 1024)) : 0;
  document.getElementById('kpi-ram-detail').textContent = `${freeMb} MB livre`;

  // WAN & Latência
  const wan = data.wan_info || {};
  document.getElementById('kpi-wan-ip').textContent = wan.ip || '--';
  document.getElementById('spec-gateway').textContent = wan.gateway || '--';
  if (wan.ping_latency_ms) {
    document.getElementById('kpi-latency-val').textContent = wan.ping_latency_ms;
  }

  // Atualizar Gráfico
  pushChartData(dlMbps, ulMbps);

  // 4. Interfaces
  renderInterfaces(data.interfaces || []);

  // 5. Dispositivos Conectados
  allDevices = data.devices || [];
  document.getElementById('kpi-devices-count').textContent = allDevices.length;
  renderDevicesTable();

  // 6. Logs do Sistema
  renderLogs(data.logs || []);
}

// Renderizar Grade de Interfaces
function renderInterfaces(interfaces) {
  const container = document.getElementById('interfaces-container');
  document.getElementById('interfaces-count-badge').textContent = `${interfaces.length} Interfaces`;

  container.innerHTML = interfaces.map(iface => {
    const isUp = iface.running === 'true' || iface.running === true;
    const statusClass = isUp ? 'up' : 'down';
    const statusText = isUp ? 'Conectado' : 'Inativo';
    const rxKbps = ((iface.rate_rx_bps || 0) / 1000).toFixed(1);
    const txKbps = ((iface.rate_tx_bps || 0) / 1000).toFixed(1);

    return `
      <div class="interface-card">
        <div class="iface-top">
          <div class="iface-name-group">
            <svg class="iface-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <rect x="2" y="2" width="20" height="8" rx="2" ry="2"></rect>
              <rect x="2" y="14" width="20" height="8" rx="2" ry="2"></rect>
              <line x1="6" y1="6" x2="6.01" y2="6"></line>
              <line x1="6" y1="18" x2="6.01" y2="18"></line>
            </svg>
            <span class="iface-name">${iface.name}</span>
          </div>
          <span class="iface-status-pill ${statusClass}">${statusText}</span>
        </div>
        <div class="iface-comment" title="${iface.comment || ''}">${iface.comment || 'Porta de Rede Ethernet'}</div>
        <div class="iface-rates">
          <div class="rate-item rate-rx" title="Download Atual">
            <span>↓</span>
            <span>${rxKbps} Kbps</span>
          </div>
          <div class="rate-item rate-tx" title="Upload Atual">
            <span>↑</span>
            <span>${txKbps} Kbps</span>
          </div>
        </div>
      </div>
    `;
  }).join('');
}

// Ícones por tipo de dispositivo
function getDeviceSvg(type) {
  switch (type) {
    case 'mobile':
      return `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="5" y="2" width="14" height="20" rx="2" ry="2"></rect><line x1="12" y1="18" x2="12.01" y2="18"></line></svg>`;
    case 'laptop':
      return `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="2" y="3" width="20" height="14" rx="2" ry="2"></rect><line x1="2" y1="20" x2="22" y2="20"></line></svg>`;
    case 'tv':
      return `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="2" y="7" width="20" height="15" rx="2" ry="2"></rect><polyline points="17 2 12 7 7 2"></polyline></svg>`;
    case 'game':
      return `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="6" y1="12" x2="10" y2="12"></line><line x1="8" y1="10" x2="8" y2="14"></line><line x1="15" y1="13" x2="15.01" y2="13"></line><line x1="18" y1="11" x2="18.01" y2="11"></line><rect x="2" y="6" width="20" height="12" rx="6"></rect></svg>`;
    case 'camera':
      return `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M23 19a2 2 0 0 1-2 2H3a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h4l2-3h6l2 3h4a2 2 0 0 1 2 2z"></path><circle cx="12" cy="13" r="4"></circle></svg>`;
    case 'nas':
      return `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="2" y="2" width="20" height="8" rx="2" ry="2"></rect><rect x="2" y="14" width="20" height="8" rx="2" ry="2"></rect><line x1="6" y1="6" x2="6.01" y2="6"></line><line x1="6" y1="18" x2="6.01" y2="18"></line></svg>`;
    case 'iot':
      return `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M9 18h6"></path><path d="M10 22h4"></path><path d="M15.09 14c.18-.98.65-1.74 1.41-2.5A4.65 4.65 0 0 0 18 8 6 6 0 0 0 6 8c0 1 .23 2.23 1.5 3.5A4.61 4.61 0 0 1 8.91 14"></path></svg>`;
    default:
      return `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="2" y="3" width="20" height="14" rx="2" ry="2"></rect><line x1="8" y1="21" x2="16" y2="21"></line><line x1="12" y1="17" x2="12" y2="21"></line></svg>`;
  }
}

// Renderizar Tabela de Dispositivos com Filtros e Busca
function renderDevicesTable() {
  const tbody = document.getElementById('devices-tbody');
  const countAll = document.getElementById('filter-count-all');
  if (countAll) countAll.textContent = allDevices.length;

  const filtered = allDevices.filter(dev => {
    // Filtro por Categoria
    if (currentDeviceFilter !== 'all') {
      if (currentDeviceFilter === 'pc' && !['pc', 'laptop'].includes(dev.type)) return false;
      if (currentDeviceFilter === 'mobile' && dev.type !== 'mobile') return false;
      if (currentDeviceFilter === 'tv' && !['tv', 'game'].includes(dev.type)) return false;
      if (currentDeviceFilter === 'iot' && !['iot', 'camera', 'nas'].includes(dev.type)) return false;
    }

    // Busca textual
    if (currentSearchTerm) {
      const q = currentSearchTerm.toLowerCase();
      const hn = (dev.hostname || '').toLowerCase();
      const ip = (dev.address || '').toLowerCase();
      const mac = (dev['mac-address'] || '').toLowerCase();
      const comment = (dev.comment || '').toLowerCase();
      return hn.includes(q) || ip.includes(q) || mac.includes(q) || comment.includes(q);
    }
    return true;
  });

  if (filtered.length === 0) {
    tbody.innerHTML = `
      <tr>
        <td colspan="7" style="text-align: center; color: var(--text-muted); padding: 30px;">
          Nenhum dispositivo encontrado com o filtro selecionado.
        </td>
      </tr>
    `;
    return;
  }

  tbody.innerHTML = filtered.map(dev => {
    const isDynamic = dev.dynamic === 'true' || dev.dynamic === true;
    const statusBadge = isDynamic
      ? `<span class="status-badge badge-active">Dinâmico (DHCP)</span>`
      : `<span class="status-badge badge-static">Estático</span>`;

    return `
      <tr>
        <td>
          <div class="device-cell">
            <div class="device-avatar">
              ${getDeviceSvg(dev.type)}
            </div>
            <div>
              <span class="device-title">${escapeHtml(dev.hostname || 'Dispositivo')}</span>
              <span class="device-vendor">${escapeHtml(dev.vendor || dev.comment || 'Rede Local')}</span>
            </div>
          </div>
        </td>
        <td><span class="font-mono">${escapeHtml(dev.address)}</span></td>
        <td><span class="font-mono text-muted">${escapeHtml(dev['mac-address'])}</span></td>
        <td><span class="font-mono">${escapeHtml(dev.interface || 'bridge-LAN')}</span></td>
        <td><span class="text-secondary">${escapeHtml(dev.comment || dev.type || '--')}</span></td>
        <td>${statusBadge}</td>
        <td>
          <button class="btn btn-sm btn-glass" onclick="triggerPing('${dev.address}')" title="Testar Latência para ${dev.address}">
            Ping
          </button>
        </td>
      </tr>
    `;
  }).join('');
}

// Renderizar Logs
function renderLogs(logs) {
  const container = document.getElementById('logs-container');
  if (!logs || logs.length === 0) return;

  container.innerHTML = logs.map(log => {
    let typeClass = '';
    const topics = (log.topics || '').toLowerCase();
    if (topics.includes('warning')) typeClass = 'warning';
    else if (topics.includes('error')) typeClass = 'error';
    else if (topics.includes('firewall')) typeClass = 'firewall';

    return `
      <div class="log-entry ${typeClass}">
        <span class="log-time">${escapeHtml(log.time)}</span>
        <span class="log-topic">${escapeHtml(log.topics)}</span>
        <span class="log-msg">${escapeHtml(log.message)}</span>
      </div>
    `;
  }).join('');
}

// Event Listeners
function setupEventListeners() {
  // Modal openers
  document.getElementById('btn-open-settings').addEventListener('click', () => openModal('settings-modal'));
  document.getElementById('btn-open-ping').addEventListener('click', () => openModal('ping-modal'));
  document.getElementById('btn-open-guide').addEventListener('click', () => openModal('guide-modal'));

  // Pause chart button
  const btnPause = document.getElementById('btn-toggle-pause');
  btnPause.addEventListener('click', () => {
    isChartPaused = !isChartPaused;
    btnPause.textContent = isChartPaused ? 'Retomar' : 'Pausar';
    btnPause.classList.toggle('btn-primary', isChartPaused);
  });

  // Device search
  document.getElementById('device-search-input').addEventListener('input', (e) => {
    currentSearchTerm = e.target.value.trim();
    renderDevicesTable();
  });

  // Device filters
  document.querySelectorAll('.filter-pills-row .pill-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      document.querySelectorAll('.filter-pills-row .pill-btn').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      currentDeviceFilter = btn.dataset.filter;
      renderDevicesTable();
    });
  });

  // Settings form submit
  document.getElementById('settings-form').addEventListener('submit', async (e) => {
    e.preventDefault();
    await saveSettings();
  });

  // Test connection button
  document.getElementById('btn-test-connection').addEventListener('click', async () => {
    await testConnection();
  });

  // Ping tool run
  document.getElementById('btn-run-ping').addEventListener('click', () => {
    const target = document.getElementById('ping-target-input').value.trim();
    if (target) runPingDiagnostic(target);
  });

  // Clear logs view button
  document.getElementById('btn-clear-logs-view').addEventListener('click', () => {
    document.getElementById('logs-container').innerHTML = '<div style="color: var(--text-muted); padding: 10px;">Visualização de logs limpa. Novos eventos aparecerão automaticamente.</div>';
  });

  // Toggle de período do Histórico (Diário vs Mensal)
  const btnDaily = document.getElementById('btn-hist-daily');
  const btnMonthly = document.getElementById('btn-hist-monthly');
  if (btnDaily && btnMonthly) {
    btnDaily.addEventListener('click', () => {
      btnDaily.classList.add('active');
      btnMonthly.classList.remove('active');
      currentHistoryPeriod = 'daily';
      loadHistoryData('daily');
    });

    btnMonthly.addEventListener('click', () => {
      btnMonthly.classList.add('active');
      btnDaily.classList.remove('active');
      currentHistoryPeriod = 'monthly';
      loadHistoryData('monthly');
    });
  }

  // Filtros de período do Ranking (Hoje, 7 Dias, Mês)
  document.querySelectorAll('.ranking-period-filters .rank-filter-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      document.querySelectorAll('.ranking-period-filters .rank-filter-btn').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      currentRankPeriod = btn.dataset.period;
      loadDeviceConsumption(currentRankPeriod);
    });
  });

  // Botão Zerar Histórico
  const btnClearHistory = document.getElementById('btn-clear-history');
  if (btnClearHistory) {
    btnClearHistory.addEventListener('click', async () => {
      if (!confirm('Deseja realmente limpar todo o histórico e iniciar o registro a partir de hoje?')) {
        return;
      }
      try {
        btnClearHistory.disabled = true;
        btnClearHistory.textContent = 'Limpando...';
        const res = await fetch('/api/history/clear', { method: 'POST' });
        if (res.ok) {
          await loadHistoryData(currentHistoryPeriod);
          await loadDeviceConsumption(currentRankPeriod);
        }
      } catch (err) {
        console.error('Erro ao limpar histórico:', err);
      } finally {
        btnClearHistory.disabled = false;
        btnClearHistory.innerHTML = `
          <svg class="btn-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M3 6h18"></path>
            <path d="M19 6v14c0 1-1 2-2 2H7c-1 0-2-1-2-2V6"></path>
            <path d="M8 6V4c0-1 1-2 2-2h4c1 0 2 1 2 2v2"></path>
          </svg>
          <span>Zerar Histórico</span>
        `;
      }
    });
  }

  // Alternância de métricas de hardware (CPU/RAM vs Temp/Voltagem)
  const btnHwCpu = document.getElementById('btn-hw-metric-cpu');
  const btnHwTemp = document.getElementById('btn-hw-metric-temp');
  if (btnHwCpu && btnHwTemp) {
    btnHwCpu.addEventListener('click', () => {
      btnHwCpu.classList.add('active');
      btnHwTemp.classList.remove('active');
      currentHwMetric = 'cpu_ram';
      renderHardwareHistoryChart();
    });

    btnHwTemp.addEventListener('click', () => {
      btnHwTemp.classList.add('active');
      btnHwCpu.classList.remove('active');
      currentHwMetric = 'temp_volt';
      renderHardwareHistoryChart();
    });
  }

  // Timeframe de histórico de hardware (1h, 6h, 24h)
  document.querySelectorAll('.hw-timeframe-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      document.querySelectorAll('.hw-timeframe-btn').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      currentHwTimeframe = btn.dataset.timeframe;
      loadHardwareHistory(currentHwTimeframe);
    });
  });

  // Botão Testar Telegram
  const btnTestTg = document.getElementById('btn-test-telegram');
  if (btnTestTg) {
    btnTestTg.addEventListener('click', async () => {
      const fb = document.getElementById('telegram-test-feedback');
      btnTestTg.disabled = true;
      btnTestTg.textContent = 'Enviando...';
      fb.classList.add('hidden');

      const payload = {
        bot_token: document.getElementById('cfg-tg-token').value.trim(),
        chat_id: document.getElementById('cfg-tg-chat-id').value.trim()
      };

      try {
        const res = await fetch('/api/telegram/test', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload)
        });
        const data = await res.json();
        fb.classList.remove('hidden');
        if (data.success) {
          fb.className = 'test-feedback-box success';
          fb.innerHTML = `<strong>Sucesso!</strong> Notificação de teste enviada para o seu Telegram.`;
        } else {
          fb.className = 'test-feedback-box error';
          fb.innerHTML = `<strong>Falha:</strong> ${escapeHtml(data.error || 'Verifique o Token e Chat ID')}`;
        }
      } catch (err) {
        fb.classList.remove('hidden');
        fb.className = 'test-feedback-box error';
        fb.textContent = 'Erro ao enviar teste: ' + err.message;
      } finally {
        btnTestTg.disabled = false;
        btnTestTg.innerHTML = `
          <svg class="btn-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <line x1="22" y1="2" x2="11" y2="13"></line>
            <polygon points="22 2 15 22 11 13 2 9 22 2"></polygon>
          </svg>
          <span>Enviar Teste no Telegram</span>
        `;
      }
    });
  }
}

// Modal management
function openModal(id) {
  const el = document.getElementById(id);
  if (el) el.classList.remove('hidden');
}

function closeModal(id) {
  const el = document.getElementById(id);
  if (el) el.classList.add('hidden');
}

// Carregar Configurações Atuais no Form
async function loadCurrentSettings() {
  try {
    const res = await fetch('/api/config');
    if (!res.ok) return;
    const cfg = await res.json();

    document.getElementById('cfg-router-ip').value = cfg.router_ip || '';
    document.getElementById('cfg-port').value = cfg.port || 80;
    document.getElementById('cfg-username').value = cfg.username || '';
    document.getElementById('cfg-wan-interface').value = cfg.wan_interface || 'ether1';
    document.getElementById('cfg-poll-interval').value = cfg.poll_interval || 2.0;
    document.getElementById('cfg-use-https').checked = !!cfg.use_https;
    document.getElementById('cfg-verify-ssl').checked = !!cfg.verify_ssl;
    document.getElementById('cfg-demo-mode').checked = !!cfg.demo_mode;
    if (cfg.password) {
      document.getElementById('cfg-password').value = cfg.password;
    }

    // Telegram
    document.getElementById('cfg-tg-enabled').checked = !!cfg.telegram_enabled;
    document.getElementById('cfg-tg-token').value = cfg.telegram_bot_token || '';
    document.getElementById('cfg-tg-chat-id').value = cfg.telegram_chat_id || '';
    document.getElementById('cfg-tg-temp-threshold').value = cfg.telegram_temp_threshold || 60;
    document.getElementById('cfg-tg-notify-wan').checked = cfg.telegram_notify_wan_down !== false;
    document.getElementById('cfg-tg-notify-temp').checked = cfg.telegram_notify_temp_high !== false;
  } catch (e) {
    console.error('Erro ao ler configuração:', e);
  }
}

// Salvar Configurações
async function saveSettings() {
  const saveBtn = document.getElementById('btn-save-settings');
  saveBtn.disabled = true;
  saveBtn.textContent = 'Salvando...';

  const payload = {
    router_ip: document.getElementById('cfg-router-ip').value.trim(),
    port: parseInt(document.getElementById('cfg-port').value) || 80,
    username: document.getElementById('cfg-username').value.trim(),
    password: document.getElementById('cfg-password').value,
    wan_interface: document.getElementById('cfg-wan-interface').value.trim(),
    poll_interval: parseFloat(document.getElementById('cfg-poll-interval').value) || 2.0,
    use_https: document.getElementById('cfg-use-https').checked,
    verify_ssl: document.getElementById('cfg-verify-ssl').checked,
    demo_mode: document.getElementById('cfg-demo-mode').checked,
    telegram_enabled: document.getElementById('cfg-tg-enabled').checked,
    telegram_bot_token: document.getElementById('cfg-tg-token').value.trim(),
    telegram_chat_id: document.getElementById('cfg-tg-chat-id').value.trim(),
    telegram_temp_threshold: parseFloat(document.getElementById('cfg-tg-temp-threshold').value) || 60.0,
    telegram_notify_wan_down: document.getElementById('cfg-tg-notify-wan').checked,
    telegram_notify_temp_high: document.getElementById('cfg-tg-notify-temp').checked
  };

  try {
    const res = await fetch('/api/config', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });
    const data = await res.json();

    const fb = document.getElementById('connection-test-feedback');
    fb.className = 'test-feedback-box success';
    fb.textContent = 'Configurações salvas! Atualizando conexão...';
    fb.classList.remove('hidden');

    setTimeout(() => {
      closeModal('settings-modal');
      fb.classList.add('hidden');
    }, 1200);
  } catch (e) {
    alert('Erro ao salvar: ' + e.message);
  } finally {
    saveBtn.disabled = false;
    saveBtn.textContent = 'Salvar Configurações';
  }
}

// Testar Conexão em tempo real
async function testConnection() {
  const btn = document.getElementById('btn-test-connection');
  const fb = document.getElementById('connection-test-feedback');
  btn.disabled = true;
  btn.textContent = 'Testando...';
  fb.classList.add('hidden');

  const payload = {
    router_ip: document.getElementById('cfg-router-ip').value.trim(),
    port: parseInt(document.getElementById('cfg-port').value) || 80,
    username: document.getElementById('cfg-username').value.trim(),
    password: document.getElementById('cfg-password').value,
    use_https: document.getElementById('cfg-use-https').checked,
    verify_ssl: document.getElementById('cfg-verify-ssl').checked
  };

  try {
    const res = await fetch('/api/test-connection', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });
    const result = await res.json();

    fb.classList.remove('hidden');
    if (result.success) {
      fb.className = 'test-feedback-box success';
      fb.innerHTML = `<strong>Sucesso!</strong> Conectado a <strong>${escapeHtml(result.board_name)}</strong> (RouterOS ${escapeHtml(result.version)}). Uptime: ${escapeHtml(result.uptime)}`;
    } else {
      fb.className = 'test-feedback-box error';
      fb.innerHTML = `<strong>Falha na Conexão:</strong> ${escapeHtml(result.error || 'Erro desconhecido')}`;
    }
  } catch (e) {
    fb.className = 'test-feedback-box error';
    fb.innerHTML = `<strong>Erro:</strong> ${escapeHtml(e.message)}`;
    fb.classList.remove('hidden');
  } finally {
    btn.disabled = false;
    btn.textContent = 'Testar Conexão';
  }
}

// Disparar Diagnóstico de Ping
async function runPingDiagnostic(target) {
  const panel = document.getElementById('ping-results-panel');
  const btn = document.getElementById('btn-run-ping');
  btn.disabled = true;
  btn.textContent = 'Enviando...';

  panel.innerHTML = `<div class="empty-state"><p>Enviando 4 pacotes ICMP para <strong>${escapeHtml(target)}</strong> através do roteador MikroTik...</p></div>`;

  try {
    const res = await fetch('/api/ping', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ address: target, count: 4 })
    });
    const data = await res.json();

    if (data.error) {
      panel.innerHTML = `<div class="test-feedback-box error">Erro ao executar ping: ${escapeHtml(data.error)}</div>`;
      return;
    }

    panel.innerHTML = `
      <div class="ping-summary-grid">
        <div class="ping-stat-card">
          <span class="ping-stat-title">Pacotes Enviados/Recebidos</span>
          <span class="ping-stat-val">${data.packets_sent} / ${data.packets_received}</span>
        </div>
        <div class="ping-stat-card">
          <span class="ping-stat-title">Perda de Pacotes</span>
          <span class="ping-stat-val">${data.packet_loss_pct}%</span>
        </div>
        <div class="ping-stat-card">
          <span class="ping-stat-title">Latência Média</span>
          <span class="ping-stat-val">${data.avg_rtt} ms</span>
        </div>
        <div class="ping-stat-card">
          <span class="ping-stat-title">Mín / Máx RTT</span>
          <span class="ping-stat-val">${data.min_rtt} / ${data.max_rtt} ms</span>
        </div>
      </div>
      <div class="ping-seq-list">
        ${(data.results || []).map(r => `
          <div class="ping-seq-row">
            <span>Sequência #${r.seq}: ${escapeHtml(r.host)}</span>
            <span>Tamanho: ${r.size} bytes</span>
            <span>TTL: ${r.ttl}</span>
            <span style="color: var(--color-cyan); font-weight: 600;">Tempo: ${r.time}</span>
          </div>
        `).join('')}
      </div>
    `;
  } catch (e) {
    panel.innerHTML = `<div class="test-feedback-box error">Falha na requisição: ${escapeHtml(e.message)}</div>`;
  } finally {
    btn.disabled = false;
    btn.textContent = 'Disparar Ping';
  }
}

// Ping para dispositivo individual na tabela
function triggerPing(ip) {
  openModal('ping-modal');
  document.getElementById('ping-target-input').value = ip;
  runPingDiagnostic(ip);
}

function setPingTarget(ip) {
  document.getElementById('ping-target-input').value = ip;
  runPingDiagnostic(ip);
}

// Copiar código do Guia
function copyCode(btn, text) {
  navigator.clipboard.writeText(text).then(() => {
    const orig = btn.textContent;
    btn.textContent = 'Copiado!';
    setTimeout(() => { btn.textContent = orig; }, 1800);
  });
}

function escapeHtml(str) {
  if (!str) return '';
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;');
}

// -------------------------------------------------------------
// HISTÓRICO DE CONSUMO (DIÁRIO E MENSAL)
// -------------------------------------------------------------
async function loadHistoryData(period) {
  try {
    const endpoint = period === 'monthly' ? '/api/history/monthly?months=12' : '/api/history/daily?days=30';
    const res = await fetch(endpoint);
    if (!res.ok) return;
    const data = await res.json();
    renderHistoryChart(data, period);
  } catch (err) {
    console.error('Erro ao carregar dados de histórico:', err);
  }
}

function renderHistoryChart(data, period) {
  const summary = data.summary || {};
  
  // Atualizar KPI Chips do Histórico
  document.getElementById('hist-total-gb').textContent = `${summary.total_gb || 0} GB`;
  document.getElementById('hist-rx-gb').textContent = `${summary.total_rx_gb || 0} GB`;
  document.getElementById('hist-tx-gb').textContent = `${summary.total_tx_gb || 0} GB`;
  
  const avgLabel = document.getElementById('hist-avg-label');
  const avgVal = document.getElementById('hist-avg-gb');
  const peakLabel = document.getElementById('hist-peak-label');
  const peakVal = document.getElementById('hist-peak-val');

  if (period === 'monthly') {
    avgLabel.textContent = 'Média Mensal';
    avgVal.textContent = `${summary.monthly_avg_gb || 0} GB`;
    peakLabel.textContent = 'Mês de Pico';
    peakVal.textContent = `${summary.peak_month || '--'} (${summary.peak_gb || 0} GB)`;
  } else {
    avgLabel.textContent = 'Média Diária';
    avgVal.textContent = `${summary.daily_avg_gb || 0} GB`;
    peakLabel.textContent = 'Dia de Pico';
    peakVal.textContent = `${summary.peak_day || '--'} (${summary.peak_gb || 0} GB)`;
  }

  // Renderizar Chart.js
  const ctx = document.getElementById('historyChart').getContext('2d');
  
  if (historyChart) {
    historyChart.destroy();
  }

  const gradientDl = ctx.createLinearGradient(0, 0, 0, 260);
  gradientDl.addColorStop(0, 'rgba(0, 240, 255, 0.85)');
  gradientDl.addColorStop(1, 'rgba(0, 240, 255, 0.25)');

  const gradientUl = ctx.createLinearGradient(0, 0, 0, 260);
  gradientUl.addColorStop(0, 'rgba(168, 85, 247, 0.85)');
  gradientUl.addColorStop(1, 'rgba(168, 85, 247, 0.25)');

  historyChart = new Chart(ctx, {
    type: 'bar',
    data: {
      labels: data.labels,
      datasets: [
        {
          label: 'Download (GB)',
          data: data.download_gb,
          backgroundColor: gradientDl,
          borderRadius: 4,
          borderSkipped: false,
          maxBarThickness: period === 'monthly' ? 36 : 14,
        },
        {
          label: 'Upload (GB)',
          data: data.upload_gb,
          backgroundColor: gradientUl,
          borderRadius: 4,
          borderSkipped: false,
          maxBarThickness: period === 'monthly' ? 36 : 14,
        }
      ]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: {
          display: true,
          position: 'top',
          align: 'end',
          labels: {
            boxWidth: 12,
            boxHeight: 12,
            color: '#94a3b8',
            font: { family: 'Outfit', size: 12 }
          }
        },
        tooltip: {
          backgroundColor: 'rgba(15, 22, 38, 0.95)',
          titleFont: { family: 'Outfit', size: 13, weight: 'bold' },
          bodyFont: { family: 'JetBrains Mono', size: 12 },
          borderColor: 'rgba(255, 255, 255, 0.12)',
          borderWidth: 1,
          padding: 12,
          callbacks: {
            afterBody: function(tooltipItems) {
              const dl = tooltipItems.find(t => t.datasetIndex === 0)?.parsed.y || 0;
              const ul = tooltipItems.find(t => t.datasetIndex === 1)?.parsed.y || 0;
              const tot = (dl + ul).toFixed(2);
              return `Consumo Total: ${tot} GB`;
            }
          }
        }
      },
      scales: {
        x: {
          grid: { display: false },
          ticks: {
            color: '#94a3b8',
            font: { family: 'JetBrains Mono', size: 11 },
            maxRotation: 0,
            autoSkip: true,
            maxTicksLimit: period === 'monthly' ? 12 : 15
          }
        },
        y: {
          grid: { color: 'rgba(255, 255, 255, 0.05)' },
          ticks: {
            color: '#64748b',
            font: { family: 'JetBrains Mono', size: 11 },
            callback: function(val) { return val + ' GB'; }
          }
        }
      }
    }
  });
}

// -------------------------------------------------------------
// CONSUMO POR DISPOSITIVO & RANKING (LEADERBOARD)
// -------------------------------------------------------------
async function loadDeviceConsumption(period) {
  try {
    const res = await fetch(`/api/consumption/devices?period=${period}`);
    if (!res.ok) return;
    const data = await res.json();
    renderDeviceDonutChart(data.chart, data.total_network_gb);
    renderLeaderboard(data.devices || [], data.total_network_gb);
  } catch (err) {
    console.error('Erro ao carregar ranking de consumo:', err);
  }
}

function renderDeviceDonutChart(chartData, totalNetworkGb) {
  document.getElementById('donut-total-gb').textContent = totalNetworkGb.toFixed(1);

  const ctx = document.getElementById('deviceDonutChart').getContext('2d');
  if (deviceDonutChart) {
    deviceDonutChart.destroy();
  }

  deviceDonutChart = new Chart(ctx, {
    type: 'doughnut',
    data: {
      labels: chartData.labels,
      datasets: [{
        data: chartData.data,
        backgroundColor: chartData.colors,
        borderWidth: 2,
        borderColor: '#0f1626',
        hoverOffset: 6
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      cutout: '72%',
      plugins: {
        legend: { display: false },
        tooltip: {
          backgroundColor: 'rgba(15, 22, 38, 0.95)',
          titleFont: { family: 'Outfit', size: 12 },
          bodyFont: { family: 'JetBrains Mono', size: 12 },
          borderColor: 'rgba(255, 255, 255, 0.12)',
          borderWidth: 1,
          padding: 10,
          callbacks: {
            label: function(ctx) {
              const val = ctx.parsed;
              const pct = totalNetworkGb > 0 ? ((val / totalNetworkGb) * 100).toFixed(1) : 0;
              return `${ctx.label}: ${val} GB (${pct}%)`;
            }
          }
        }
      }
    }
  });

  // Renderizar legenda detalhada
  const legendContainer = document.getElementById('device-shares-legend');
  legendContainer.innerHTML = (chartData.labels || []).slice(0, 5).map((label, i) => {
    const val = chartData.data[i] || 0;
    const pct = totalNetworkGb > 0 ? ((val / totalNetworkGb) * 100).toFixed(1) : 0;
    const color = chartData.colors[i];
    return `
      <div class="legend-share-row">
        <div class="legend-share-left">
          <span class="legend-color-dot" style="background-color: ${color}; box-shadow: 0 0 6px ${color};"></span>
          <span class="legend-dev-name" title="${escapeHtml(label)}">${escapeHtml(label)}</span>
        </div>
        <div class="legend-share-right">
          <span class="legend-gb">${val} GB</span>
          <span class="legend-pct">${pct}%</span>
        </div>
      </div>
    `;
  }).join('');
}

function renderLeaderboard(devices, totalNetworkGb) {
  const container = document.getElementById('leaderboard-list');
  if (!devices || devices.length === 0) {
    container.innerHTML = '<div style="color: var(--text-muted); text-align: center; padding: 20px;">Nenhum registro de consumo no período.</div>';
    return;
  }

  const maxBytes = devices[0]?.total_bytes_raw || ((devices[0]?.total_gb || 0) * 1024 * 1024 * 1024) || 1;

  container.innerHTML = devices.map(dev => {
    let medalClass = '';
    let medalContent = `#${dev.rank}`;
    let itemSpecialClass = '';

    if (dev.rank === 1) {
      medalClass = 'gold-medal';
      medalContent = '🥇';
      itemSpecialClass = 'rank-top-1';
    } else if (dev.rank === 2) {
      medalClass = 'silver-medal';
      medalContent = '🥈';
      itemSpecialClass = 'rank-top-2';
    } else if (dev.rank === 3) {
      medalClass = 'bronze-medal';
      medalContent = '🥉';
      itemSpecialClass = 'rank-top-3';
    }

    // Progresso relativo ao dispositivo líder (Top 1)
    const devBytes = dev.total_bytes_raw || ((dev.total_gb || 0) * 1024 * 1024 * 1024);
    const progressPct = maxBytes > 0 ? Math.min(100, Math.max(devBytes > 0 ? 4 : 0, Math.round((devBytes / maxBytes) * 100))) : 0;
    const displayTotal = dev.formatted_total || `${dev.total_gb} GB`;
    const displayDl = dev.formatted_rx ? `↓ ${dev.formatted_rx}` : `↓ ${dev.download_gb} GB`;
    const displayUl = dev.formatted_tx ? `↑ ${dev.formatted_tx}` : `↑ ${dev.upload_gb} GB`;

    return `
      <div class="leaderboard-item ${itemSpecialClass}">
        <div class="rank-row-main">
          <div class="rank-left">
            <span class="rank-pos-badge ${medalClass}">${medalContent}</span>
            <div class="rank-dev-avatar">
              ${getDeviceSvg(dev.device_type)}
            </div>
            <div class="rank-device-info">
              <span class="rank-dev-name">${escapeHtml(dev.hostname || 'Dispositivo')}</span>
              <div class="rank-dev-sub">
                <span class="font-mono">${escapeHtml(dev.ip_address || dev.mac_address)}</span>
                <span>&bull;</span>
                <span class="text-muted">${escapeHtml(dev.mac_address)}</span>
              </div>
            </div>
          </div>

          <div class="rank-right">
            <div class="rank-metrics-breakdown">
              <span class="rank-stat-dl" title="Download">${displayDl}</span>
              <span class="rank-stat-ul" title="Upload">${displayUl}</span>
            </div>
            <div class="rank-total-badge" title="Consumo Total">
              ${displayTotal}
            </div>
            <span class="rank-percent-pill" title="Participação no Tráfego Total">
              ${dev.percentage}%
            </span>
          </div>
        </div>

        <div class="rank-progress-bg">
          <div class="rank-progress-fill" style="width: ${progressPct}%;"></div>
        </div>
      </div>
    `;
  }).join('');
}

// -------------------------------------------------------------
// HISTÓRICO DE TELEMETRIA DE HARDWARE
// -------------------------------------------------------------
async function loadHardwareHistory(timeframe) {
  try {
    const res = await fetch(`/api/history/hardware?timeframe=${timeframe}`);
    if (!res.ok) return;
    const data = await res.json();
    cachedHwData = data;

    // Atualizar KPI Chips de Hardware
    const summary = data.summary || {};
    document.getElementById('hw-cpu-kpi').textContent = `${summary.avg_cpu || 0}% / ${summary.peak_cpu || 0}%`;
    document.getElementById('hw-ram-kpi').textContent = `${summary.avg_ram || 0}% / ${summary.peak_ram || 0}%`;
    document.getElementById('hw-temp-kpi').textContent = `${summary.avg_temp || 0}°C / ${summary.peak_temp || 0}°C`;
    document.getElementById('hw-volt-kpi').textContent = `${summary.avg_voltage || 0} V`;
    document.getElementById('hw-samples-count').textContent = `${(data.labels || []).length} pontos`;

    renderHardwareHistoryChart();
  } catch (err) {
    console.error('Erro ao carregar telemetria de hardware:', err);
  }
}

function renderHardwareHistoryChart() {
  if (!cachedHwData) return;

  const ctx = document.getElementById('hardwareHistoryChart').getContext('2d');
  if (hardwareHistoryChart) {
    hardwareHistoryChart.destroy();
  }

  const labels = cachedHwData.labels || [];
  let datasets = [];
  let yScales = {};

  if (currentHwMetric === 'cpu_ram') {
    // Gradientes CPU (Amber) e RAM (Cyan)
    const gradCpu = ctx.createLinearGradient(0, 0, 0, 260);
    gradCpu.addColorStop(0, 'rgba(245, 158, 11, 0.35)');
    gradCpu.addColorStop(1, 'rgba(245, 158, 11, 0.0)');

    const gradRam = ctx.createLinearGradient(0, 0, 0, 260);
    gradRam.addColorStop(0, 'rgba(0, 240, 255, 0.30)');
    gradRam.addColorStop(1, 'rgba(0, 240, 255, 0.0)');

    datasets = [
      {
        label: 'Carga de CPU (%)',
        data: cachedHwData.cpu_load || [],
        borderColor: '#f59e0b',
        backgroundColor: gradCpu,
        borderWidth: 2,
        fill: true,
        tension: 0.3,
        pointRadius: labels.length > 30 ? 0 : 2
      },
      {
        label: 'Uso de Memória RAM (%)',
        data: cachedHwData.memory_pct || [],
        borderColor: '#00f0ff',
        backgroundColor: gradRam,
        borderWidth: 2,
        fill: true,
        tension: 0.3,
        pointRadius: labels.length > 30 ? 0 : 2
      }
    ];

    yScales = {
      y: {
        min: 0,
        max: 100,
        grid: { color: 'rgba(255, 255, 255, 0.05)' },
        ticks: {
          color: '#64748b',
          font: { family: 'JetBrains Mono', size: 11 },
          callback: (v) => v + '%'
        }
      }
    };
  } else {
    // Temperatura (°C) e Voltagem (V)
    const gradTemp = ctx.createLinearGradient(0, 0, 0, 260);
    gradTemp.addColorStop(0, 'rgba(244, 63, 94, 0.35)');
    gradTemp.addColorStop(1, 'rgba(244, 63, 94, 0.0)');

    datasets = [
      {
        label: 'Temperatura (°C)',
        data: cachedHwData.temperature || [],
        borderColor: '#f43f5e',
        backgroundColor: gradTemp,
        borderWidth: 2,
        fill: true,
        tension: 0.3,
        yAxisID: 'yTemp',
        pointRadius: labels.length > 30 ? 0 : 2
      },
      {
        label: 'Voltagem (V)',
        data: cachedHwData.voltage || [],
        borderColor: '#10b981',
        borderWidth: 2,
        borderDash: [4, 4],
        fill: false,
        tension: 0.2,
        yAxisID: 'yVolt',
        pointRadius: labels.length > 30 ? 0 : 2
      }
    ];

    yScales = {
      yTemp: {
        type: 'linear',
        position: 'left',
        min: 20,
        max: 80,
        grid: { color: 'rgba(255, 255, 255, 0.05)' },
        ticks: {
          color: '#fb7185',
          font: { family: 'JetBrains Mono', size: 11 },
          callback: (v) => v + '°C'
        }
      },
      yVolt: {
        type: 'linear',
        position: 'right',
        min: 10,
        max: 32,
        grid: { display: false },
        ticks: {
          color: '#34d399',
          font: { family: 'JetBrains Mono', size: 11 },
          callback: (v) => v + 'V'
        }
      }
    };
  }

  hardwareHistoryChart = new Chart(ctx, {
    type: 'line',
    data: {
      labels: labels,
      datasets: datasets
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: {
          display: true,
          position: 'top',
          align: 'end',
          labels: {
            boxWidth: 12,
            boxHeight: 12,
            color: '#94a3b8',
            font: { family: 'Outfit', size: 12 }
          }
        },
        tooltip: {
          backgroundColor: 'rgba(15, 22, 38, 0.95)',
          titleFont: { family: 'Outfit', size: 12, weight: 'bold' },
          bodyFont: { family: 'JetBrains Mono', size: 12 },
          borderColor: 'rgba(255, 255, 255, 0.12)',
          borderWidth: 1,
          padding: 10
        }
      },
      scales: {
        x: {
          grid: { display: false },
          ticks: {
            color: '#94a3b8',
            font: { family: 'JetBrains Mono', size: 10 },
            autoSkip: true,
            maxTicksLimit: 12
          }
        },
        ...yScales
      }
    }
  });
}


