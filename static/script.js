// 전역 변수
let manualUsdtKrwPrice = null;
let priceChart = null;
let socket = null;

// 숫자 포맷팅 함수
function formatNumber(num) {
    if (num === null || num === undefined) return '-';
    return new Intl.NumberFormat('ko-KR', {
        minimumFractionDigits: 0,
        maximumFractionDigits: 2
    }).format(num);
}

function formatCurrency(num) {
    if (num === null || num === undefined) return '-';
    return new Intl.NumberFormat('ko-KR', {
        style: 'currency',
        currency: 'KRW',
        minimumFractionDigits: 0,
        maximumFractionDigits: 0
    }).format(num);
}

// 날짜 포맷팅 함수
function formatTimestamp(isoString) {
    if (!isoString) return '-';
    const date = new Date(isoString);
    return date.toLocaleString('ko-KR');
}

// 거래소 이름 포맷팅 함수 (첫 글자 대문자)
function formatExchangeName(name) {
    if (!name) return '';
    
    // 단어 변환 헬퍼 함수
    const capitalizeWord = (word) => {
        if (word.length === 0) return word;
        // 괄호로 시작하는 경우 (예: "(converted)")
        if (word.startsWith('(') && word.length > 1) {
            return '(' + word.charAt(1).toUpperCase() + word.slice(2).toLowerCase();
        }
        return word.charAt(0).toUpperCase() + word.slice(1).toLowerCase();
    };
    
    // OKX는 전부 대문자로 변환
    if (name.toLowerCase().startsWith('okx')) {
        return name.split(' ').map(word => {
            if (word.toLowerCase() === 'okx') {
                return 'OKX';
            }
            return capitalizeWord(word);
        }).join(' ');
    }
    // 각 단어의 첫 글자를 대문자로 변환
    return name.split(' ').map(word => capitalizeWord(word)).join(' ');
}

// 웹소켓 연결 설정
function setupWebSocket() {
    socket = io();
    
    socket.on('connect', () => {
        console.log('웹소켓 연결됨');
    });
    
    socket.on('disconnect', () => {
        console.log('웹소켓 연결 해제됨');
    });
    
    socket.on('price_update', (data) => {
        updateDashboard(data);
    });
    
    socket.on('connect_error', (error) => {
        console.error('웹소켓 연결 오류:', error);
        // 웹소켓 연결 실패 시 HTTP 폴링으로 폴백
        console.log('HTTP 폴링으로 전환합니다...');
        setupHttpPolling();
    });
}

// HTTP 폴링 (웹소켓 폴백용)
function setupHttpPolling() {
    const fetchData = async () => {
        try {
            const response = await fetch('/api/data');
            const data = await response.json();
            updateDashboard(data);
        } catch (error) {
            console.error('데이터 가져오기 실패:', error);
        }
    };
    
    // 즉시 한 번 실행
    fetchData();
    
    // 1초마다 폴링
    setInterval(fetchData, 1000);
}

// 차트 초기화
function initPriceChart() {
    const ctx = document.getElementById('priceChart').getContext('2d');
    const isDark = document.body.classList.contains('dark-mode');
    
    // 다크모드에 따른 초기 색상 설정
    const primaryColor = isDark ? '#e0e0e0' : '#1a1a1a';
    const secondaryColor = isDark ? '#b0b0b0' : '#666';
    const gridColor = isDark ? '#333' : '#e5e5e5';
    const textColor = isDark ? '#b0b0b0' : '#1a1a1a';
    const legendColor = isDark ? '#e0e0e0' : '#1a1a1a';
    
    priceChart = new Chart(ctx, {
        type: 'line',
        data: {
            labels: [],
            datasets: [
                {
                    label: '중앙값 가격',
                    data: [],
                    borderColor: primaryColor,
                    backgroundColor: isDark ? 'rgba(224, 224, 224, 0.1)' : 'rgba(26, 26, 26, 0.1)',
                    borderWidth: 2,
                    fill: true,
                    tension: 0.4,
                },
                {
                    label: '업비트 ETH/KRW',
                    data: [],
                    borderColor: secondaryColor,
                    backgroundColor: isDark ? 'rgba(176, 176, 176, 0.1)' : 'rgba(102, 102, 102, 0.1)',
                    borderWidth: 1,
                    fill: false,
                    tension: 0.4,
                    borderDash: [5, 5],
                }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: true,
            aspectRatio: 3,
            plugins: {
                legend: {
                    display: true,
                    position: 'top',
                    labels: {
                        font: {
                            family: "'JetBrains Mono', monospace",
                            size: 12,
                        },
                        usePointStyle: true,
                        color: legendColor,
                    }
                },
                tooltip: {
                    mode: 'index',
                    intersect: false,
                    callbacks: {
                        label: function(context) {
                            return context.dataset.label + ': ' + formatCurrency(context.parsed.y);
                        }
                    },
                    font: {
                        family: "'JetBrains Mono', monospace",
                    }
                }
            },
            scales: {
                x: {
                    grid: {
                        color: gridColor,
                    },
                    ticks: {
                        font: {
                            family: "'JetBrains Mono', monospace",
                            size: 10,
                        },
                        color: textColor,
                        maxRotation: 45,
                        minRotation: 45,
                    }
                },
                y: {
                    grid: {
                        color: gridColor,
                    },
                    ticks: {
                        font: {
                            family: "'JetBrains Mono', monospace",
                            size: 10,
                        },
                        color: textColor,
                        callback: function(value) {
                            return formatNumber(value);
                        }
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

// 대시보드 업데이트
function updateDashboard(data) {
    if (!data.prices || !data.oracle_result) {
        return;
    }

    const { prices, oracle_result } = data;
    
    // 차트 업데이트
    if (data.price_history && priceChart && data.price_history.timestamps && data.price_history.timestamps.length > 0) {
        const history = data.price_history;
        const labels = history.timestamps.map(ts => {
            const date = new Date(ts);
            return date.toLocaleTimeString('ko-KR', { hour: '2-digit', minute: '2-digit', second: '2-digit' });
        });
        
        priceChart.data.labels = labels;
        priceChart.data.datasets[0].data = history.median_prices || [];
        priceChart.data.datasets[1].data = history.upbit_eth_krw || [];
        priceChart.update('none'); // 애니메이션 없이 업데이트
    }

    // 중앙값 가격 표시
    const medianPriceEl = document.getElementById('median-price');
    if (oracle_result.median_price !== null) {
        medianPriceEl.querySelector('.price-value').textContent = formatNumber(oracle_result.median_price);
    } else {
        medianPriceEl.querySelector('.price-value').textContent = '-';
    }
    
    // 업비트 가격과 비교 정보 표시
    const upbitEthKrw = prices.upbit_eth_krw;
    const medianPrice = oracle_result.median_price;
    const priceComparisonEl = document.getElementById('price-comparison');
    const upbitPriceCompareEl = document.getElementById('upbit-price-compare');
    const priceDiffEl = document.getElementById('price-diff');
    const priceDiffPercentEl = document.getElementById('price-diff-percent');
    
    if (upbitEthKrw !== null && upbitEthKrw !== undefined && medianPrice !== null && medianPrice !== undefined) {
        // 업비트 가격
        upbitPriceCompareEl.textContent = `업비트: ${formatCurrency(upbitEthKrw)}`;
        
        // 차이값 계산
        const diff = medianPrice - upbitEthKrw;
        const diffPercent = (diff / upbitEthKrw) * 100;
        
        // 차이값 표시
        const diffSign = diff >= 0 ? '+' : '';
        priceDiffEl.textContent = `차이: ${diffSign}${formatCurrency(diff)}`;
        
        // 차이 퍼센티지 표시
        const percentSign = diffPercent >= 0 ? '+' : '';
        priceDiffPercentEl.textContent = `(${percentSign}${diffPercent.toFixed(2)}%)`;
        
        // 차이값에 따라 색상 변경
        if (Math.abs(diffPercent) < 0.1) {
            // 거의 차이 없음
            priceDiffEl.style.color = '#999';
            priceDiffPercentEl.style.color = '#999';
        } else if (diffPercent > 0) {
            // 중앙값이 더 높음
            priceDiffEl.style.color = '#4caf50';
            priceDiffPercentEl.style.color = '#4caf50';
        } else {
            // 중앙값이 더 낮음
            priceDiffEl.style.color = '#f44336';
            priceDiffPercentEl.style.color = '#f44336';
        }
    } else {
        upbitPriceCompareEl.textContent = '-';
        priceDiffEl.textContent = '-';
        priceDiffPercentEl.textContent = '';
    }

    // 계산 방법 표시
    const methodEl = document.getElementById('calculation-method');
    if (oracle_result.calculation_method === 'normal') {
        methodEl.textContent = 'Normal Mode';
        methodEl.style.color = '#4caf50';
    } else if (oracle_result.calculation_method === 'inverse') {
        methodEl.textContent = 'Inverse Mode';
        methodEl.style.color = '#dc3545';
    } else {
        methodEl.textContent = 'No Data';
        methodEl.style.color = '#999';
    }

    // 타임스탬프
    document.getElementById('price-timestamp').textContent = formatTimestamp(data.timestamp);

    // USDT/KRW 정보
    document.getElementById('upbit-usdt-krw').textContent = formatCurrency(prices.upbit_usdt_krw);
    
    const twapPrice = oracle_result.twap;
    document.getElementById('twap-price').textContent = twapPrice !== null ? formatCurrency(twapPrice) : '-';
    
    // 변동성 상태
    const volatilityEl = document.getElementById('volatility-status');
    if (oracle_result.is_volatile) {
        volatilityEl.textContent = '⚠️ 변동성 높음';
        volatilityEl.className = 'status-badge volatile';
    } else {
        volatilityEl.textContent = '✅ 정상';
        volatilityEl.className = 'status-badge normal';
    }

    // 사용 중인 USDT/KRW 가격
    const usedUsdtKrw = oracle_result.usdt_krw_used;
    document.getElementById('used-usdt-krw').textContent = formatCurrency(usedUsdtKrw);
    
    // 역산된 USDT/KRW 가격 표시 (역산 모드일 때만)
    const inverseUsdtKrw = oracle_result.inverse_usdt_krw;
    const originalUsdtKrw = oracle_result.usdt_krw_original;
    const inverseContainer = document.getElementById('inverse-usdt-krw-container');
    const originalContainer = document.getElementById('original-usdt-krw-container');
    
    if (oracle_result.is_volatile && inverseUsdtKrw !== null && inverseUsdtKrw !== undefined) {
        // 역산 모드: 역산된 USDT/KRW와 원본 가격 표시
        document.getElementById('inverse-usdt-krw').textContent = formatCurrency(inverseUsdtKrw);
        inverseContainer.style.display = 'block';
        
        if (originalUsdtKrw !== null && originalUsdtKrw !== undefined) {
            document.getElementById('original-usdt-krw').textContent = formatCurrency(originalUsdtKrw);
            originalContainer.style.display = 'block';
        }
    } else {
        // 정상 모드: 역산 정보 숨기기
        inverseContainer.style.display = 'none';
        originalContainer.style.display = 'none';
    }

    // 중앙값 결과 헤더에 표시
    const medianResultValue = document.getElementById('median-result-value');
    if (oracle_result.median_price !== null) {
        medianResultValue.textContent = formatCurrency(oracle_result.median_price);
    } else {
        medianResultValue.textContent = '-';
    }

    // 가격 상세 정보
    const priceDetailsEl = document.getElementById('price-details-list');
    priceDetailsEl.innerHTML = '';
    
    if (oracle_result.price_details && oracle_result.price_details.length > 0) {
        oracle_result.price_details.forEach(([name, price]) => {
            const detailItem = document.createElement('div');
            detailItem.className = 'price-detail-item';
            
            // 업비트는 강조 표시
            const isUpbit = name === 'upbit';
            const itemStyle = isUpbit ? 'border-left: 3px solid #1a1a1a;' : '';
            
            detailItem.style.cssText = itemStyle;
            detailItem.innerHTML = `
                <span class="exchange-name">${formatExchangeName(name)}</span>
                <span class="price-value">${formatCurrency(price)}</span>
            `;
            priceDetailsEl.appendChild(detailItem);
        });
    }
}

// USDT/KRW 게이지 이벤트
function setupUsdtKrwGauge() {
    const gauge = document.getElementById('usdt-krw-gauge');
    const gaugeValueDisplay = document.getElementById('gauge-value-display');
    const resetBtn = document.getElementById('reset-gauge');
    const applyBtn = document.getElementById('apply-gauge');
    const gaugeStatus = document.getElementById('gauge-status');

    // 게이지 값 변경 시 표시 업데이트
    gauge.addEventListener('input', (e) => {
        gaugeValueDisplay.textContent = formatNumber(parseFloat(e.target.value));
    });

    // 리셋 버튼
    resetBtn.addEventListener('click', async () => {
        manualUsdtKrwPrice = null;
        gaugeStatus.textContent = '자동 모드';
        gaugeStatus.className = 'gauge-status auto';
        
        // 서버에 수동 가격 해제 요청
        try {
            const response = await fetch('/api/usdt-krw/manual', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ price: null }),
            });
            
            const result = await response.json();
            console.log(result.message);
            
            // 수동 업데이트 트리거 (서버에서 웹소켓으로 브로드캐스트됨)
            if (socket && socket.connected) {
                // 웹소켓 연결된 경우 서버에서 자동으로 업데이트가 브로드캐스트됨
                // 필요시 수동 업데이트 API 호출
                fetch('/api/oracle/update', { method: 'POST' });
            }
        } catch (error) {
            console.error('리셋 실패:', error);
        }
    });

    // 적용 버튼
    applyBtn.addEventListener('click', async () => {
        const price = parseFloat(gauge.value);
        manualUsdtKrwPrice = price;
        gaugeStatus.textContent = `수동 모드: ${formatNumber(price)} KRW`;
        gaugeStatus.className = 'gauge-status manual';
        
        // 서버에 수동 가격 설정 요청
        try {
            const response = await fetch('/api/usdt-krw/manual', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ price: price }),
            });
            
            const result = await response.json();
            console.log(result.message);
            
            // 수동 업데이트 트리거 (서버에서 웹소켓으로 브로드캐스트됨)
            if (socket && socket.connected) {
                // 웹소켓 연결된 경우 서버에서 자동으로 업데이트가 브로드캐스트됨
                // 필요시 수동 업데이트 API 호출
                fetch('/api/oracle/update', { method: 'POST' });
            }
        } catch (error) {
            console.error('적용 실패:', error);
        }
    });

    // 초기 수동 가격 상태 확인
    checkManualPrice();
}

// 수동 가격 상태 확인
async function checkManualPrice() {
    try {
        const response = await fetch('/api/usdt-krw/manual');
        const data = await response.json();
        
        if (data.manual_price !== null) {
            manualUsdtKrwPrice = data.manual_price;
            const gauge = document.getElementById('usdt-krw-gauge');
            const gaugeValueDisplay = document.getElementById('gauge-value-display');
            const gaugeStatus = document.getElementById('gauge-status');
            
            gauge.value = data.manual_price;
            gaugeValueDisplay.textContent = formatNumber(data.manual_price);
            gaugeStatus.textContent = `수동 모드: ${formatNumber(data.manual_price)} KRW`;
            gaugeStatus.className = 'gauge-status manual';
        }
    } catch (error) {
        console.error('수동 가격 확인 실패:', error);
    }
}

// 다크모드 설정
function setupDarkMode() {
    const toggleInput = document.getElementById('dark-mode-toggle-input');
    const body = document.body;
    
    // localStorage에서 다크모드 설정 불러오기
    const isDarkMode = localStorage.getItem('darkMode') === 'true';
    if (isDarkMode) {
        body.classList.add('dark-mode');
        toggleInput.checked = true;
    } else {
        toggleInput.checked = false;
    }
    
    // 초기 차트 색상 설정
    if (priceChart) {
        updateChartColors(isDarkMode);
    }
    
    // 다크모드 토글
    toggleInput.addEventListener('change', () => {
        const isDark = toggleInput.checked;
        if (isDark) {
            body.classList.add('dark-mode');
        } else {
            body.classList.remove('dark-mode');
        }
        localStorage.setItem('darkMode', isDark);
        
        // 차트 색상 업데이트
        if (priceChart) {
            updateChartColors(isDark);
        }
    });
}

// 차트 색상 업데이트
function updateChartColors(isDark) {
    if (!priceChart) return;
    
    if (isDark) {
        priceChart.data.datasets[0].borderColor = '#e0e0e0';
        priceChart.data.datasets[0].backgroundColor = 'rgba(224, 224, 224, 0.1)';
        priceChart.data.datasets[1].borderColor = '#b0b0b0';
        priceChart.data.datasets[1].backgroundColor = 'rgba(176, 176, 176, 0.1)';
        priceChart.options.scales.x.grid.color = '#333';
        priceChart.options.scales.y.grid.color = '#333';
        priceChart.options.scales.x.ticks.color = '#b0b0b0';
        priceChart.options.scales.y.ticks.color = '#b0b0b0';
        priceChart.options.plugins.legend.labels.color = '#e0e0e0';
    } else {
        priceChart.data.datasets[0].borderColor = '#1a1a1a';
        priceChart.data.datasets[0].backgroundColor = 'rgba(26, 26, 26, 0.1)';
        priceChart.data.datasets[1].borderColor = '#666';
        priceChart.data.datasets[1].backgroundColor = 'rgba(102, 102, 102, 0.1)';
        priceChart.options.scales.x.grid.color = '#e5e5e5';
        priceChart.options.scales.y.grid.color = '#e5e5e5';
        priceChart.options.scales.x.ticks.color = '#1a1a1a';
        priceChart.options.scales.y.ticks.color = '#1a1a1a';
        priceChart.options.plugins.legend.labels.color = '#1a1a1a';
    }
    priceChart.update('none');
}

// 초기화
document.addEventListener('DOMContentLoaded', () => {
    setupUsdtKrwGauge();
    
    // 다크모드 설정
    setupDarkMode();
    
    // 차트 초기화
    initPriceChart();
    
    // 웹소켓 연결
    setupWebSocket();
    
    // 초기 차트 색상 설정
    const isDark = document.body.classList.contains('dark-mode');
    if (priceChart) {
        updateChartColors(isDark);
    }
});

// 페이지 언로드 시 정리
window.addEventListener('beforeunload', () => {
    if (socket) {
        socket.disconnect();
    }
});

