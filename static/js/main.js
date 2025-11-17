// Configuration
const API_BASE = '';
const UPDATE_INTERVAL = 1000; // 1 second

// State
let currentCoin = 'BTC';
let chart = null;
let currentWeights = { upbit: 0, bithumb: 0, coinone: 0 }; // 실시간 가중치 저장
let params = {
    exchange_weights: { upbit: 1.0, bithumb: 1.0, coinone: 1.0 },
    spread_weights: { upbit: 1.0, bithumb: 1.0, coinone: 1.0 },
    volume_weights: { upbit: 1.0, bithumb: 1.0, coinone: 1.0 },
    depth_weights: { upbit: 1.0, bithumb: 1.0, coinone: 1.0 },
    aggregation_method: 'average'
};

// Initialize
document.addEventListener('DOMContentLoaded', () => {
    initializeUI();
    loadParamsFromStorage();
    initializeChart();
    setupEventListeners();
    startPolling();
});

// Initialize UI
function initializeUI() {
    // Initialize exchange weights controls
    initializeWeightControls('exchangeWeights', 'exchange_weights', ['업비트', '빗썸', '코인원'], ['upbit', 'bithumb', 'coinone']);
    initializeWeightControls('spreadWeights', 'spread_weights', ['업비트', '빗썸', '코인원'], ['upbit', 'bithumb', 'coinone']);
    initializeWeightControls('volumeWeights', 'volume_weights', ['업비트', '빗썸', '코인원'], ['upbit', 'bithumb', 'coinone']);
    initializeWeightControls('depthWeights', 'depth_weights', ['업비트', '빗썸', '코인원'], ['upbit', 'bithumb', 'coinone']);
}

function initializeWeightControls(containerId, paramKey, labels, keys) {
    const container = document.getElementById(containerId);
    container.innerHTML = '';
    
    keys.forEach((key, index) => {
        const control = document.createElement('div');
        control.className = 'weight-control';
        control.innerHTML = `
            <label>${labels[index]}</label>
            <div class="weight-control-row">
                <input type="range" 
                       class="weight-slider" 
                       min="0" 
                       max="2" 
                       step="0.01" 
                       value="${params[paramKey][key]}"
                       data-param="${paramKey}"
                       data-key="${key}">
                <input type="number" 
                       class="weight-input" 
                       min="0" 
                       max="2" 
                       step="0.01" 
                       value="${params[paramKey][key]}"
                       data-param="${paramKey}"
                       data-key="${key}">
            </div>
        `;
        container.appendChild(control);
    });
}

// Load params from localStorage
function loadParamsFromStorage() {
    const saved = localStorage.getItem('oracleParams');
    if (saved) {
        try {
            const savedParams = JSON.parse(saved);
            Object.assign(params, savedParams);
            updateUIFromParams();
        } catch (e) {
            console.error('Failed to load params from storage:', e);
        }
    }
}

// Save params to localStorage
function saveParamsToStorage() {
    localStorage.setItem('oracleParams', JSON.stringify(params));
}

// Update UI from params
function updateUIFromParams() {
    // Update aggregation method
    document.querySelector(`input[name="aggregationMethod"][value="${params.aggregation_method}"]`).checked = true;
    
    // Update all weight controls
    document.querySelectorAll('.weight-slider, .weight-input').forEach(input => {
        const param = input.dataset.param;
        const key = input.dataset.key;
        if (params[param] && params[param][key] !== undefined) {
            input.value = params[param][key];
        }
    });
}

// Setup event listeners
function setupEventListeners() {
    // Coin selector
    document.getElementById('coinSelect').addEventListener('change', (e) => {
        currentCoin = e.target.value;
        updateChart();
    });
    
    // Aggregation method
    document.querySelectorAll('input[name="aggregationMethod"]').forEach(radio => {
        radio.addEventListener('change', (e) => {
            params.aggregation_method = e.target.value;
            updateParams();
        });
    });
    
    // Weight controls
    document.querySelectorAll('.weight-slider').forEach(slider => {
        slider.addEventListener('input', (e) => {
            const param = e.target.dataset.param;
            const key = e.target.dataset.key;
            const value = parseFloat(e.target.value);
            params[param][key] = value;
            
            // Sync with input
            const input = document.querySelector(`.weight-input[data-param="${param}"][data-key="${key}"]`);
            if (input) input.value = value;
            
            updateParams();
        });
    });
    
    document.querySelectorAll('.weight-input').forEach(input => {
        input.addEventListener('change', (e) => {
            const param = e.target.dataset.param;
            const key = e.target.dataset.key;
            const value = parseFloat(e.target.value);
            params[param][key] = value;
            
            // Sync with slider
            const slider = document.querySelector(`.weight-slider[data-param="${param}"][data-key="${key}"]`);
            if (slider) slider.value = value;
            
            updateParams();
        });
    });
}

// Initialize Chart.js
function initializeChart() {
    const ctx = document.getElementById('priceChart').getContext('2d');
    
    chart = new Chart(ctx, {
        type: 'line',
        data: {
            labels: [],
            datasets: [
                {
                    label: '집계 가격',
                    data: [],
                    borderColor: '#4a90e2',
                    backgroundColor: 'rgba(74, 144, 226, 0.1)',
                    borderWidth: 2,
                    fill: true,
                    tension: 0.4
                },
                {
                    label: '업비트',
                    data: [],
                    borderColor: '#4a90e2',
                    backgroundColor: 'transparent',
                    borderWidth: 1,
                    borderDash: [5, 5],
                    pointRadius: 0
                },
                {
                    label: '빗썸',
                    data: [],
                    borderColor: '#f39c12',
                    backgroundColor: 'transparent',
                    borderWidth: 1,
                    borderDash: [5, 5],
                    pointRadius: 0
                },
                {
                    label: '코인원',
                    data: [],
                    borderColor: '#27ae60',
                    backgroundColor: 'transparent',
                    borderWidth: 1,
                    borderDash: [5, 5],
                    pointRadius: 0
                }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    display: true,
                    position: 'top'
                },
                tooltip: {
                    mode: 'index',
                    intersect: false
                }
            },
            scales: {
                x: {
                    display: true,
                    title: {
                        display: true,
                        text: '시간'
                    }
                },
                y: {
                    display: true,
                    title: {
                        display: true,
                        text: '가격 (KRW)'
                    }
                }
            },
            interaction: {
                mode: 'nearest',
                axis: 'x',
                intersect: false
            }
        }
    });
}

// Update chart with new data
function updateChart() {
    fetch(`${API_BASE}/api/chart/${currentCoin}`)
        .then(res => res.json())
        .then(data => {
            if (!data || data.length === 0) return;
            
            const labels = data.map(d => {
                const date = new Date(d.timestamp);
                return date.toLocaleTimeString('ko-KR');
            });
            
            const aggregatedPrices = data.map(d => d.price);
            const upbitPrices = data.map(d => d.exchanges?.upbit || null);
            const bithumbPrices = data.map(d => d.exchanges?.bithumb || null);
            const coinonePrices = data.map(d => d.exchanges?.coinone || null);
            
            chart.data.labels = labels;
            chart.data.datasets[0].data = aggregatedPrices;
            chart.data.datasets[1].data = upbitPrices;
            chart.data.datasets[2].data = bithumbPrices;
            chart.data.datasets[3].data = coinonePrices;
            chart.update('none');
        })
        .catch(err => console.error('Chart update error:', err));
}

// Start polling for data
function startPolling() {
    updateData();
    setInterval(updateData, UPDATE_INTERVAL);
    setInterval(updateChart, UPDATE_INTERVAL);
}

// Update data from API
function updateData() {
    // Get aggregated prices
    fetch(`${API_BASE}/api/aggregated`)
        .then(res => res.json())
        .then(data => {
            if (data[currentCoin]) {
                const coinData = data[currentCoin];
                // 가중치 저장
                if (coinData.weights) {
                    currentWeights = coinData.weights;
                }
                updatePriceDisplay(coinData.price, coinData.weights);
            }
        })
        .catch(err => console.error('Aggregated price fetch error:', err));
    
    // Get exchange prices
    fetch(`${API_BASE}/api/prices`)
        .then(res => res.json())
        .then(data => {
            if (data[currentCoin]) {
                updateExchangePrices(data[currentCoin]);
            }
        })
        .catch(err => console.error('Exchange prices fetch error:', err));
}

// Update price display
function updatePriceDisplay(price, weights) {
    const priceElement = document.getElementById('aggregatedPrice');
    const methodElement = document.getElementById('aggregationMethod');
    
    if (price) {
        priceElement.textContent = formatPrice(price);
        const method = params.aggregation_method === 'average' ? '평균값' : '중앙값';
        methodElement.textContent = method;
    } else {
        priceElement.textContent = '-';
    }
}

// Update exchange prices display
function updateExchangePrices(data) {
    const container = document.getElementById('exchangePrices');
    const exchanges = [
        { key: 'upbit', name: '업비트', class: 'upbit' },
        { key: 'bithumb', name: '빗썸', class: 'bithumb' },
        { key: 'coinone', name: '코인원', class: 'coinone' }
    ];
    
    container.innerHTML = exchanges.map(ex => {
        const exchangeData = data[ex.key];
        if (!exchangeData || !exchangeData.price) {
            return `
                <div class="exchange-card ${ex.class}">
                    <div class="exchange-name">${ex.name}</div>
                    <div class="exchange-price">-</div>
                    <div class="exchange-weight">
                        <span class="weight-label">가중치:</span>
                        <span class="weight-value">-</span>
                    </div>
                    <div class="exchange-info">
                        <span><span>스프레드:</span> <span>-</span></span>
                        <span><span>거래량:</span> <span>-</span></span>
                        <span><span>호가 깊이:</span> <span>-</span></span>
                    </div>
                </div>
            `;
        }
        
        const weight = currentWeights[ex.key] || 0;
        const totalWeight = Object.values(currentWeights).reduce((a, b) => a + b, 0);
        const weightPercent = totalWeight > 0 ? ((weight / totalWeight) * 100).toFixed(1) : '0.0';
        
        return `
            <div class="exchange-card ${ex.class}">
                <div class="exchange-name">${ex.name}</div>
                <div class="exchange-price">${formatPrice(exchangeData.price)}</div>
                <div class="exchange-weight">
                    <span class="weight-label">가중치:</span>
                    <span class="weight-value">${formatNumber(weight)}</span>
                    <span class="weight-percent">(${weightPercent}%)</span>
                </div>
                <div class="exchange-info">
                    <span><span>스프레드:</span> <span>${formatNumber(exchangeData.spread)}%</span></span>
                    <span><span>거래량:</span> <span>${formatVolume(exchangeData.volume)}</span></span>
                    <span><span>호가 깊이:</span> <span>${formatNumber(exchangeData.depth)}</span></span>
                </div>
            </div>
        `;
    }).join('');
}

// Update params on server
function updateParams() {
    saveParamsToStorage();
    
    fetch(`${API_BASE}/api/params`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify(params)
    })
    .then(res => res.json())
    .then(data => {
        console.log('Params updated:', data);
    })
    .catch(err => console.error('Params update error:', err));
}

// Format helpers
function formatPrice(price) {
    if (!price) return '-';
    return new Intl.NumberFormat('ko-KR', {
        style: 'currency',
        currency: 'KRW',
        minimumFractionDigits: 0,
        maximumFractionDigits: 0
    }).format(price);
}

function formatNumber(num) {
    if (num === null || num === undefined || num === 'null' || num === 'undefined') return '-';
    if (isNaN(num)) return '-';
    return new Intl.NumberFormat('ko-KR', {
        minimumFractionDigits: 2,
        maximumFractionDigits: 2
    }).format(num);
}

function formatVolume(volume) {
    if (!volume) return '-';
    if (volume >= 1000000000) {
        return (volume / 1000000000).toFixed(2) + 'B';
    } else if (volume >= 1000000) {
        return (volume / 1000000).toFixed(2) + 'M';
    } else if (volume >= 1000) {
        return (volume / 1000).toFixed(2) + 'K';
    }
    return volume.toFixed(2);
}

