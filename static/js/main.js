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
    aggregation_method: 'average',
    price_overrides: { upbit: null, bithumb: null, coinone: null } // 거래소별 가격 오버라이드
};

// Initialize
document.addEventListener('DOMContentLoaded', () => {
    initializeUI();
    loadParamsFromStorage();
    initializeChart();
    initializeExchangeCards(); // 거래소 카드 초기화 (한 번만 생성)
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

// Initialize exchange cards (한 번만 실행)
function initializeExchangeCards() {
    const container = document.getElementById('exchangePrices');
    const exchanges = [
        { key: 'upbit', name: '업비트', class: 'upbit' },
        { key: 'bithumb', name: '빗썸', class: 'bithumb' },
        { key: 'coinone', name: '코인원', class: 'coinone' }
    ];
    
    container.innerHTML = exchanges.map(ex => {
        const exchangeWeight = params.exchange_weights[ex.key] || 1.0;
        const spreadWeight = params.spread_weights[ex.key] || 1.0;
        const volumeWeight = params.volume_weights[ex.key] || 1.0;
        const depthWeight = params.depth_weights[ex.key] || 1.0;
        const priceOverride = params.price_overrides[ex.key];
        const isPriceOverridden = priceOverride !== null && priceOverride !== undefined;
        
        return `
            <div class="exchange-card ${ex.class}" id="exchange-card-${ex.key}">
                <div class="exchange-display" id="exchange-display-${ex.key}">
                    <div class="exchange-header">
                        <div>
                            <div class="exchange-name">${ex.name}</div>
                            <div class="exchange-price" id="exchange-price-${ex.key}">
                                <span id="price-value-${ex.key}">-</span>
                                <span id="price-badge-${ex.key}" class="override-badge" style="display: none;">수동</span>
                            </div>
                            <div class="exchange-weight">
                                <span class="weight-label">가중치:</span>
                                <span class="weight-value" id="weight-value-${ex.key}">-</span>
                                <span class="weight-percent" id="weight-percent-${ex.key}"></span>
                            </div>
                        </div>
                    </div>
                    <div class="exchange-info" id="exchange-info-${ex.key}">
                        <span><span>스프레드:</span> <span id="spread-${ex.key}">-</span></span>
                        <span><span>거래량:</span> <span id="volume-${ex.key}">-</span></span>
                        <span><span>호가 깊이:</span> <span id="depth-${ex.key}">-</span></span>
                    </div>
                </div>
                <div class="exchange-params" id="params-${ex.key}">
                    <div class="exchange-param-control">
                        <label>가격 오버라이드</label>
                        <div class="price-override-control">
                            <input type="number" 
                                   class="price-override-input" 
                                   data-exchange="${ex.key}"
                                   id="price-override-input-${ex.key}"
                                   placeholder="자동"
                                   value="${priceOverride !== null && priceOverride !== undefined ? priceOverride : ''}"
                                   step="1"
                                   onchange="updatePriceOverride('${ex.key}', this.value)"
                                   oninput="updatePriceOverrideInput('${ex.key}', this.value)">
                            <button class="clear-override-btn" 
                                    onclick="clearPriceOverride('${ex.key}')"
                                    ${isPriceOverridden ? '' : 'style="display: none;"'}
                                    id="clearBtn-${ex.key}">
                                초기화
                            </button>
                        </div>
                        <div class="price-override-hint">
                            <small>값을 입력하면 해당 가격으로 고정됩니다. 비우면 자동으로 복원됩니다.</small>
                        </div>
                    </div>
                    <div class="exchange-param-control">
                        <label>거래소 가중치</label>
                        <div class="weight-control-row">
                            <input type="range" 
                                   class="weight-slider" 
                                   min="0" 
                                   max="2" 
                                   step="0.01" 
                                   value="${exchangeWeight}"
                                   data-param="exchange_weights"
                                   data-key="${ex.key}"
                                   oninput="updateExchangeParam('${ex.key}', 'exchange_weights', this.value)">
                            <input type="number" 
                                   class="weight-input" 
                                   min="0" 
                                   max="2" 
                                   step="0.01" 
                                   value="${exchangeWeight}"
                                   data-param="exchange_weights"
                                   data-key="${ex.key}"
                                   onchange="updateExchangeParam('${ex.key}', 'exchange_weights', this.value)">
                        </div>
                    </div>
                    <div class="exchange-param-control">
                        <label>스프레드 가중치 계수</label>
                        <div class="weight-control-row">
                            <input type="range" 
                                   class="weight-slider" 
                                   min="0" 
                                   max="2" 
                                   step="0.01" 
                                   value="${spreadWeight}"
                                   data-param="spread_weights"
                                   data-key="${ex.key}"
                                   oninput="updateExchangeParam('${ex.key}', 'spread_weights', this.value)">
                            <input type="number" 
                                   class="weight-input" 
                                   min="0" 
                                   max="2" 
                                   step="0.01" 
                                   value="${spreadWeight}"
                                   data-param="spread_weights"
                                   data-key="${ex.key}"
                                   onchange="updateExchangeParam('${ex.key}', 'spread_weights', this.value)">
                        </div>
                    </div>
                    <div class="exchange-param-control">
                        <label>거래량 가중치 계수</label>
                        <div class="weight-control-row">
                            <input type="range" 
                                   class="weight-slider" 
                                   min="0" 
                                   max="2" 
                                   step="0.01" 
                                   value="${volumeWeight}"
                                   data-param="volume_weights"
                                   data-key="${ex.key}"
                                   oninput="updateExchangeParam('${ex.key}', 'volume_weights', this.value)">
                            <input type="number" 
                                   class="weight-input" 
                                   min="0" 
                                   max="2" 
                                   step="0.01" 
                                   value="${volumeWeight}"
                                   data-param="volume_weights"
                                   data-key="${ex.key}"
                                   onchange="updateExchangeParam('${ex.key}', 'volume_weights', this.value)">
                        </div>
                    </div>
                    <div class="exchange-param-control">
                        <label>호가 깊이 가중치 계수</label>
                        <div class="weight-control-row">
                            <input type="range" 
                                   class="weight-slider" 
                                   min="0" 
                                   max="2" 
                                   step="0.01" 
                                   value="${depthWeight}"
                                   data-param="depth_weights"
                                   data-key="${ex.key}"
                                   oninput="updateExchangeParam('${ex.key}', 'depth_weights', this.value)">
                            <input type="number" 
                                   class="weight-input" 
                                   min="0" 
                                   max="2" 
                                   step="0.01" 
                                   value="${depthWeight}"
                                   data-param="depth_weights"
                                   data-key="${ex.key}"
                                   onchange="updateExchangeParam('${ex.key}', 'depth_weights', this.value)">
                        </div>
                    </div>
                </div>
            </div>
        `;
    }).join('');
}

// Update exchange prices display (가격 표시 부분만 업데이트)
function updateExchangePrices(data) {
    const exchanges = [
        { key: 'upbit', name: '업비트', class: 'upbit' },
        { key: 'bithumb', name: '빗썸', class: 'bithumb' },
        { key: 'coinone', name: '코인원', class: 'coinone' }
    ];
    
    exchanges.forEach(ex => {
        const exchangeData = data[ex.key];
        const priceEl = document.getElementById(`price-value-${ex.key}`);
        const priceBadgeEl = document.getElementById(`price-badge-${ex.key}`);
        const priceContainerEl = document.getElementById(`exchange-price-${ex.key}`);
        const weightValueEl = document.getElementById(`weight-value-${ex.key}`);
        const weightPercentEl = document.getElementById(`weight-percent-${ex.key}`);
        const spreadEl = document.getElementById(`spread-${ex.key}`);
        const volumeEl = document.getElementById(`volume-${ex.key}`);
        const depthEl = document.getElementById(`depth-${ex.key}`);
        const priceOverrideInput = document.getElementById(`price-override-input-${ex.key}`);
        
        if (!priceEl || !priceContainerEl) return; // 카드가 아직 초기화되지 않음
        
        // 가격 오버라이드 값 읽기 (입력 중인 값 유지)
        if (priceOverrideInput) {
            const currentValue = priceOverrideInput.value.trim();
            if (currentValue !== '') {
                const numValue = parseFloat(currentValue);
                if (!isNaN(numValue)) {
                    params.price_overrides[ex.key] = numValue;
                }
            }
        }
        
        const priceOverride = params.price_overrides[ex.key];
        const isPriceOverridden = priceOverride !== null && priceOverride !== undefined;
        
        if (!exchangeData || !exchangeData.price) {
            // 데이터가 없는 경우
            const displayPrice = isPriceOverridden ? priceOverride : null;
            if (priceEl) {
                priceEl.textContent = displayPrice ? formatPrice(displayPrice) : '-';
            }
            if (priceContainerEl) {
                priceContainerEl.classList.toggle('price-overridden', isPriceOverridden);
            }
            if (priceBadgeEl) {
                priceBadgeEl.style.display = isPriceOverridden ? 'inline' : 'none';
            }
            if (weightValueEl) weightValueEl.textContent = '-';
            if (weightPercentEl) weightPercentEl.textContent = '';
            if (spreadEl) spreadEl.textContent = '-';
            if (volumeEl) volumeEl.textContent = '-';
            if (depthEl) depthEl.textContent = '-';
            
            // placeholder 업데이트
            if (priceOverrideInput) {
                priceOverrideInput.placeholder = '자동';
            }
        } else {
            // 데이터가 있는 경우
            const weight = currentWeights[ex.key] || 0;
            const totalWeight = Object.values(currentWeights).reduce((a, b) => a + b, 0);
            const weightPercent = totalWeight > 0 ? ((weight / totalWeight) * 100).toFixed(1) : '0.0';
            
            const displayPrice = isPriceOverridden ? priceOverride : exchangeData.price;
            
            // 가격 업데이트
            if (priceEl) {
                priceEl.textContent = formatPrice(displayPrice);
            }
            if (priceContainerEl) {
                priceContainerEl.classList.toggle('price-overridden', isPriceOverridden);
            }
            if (priceBadgeEl) {
                priceBadgeEl.style.display = isPriceOverridden ? 'inline' : 'none';
            }
            
            // 가중치 업데이트
            if (weightValueEl) {
                weightValueEl.textContent = formatNumber(weight);
            }
            if (weightPercentEl) {
                weightPercentEl.textContent = `(${weightPercent}%)`;
            }
            
            // 정보 업데이트
            if (spreadEl) spreadEl.textContent = `${formatNumber(exchangeData.spread)}%`;
            if (volumeEl) volumeEl.textContent = formatVolume(exchangeData.volume);
            if (depthEl) depthEl.textContent = formatNumber(exchangeData.depth);
            
            // placeholder 업데이트
            if (priceOverrideInput) {
                priceOverrideInput.placeholder = `자동 (${formatPrice(exchangeData.price)})`;
            }
        }
    });
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

// Update price override input (while typing)
function updatePriceOverrideInput(exchangeKey, value) {
    // 입력 중인 값을 임시로 저장 (업데이트 시 유지)
    if (value === '' || value === null) {
        // 빈 값이면 null로 설정하지 않고, 사용자가 입력 중일 수 있으므로 현재 값을 유지
        return;
    }
    const numValue = parseFloat(value);
    if (!isNaN(numValue)) {
        params.price_overrides[exchangeKey] = numValue;
    }
}

// Update price override (on change/blur)
function updatePriceOverride(exchangeKey, value) {
    const numValue = value === '' || value === null ? null : parseFloat(value);
    params.price_overrides[exchangeKey] = numValue;
    
    // Clear button 표시/숨김
    const clearBtn = document.getElementById(`clearBtn-${exchangeKey}`);
    if (clearBtn) {
        clearBtn.style.display = numValue !== null ? 'block' : 'none';
    }
    
    // 가격 표시 업데이트
    updateParams();
    updateData(); // 즉시 업데이트
}

// Clear price override
function clearPriceOverride(exchangeKey) {
    params.price_overrides[exchangeKey] = null;
    
    // Input 필드 초기화
    const input = document.querySelector(`input.price-override-input[onchange*="${exchangeKey}"]`);
    if (input) {
        input.value = '';
    }
    
    // Clear button 숨김
    const clearBtn = document.getElementById(`clearBtn-${exchangeKey}`);
    if (clearBtn) {
        clearBtn.style.display = 'none';
    }
    
    updateParams();
    updateData(); // 즉시 업데이트
}

// Update exchange-specific parameter
function updateExchangeParam(exchangeKey, paramType, value) {
    const numValue = parseFloat(value);
    
    // Update params object
    if (!params[paramType]) {
        params[paramType] = {};
    }
    params[paramType][exchangeKey] = numValue;
    
    // Sync slider and input
    const slider = document.querySelector(`input[type="range"][data-param="${paramType}"][data-key="${exchangeKey}"]`);
    const input = document.querySelector(`input[type="number"][data-param="${paramType}"][data-key="${exchangeKey}"]`);
    
    if (slider && slider.value !== value) {
        slider.value = value;
    }
    if (input && input.value !== value) {
        input.value = value;
    }
    
    // Update server
    updateParams();
}

