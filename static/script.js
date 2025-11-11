// 전역 변수
let manualUsdtKrwPrice = null;
let manualEthKrwPrice = null;
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
    socket = io({
        transports: ['websocket', 'polling'], // WebSocket 우선, 폴백 지원
        reconnection: true,
        reconnectionDelay: 1000,
        reconnectionAttempts: 5,
    });
    
    socket.on('connect', () => {
        console.log('✅ 웹소켓 연결됨 - 실시간 업데이트 활성화');
    });
    
    socket.on('disconnect', () => {
        console.log('⚠️ 웹소켓 연결 해제됨');
    });
    
    socket.on('reconnect', (attemptNumber) => {
        console.log(`🔄 웹소켓 재연결됨 (시도 ${attemptNumber})`);
    });
    
    socket.on('price_update', (data) => {
        // 즉시 대시보드 업데이트 (지연 없음)
        updateDashboard(data);
    });
    
    socket.on('connect_error', (error) => {
        console.error('❌ 웹소켓 연결 오류:', error);
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
    
    // 0.5초마다 폴링 (웹소켓 업데이트 주기와 동일)
    setInterval(fetchData, 500);
}

// 차트 초기화
function initPriceChart() {
    const ctx = document.getElementById('priceChart').getContext('2d');
    const isDark = document.body.classList.contains('dark-mode');
    
    // 다크모드에 따른 색상 설정
    const primaryColor = isDark ? '#6366f1' : '#4f46e5'; // 인디고 블루
    const secondaryColor = isDark ? '#3b82f6' : '#2563eb'; // 파란색(남색)
    const gridColor = isDark ? 'rgba(255, 255, 255, 0.05)' : 'rgba(0, 0, 0, 0.05)';
    const textColor = isDark ? 'rgba(255, 255, 255, 0.7)' : 'rgba(0, 0, 0, 0.6)';
    const legendColor = isDark ? 'rgba(255, 255, 255, 0.9)' : 'rgba(0, 0, 0, 0.9)';
    
    // 그라데이션 생성
    const gradient1 = ctx.createLinearGradient(0, 0, 0, 400);
    if (isDark) {
        gradient1.addColorStop(0, 'rgba(99, 102, 241, 0.3)');
        gradient1.addColorStop(0.5, 'rgba(99, 102, 241, 0.15)');
        gradient1.addColorStop(1, 'rgba(99, 102, 241, 0)');
    } else {
        gradient1.addColorStop(0, 'rgba(79, 70, 229, 0.2)');
        gradient1.addColorStop(0.5, 'rgba(79, 70, 229, 0.1)');
        gradient1.addColorStop(1, 'rgba(79, 70, 229, 0)');
    }
    
    const gradient2 = ctx.createLinearGradient(0, 0, 0, 400);
    if (isDark) {
        gradient2.addColorStop(0, 'rgba(139, 92, 246, 0.2)');
        gradient2.addColorStop(0.5, 'rgba(139, 92, 246, 0.1)');
        gradient2.addColorStop(1, 'rgba(139, 92, 246, 0)');
    } else {
        gradient2.addColorStop(0, 'rgba(124, 58, 237, 0.15)');
        gradient2.addColorStop(0.5, 'rgba(124, 58, 237, 0.08)');
        gradient2.addColorStop(1, 'rgba(124, 58, 237, 0)');
    }
    
    priceChart = new Chart(ctx, {
        type: 'line',
        data: {
            labels: [],
            datasets: [
                {
                    label: '중앙값 가격',
                    data: [],
                    borderColor: primaryColor,
                    backgroundColor: gradient1,
                    borderWidth: 3,
                    fill: true,
                    tension: 0.5, // 더 매끄러운 곡선
                    pointRadius: 0, // 포인트 완전히 숨김
                    pointHoverRadius: 0, // 호버 시에도 포인트 없음
                    cubicInterpolationMode: 'monotone', // 더 자연스러운 곡선
                    shadowOffsetX: 0,
                    shadowOffsetY: 4,
                    shadowBlur: 10,
                    shadowColor: isDark ? 'rgba(99, 102, 241, 0.3)' : 'rgba(79, 70, 229, 0.2)',
                },
                {
                    label: '업비트 ETH/KRW',
                    data: [],
                    borderColor: secondaryColor,
                    backgroundColor: 'transparent',
                    borderWidth: 2,
                    fill: false,
                    tension: 0.5,
                    pointRadius: 0, // 포인트 완전히 숨김
                    pointHoverRadius: 0, // 호버 시에도 포인트 없음
                    borderDash: [8, 4], // 더 긴 점선
                    cubicInterpolationMode: 'monotone',
                }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: true,
            aspectRatio: 3,
            animation: {
                duration: 400,
                easing: 'easeOutQuart',
            },
            plugins: {
                legend: {
                    display: true,
                    position: 'top',
                    align: 'end',
                    labels: {
                        font: {
                            family: "'JetBrains Mono', monospace",
                            size: 11,
                            weight: '500',
                        },
                        usePointStyle: true,
                        pointStyle: 'circle',
                        padding: 15,
                        color: legendColor,
                        boxWidth: 12,
                        boxHeight: 12,
                    }
                },
                tooltip: {
                    mode: 'index',
                    intersect: false,
                    backgroundColor: isDark ? 'rgba(0, 0, 0, 0.9)' : 'rgba(255, 255, 255, 0.95)',
                    titleColor: isDark ? 'rgba(255, 255, 255, 0.9)' : 'rgba(0, 0, 0, 0.9)',
                    bodyColor: isDark ? 'rgba(255, 255, 255, 0.8)' : 'rgba(0, 0, 0, 0.8)',
                    borderColor: isDark ? 'rgba(255, 255, 255, 0.1)' : 'rgba(0, 0, 0, 0.1)',
                    borderWidth: 1,
                    padding: 12,
                    cornerRadius: 8,
                    displayColors: true,
                    callbacks: {
                        label: function(context) {
                            return context.dataset.label + ': ' + formatCurrency(context.parsed.y);
                        }
                    },
                    font: {
                        family: "'JetBrains Mono', monospace",
                        size: 11,
                    },
                    boxPadding: 6,
                }
            },
            scales: {
                x: {
                    grid: {
                        color: gridColor,
                        drawBorder: false,
                        lineWidth: 1,
                    },
                    ticks: {
                        font: {
                            family: "'JetBrains Mono', monospace",
                            size: 10,
                        },
                        color: textColor,
                        maxRotation: 45,
                        minRotation: 45,
                        padding: 8,
                    },
                    border: {
                        display: false,
                    }
                },
                y: {
                    beginAtZero: false,
                    grid: {
                        color: gridColor,
                        drawBorder: false,
                        lineWidth: 1,
                    },
                    ticks: {
                        font: {
                            family: "'JetBrains Mono', monospace",
                            size: 10,
                        },
                        color: textColor,
                        padding: 5,
                        callback: function(value) {
                            return formatNumber(value);
                        }
                    },
                    border: {
                        display: false,
                    },
                    grace: 0, // 자동 여백 제거
                }
            },
            interaction: {
                mode: 'nearest',
                axis: 'x',
                intersect: false
            },
            elements: {
                line: {
                    borderCapStyle: 'round',
                    borderJoinStyle: 'round',
                },
                point: {
                    radius: 0,
                    hoverRadius: 0,
                    pointStyle: false,
                }
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
        
        // 계산 방법에 따라 차트 색상 변경
        const isDark = document.body.classList.contains('dark-mode');
        const calculationMethod = oracle_result.calculation_method;
        const ctx = priceChart.canvas.getContext('2d');
        const chartArea = priceChart.chartArea;
        
        // 그라데이션 생성 (차트 높이에 맞춤)
        const gradient = ctx.createLinearGradient(0, chartArea ? chartArea.top : 0, 0, chartArea ? chartArea.bottom : 400);
        
        if (calculationMethod === 'normal') {
            // Primary Mode: 초록색
            if (isDark) {
                gradient.addColorStop(0, 'rgba(76, 175, 80, 0.3)'); // #4caf50
                gradient.addColorStop(0.5, 'rgba(76, 175, 80, 0.15)');
                gradient.addColorStop(1, 'rgba(76, 175, 80, 0)');
                priceChart.data.datasets[0].borderColor = '#4caf50';
                priceChart.data.datasets[0].shadowColor = 'rgba(76, 175, 80, 0.3)';
            } else {
                gradient.addColorStop(0, 'rgba(76, 175, 80, 0.2)');
                gradient.addColorStop(0.5, 'rgba(76, 175, 80, 0.1)');
                gradient.addColorStop(1, 'rgba(76, 175, 80, 0)');
                priceChart.data.datasets[0].borderColor = '#4caf50';
                priceChart.data.datasets[0].shadowColor = 'rgba(76, 175, 80, 0.2)';
            }
        } else if (calculationMethod === 'inverse') {
            // Backup Mode: 빨간색
            if (isDark) {
                gradient.addColorStop(0, 'rgba(220, 53, 69, 0.3)'); // #dc3545
                gradient.addColorStop(0.5, 'rgba(220, 53, 69, 0.15)');
                gradient.addColorStop(1, 'rgba(220, 53, 69, 0)');
                priceChart.data.datasets[0].borderColor = '#dc3545';
                priceChart.data.datasets[0].shadowColor = 'rgba(220, 53, 69, 0.3)';
            } else {
                gradient.addColorStop(0, 'rgba(220, 53, 69, 0.2)');
                gradient.addColorStop(0.5, 'rgba(220, 53, 69, 0.1)');
                gradient.addColorStop(1, 'rgba(220, 53, 69, 0)');
                priceChart.data.datasets[0].borderColor = '#dc3545';
                priceChart.data.datasets[0].shadowColor = 'rgba(220, 53, 69, 0.2)';
            }
        } else {
            // 기본 색상 (인디고 블루)
            if (isDark) {
                gradient.addColorStop(0, 'rgba(99, 102, 241, 0.3)');
                gradient.addColorStop(0.5, 'rgba(99, 102, 241, 0.15)');
                gradient.addColorStop(1, 'rgba(99, 102, 241, 0)');
                priceChart.data.datasets[0].borderColor = '#6366f1';
                priceChart.data.datasets[0].shadowColor = 'rgba(99, 102, 241, 0.3)';
            } else {
                gradient.addColorStop(0, 'rgba(79, 70, 229, 0.2)');
                gradient.addColorStop(0.5, 'rgba(79, 70, 229, 0.1)');
                gradient.addColorStop(1, 'rgba(79, 70, 229, 0)');
                priceChart.data.datasets[0].borderColor = '#4f46e5';
                priceChart.data.datasets[0].shadowColor = 'rgba(79, 70, 229, 0.2)';
            }
        }
        
        priceChart.data.datasets[0].backgroundColor = gradient;
        
        // Y축 스케일을 데이터 범위에 맞춰 조정 (차이를 더 잘 보이도록)
        const allPrices = [
            ...(history.median_prices || []).filter(p => p !== null && p !== undefined && p > 0),
            ...(history.upbit_eth_krw || []).filter(p => p !== null && p !== undefined && p > 0)
        ];
        
        if (allPrices.length > 0) {
            const minPrice = Math.min(...allPrices);
            const maxPrice = Math.max(...allPrices);
            const priceRange = maxPrice - minPrice;
            
            // 최소한의 여백만 추가 (1% 또는 최소 1000원)
            const padding = Math.max(priceRange * 0.01, 1000);
            const suggestedMin = minPrice - padding;
            const suggestedMax = maxPrice + padding;
            
            // Y축 범위를 정확히 설정 (Chart.js의 자동 조정 방지)
            priceChart.options.scales.y.min = suggestedMin;
            priceChart.options.scales.y.max = suggestedMax;
            priceChart.options.scales.y.grace = 0; // 자동 여백 완전히 제거
        }
        
        // 부드러운 애니메이션으로 업데이트
        priceChart.update('active');
    }

    // 중앙값 가격 표시
    const medianPriceEl = document.getElementById('median-price');
    if (oracle_result.median_price !== null) {
        medianPriceEl.querySelector('.price-value').textContent = formatNumber(oracle_result.median_price);
    } else {
        medianPriceEl.querySelector('.price-value').textContent = '-';
    }
    
    // 계산 방법 표시
    const methodEl = document.getElementById('calculation-method');
    if (oracle_result.calculation_method === 'normal') {
        methodEl.textContent = 'Primary Mode';
        methodEl.style.color = '#4caf50';
    } else if (oracle_result.calculation_method === 'inverse') {
        methodEl.textContent = 'Backup Mode';
        methodEl.style.color = '#dc3545';
    } else {
        methodEl.textContent = 'No Data';
        methodEl.style.color = '#999';
    }
    
    // ETH/KRW 정보 업데이트
    // Upbit 가격 표시 (수동 가격이 있으면 수동 가격, 없으면 실제 가격)
    const hasManualEthKrw = oracle_result.price_details && 
        oracle_result.price_details.some(([name]) => name === 'upbit (manual)');
    const upbitEthKrwToShow = hasManualEthKrw 
        ? oracle_result.price_details.find(([name]) => name === 'upbit (manual)')?.[1]
        : prices.upbit_eth_krw;
    
    // 업비트 가격과 비교 정보 표시 (조작된 가격이 있으면 조작된 가격 사용)
    const medianPrice = oracle_result.median_price;
    const priceComparisonEl = document.getElementById('price-comparison');
    const upbitPriceCompareEl = document.getElementById('upbit-price-compare');
    const priceDiffEl = document.getElementById('price-diff');
    const priceDiffPercentEl = document.getElementById('price-diff-percent');
    
    if (upbitEthKrwToShow !== null && upbitEthKrwToShow !== undefined && medianPrice !== null && medianPrice !== undefined) {
        // 업비트 가격 (조작된 가격이 있으면 조작된 가격 표시)
        const upbitLabel = hasManualEthKrw ? '업비트 (조작됨)' : '업비트';
        upbitPriceCompareEl.textContent = `${upbitLabel}: ${formatCurrency(upbitEthKrwToShow)}`;
        
        // 차이값 계산
        const diff = medianPrice - upbitEthKrwToShow;
        const diffPercent = (diff / upbitEthKrwToShow) * 100;
        
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
    document.getElementById('upbit-eth-krw-info').textContent = formatCurrency(upbitEthKrwToShow);
    document.getElementById('median-eth-krw-info').textContent = formatCurrency(oracle_result.median_price);
    
    const ethKrwMethodEl = document.getElementById('eth-krw-method');
    if (hasManualEthKrw) {
        ethKrwMethodEl.textContent = 'Upbit 수동 조작';
        ethKrwMethodEl.style.color = '#ffc107';
    } else if (oracle_result.calculation_method === 'normal') {
        ethKrwMethodEl.textContent = 'Primary Mode';
        ethKrwMethodEl.style.color = '#4caf50';
    } else if (oracle_result.calculation_method === 'inverse') {
        ethKrwMethodEl.textContent = 'Backup Mode';
        ethKrwMethodEl.style.color = '#dc3545';
    } else {
        ethKrwMethodEl.textContent = '-';
        ethKrwMethodEl.style.color = '#999';
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
    
    // USDT/KRW 조작 여부 확인 (original과 실제 업비트 가격이 다르면 조작된 것으로 판단)
    const isManualUsdtKrw = originalUsdtKrw !== null && 
        prices.upbit_usdt_krw !== null && 
        Math.abs(originalUsdtKrw - prices.upbit_usdt_krw) > 0.01;
    
    if (oracle_result.is_volatile && inverseUsdtKrw !== null && inverseUsdtKrw !== undefined) {
        // 역산 모드: 역산된 USDT/KRW와 원본 가격 표시
        document.getElementById('inverse-usdt-krw').textContent = formatCurrency(inverseUsdtKrw);
        inverseContainer.style.display = 'block';
        
        if (originalUsdtKrw !== null && originalUsdtKrw !== undefined) {
            document.getElementById('original-usdt-krw').textContent = formatCurrency(originalUsdtKrw);
            originalContainer.style.display = 'block';
        }
    } else if (isManualUsdtKrw) {
        // USDT/KRW가 조작된 경우 표시
        document.getElementById('original-usdt-krw').textContent = formatCurrency(originalUsdtKrw);
        originalContainer.style.display = 'block';
        inverseContainer.style.display = 'none';
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

// ETH/KRW 게이지 이벤트
function setupEthKrwGauge() {
    const gauge = document.getElementById('eth-krw-gauge');
    const gaugeValueDisplay = document.getElementById('eth-gauge-value-display');
    const resetBtn = document.getElementById('reset-eth-gauge');
    const applyBtn = document.getElementById('apply-eth-gauge');
    const gaugeStatus = document.getElementById('eth-gauge-status');

    // 게이지 값 변경 시 표시 업데이트
    gauge.addEventListener('input', (e) => {
        gaugeValueDisplay.textContent = formatNumber(parseFloat(e.target.value));
    });

    // 리셋 버튼
    resetBtn.addEventListener('click', async () => {
        manualEthKrwPrice = null;
        gaugeStatus.textContent = '자동 모드';
        gaugeStatus.className = 'gauge-status auto';
        
        // 서버에 수동 가격 해제 요청
        try {
            const response = await fetch('/api/eth-krw/manual', {
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
        manualEthKrwPrice = price;
        gaugeStatus.textContent = `수동 모드: ${formatNumber(price)} KRW`;
        gaugeStatus.className = 'gauge-status manual';
        
        // 서버에 수동 가격 설정 요청
        try {
            const response = await fetch('/api/eth-krw/manual', {
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
    checkManualEthPrice();
}

// ETH/KRW 수동 가격 상태 확인
async function checkManualEthPrice() {
    try {
        const response = await fetch('/api/eth-krw/manual');
        const data = await response.json();
        
        if (data.manual_price !== null) {
            manualEthKrwPrice = data.manual_price;
            const gauge = document.getElementById('eth-krw-gauge');
            const gaugeValueDisplay = document.getElementById('eth-gauge-value-display');
            const gaugeStatus = document.getElementById('eth-gauge-status');
            
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
    
    const ctx = priceChart.canvas.getContext('2d');
    
    // 그라데이션 재생성
    const gradient1 = ctx.createLinearGradient(0, 0, 0, 400);
    const gradient2 = ctx.createLinearGradient(0, 0, 0, 400);
    
    if (isDark) {
        priceChart.data.datasets[0].borderColor = '#6366f1';
        gradient1.addColorStop(0, 'rgba(99, 102, 241, 0.3)');
        gradient1.addColorStop(0.5, 'rgba(99, 102, 241, 0.15)');
        gradient1.addColorStop(1, 'rgba(99, 102, 241, 0)');
        priceChart.data.datasets[0].backgroundColor = gradient1;
        priceChart.data.datasets[0].pointHoverBackgroundColor = '#6366f1';
        priceChart.data.datasets[0].shadowColor = 'rgba(99, 102, 241, 0.3)';
        
        priceChart.data.datasets[1].borderColor = '#3b82f6';
        priceChart.data.datasets[1].pointHoverBackgroundColor = '#3b82f6';
        
        priceChart.options.scales.x.grid.color = 'rgba(255, 255, 255, 0.05)';
        priceChart.options.scales.y.grid.color = 'rgba(255, 255, 255, 0.05)';
        priceChart.options.scales.x.ticks.color = 'rgba(255, 255, 255, 0.7)';
        priceChart.options.scales.y.ticks.color = 'rgba(255, 255, 255, 0.7)';
        priceChart.options.plugins.legend.labels.color = 'rgba(255, 255, 255, 0.9)';
        priceChart.options.plugins.tooltip.backgroundColor = 'rgba(0, 0, 0, 0.9)';
        priceChart.options.plugins.tooltip.titleColor = 'rgba(255, 255, 255, 0.9)';
        priceChart.options.plugins.tooltip.bodyColor = 'rgba(255, 255, 255, 0.8)';
        priceChart.options.plugins.tooltip.borderColor = 'rgba(255, 255, 255, 0.1)';
    } else {
        priceChart.data.datasets[0].borderColor = '#4f46e5';
        gradient1.addColorStop(0, 'rgba(79, 70, 229, 0.2)');
        gradient1.addColorStop(0.5, 'rgba(79, 70, 229, 0.1)');
        gradient1.addColorStop(1, 'rgba(79, 70, 229, 0)');
        priceChart.data.datasets[0].backgroundColor = gradient1;
        priceChart.data.datasets[0].pointHoverBackgroundColor = '#4f46e5';
        priceChart.data.datasets[0].shadowColor = 'rgba(79, 70, 229, 0.2)';
        
        priceChart.data.datasets[1].borderColor = '#2563eb';
        priceChart.data.datasets[1].pointHoverBackgroundColor = '#2563eb';
        
        priceChart.options.scales.x.grid.color = 'rgba(0, 0, 0, 0.05)';
        priceChart.options.scales.y.grid.color = 'rgba(0, 0, 0, 0.05)';
        priceChart.options.scales.x.ticks.color = 'rgba(0, 0, 0, 0.6)';
        priceChart.options.scales.y.ticks.color = 'rgba(0, 0, 0, 0.6)';
        priceChart.options.plugins.legend.labels.color = 'rgba(0, 0, 0, 0.9)';
        priceChart.options.plugins.tooltip.backgroundColor = 'rgba(255, 255, 255, 0.95)';
        priceChart.options.plugins.tooltip.titleColor = 'rgba(0, 0, 0, 0.9)';
        priceChart.options.plugins.tooltip.bodyColor = 'rgba(0, 0, 0, 0.8)';
        priceChart.options.plugins.tooltip.borderColor = 'rgba(0, 0, 0, 0.1)';
    }
    priceChart.update('none');
}

// 초기화
document.addEventListener('DOMContentLoaded', () => {
    setupUsdtKrwGauge();
    setupEthKrwGauge();
    
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

