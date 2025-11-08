# 업비트 코인 빌리기 서비스 가격 오라클

빗썸 렌딩 서비스 대규모 청산 사태 방지를 위한 가격 산출 오라클 프로젝트입니다.

## 주요 기능

- 여러 CEX에서 가격을 수집하여 중앙값 계산
- 김치 프리미엄을 고려한 가격 변환 로직
- USDT/KRW 급격한 변동 감지 (TWAP 기반)
- 웹 대시보드를 통한 실시간 모니터링
- USDT/KRW 가격 조작 테스트 기능

## 설치

```bash
pip install -r requirements.txt
```

## 실행

```bash
python app.py
```

웹 브라우저에서 `http://localhost:5000` 접속

## 구조

- `app.py`: Flask 웹 애플리케이션 메인 파일
- `oracle.py`: 오라클 핵심 로직
- `price_fetcher.py`: CCTX를 사용한 거래소 가격 수집
- `templates/`: HTML 템플릿
- `static/`: CSS, JavaScript 파일

## 작동 원리

### 정상 모드
1. 업비트에서 ETH/KRW, USDT/KRW 가격 수집
2. 해외 거래소(Binance, OKX, Coinbase)에서 ETH/USDT 가격 수집
3. 해외 가격 변환: `ETH/KRW = ETH/USDT * USDT/KRW`
4. 모든 가격의 중앙값 계산

### 변동성 모드 (USDT/KRW 급격한 변동 감지 시)
1. TWAP(Time-Weighted Average Price)을 사용하여 USDT/KRW 변동성 감지
2. 변동성이 임계값(기본 5%)을 초과하면 역산 모드 전환
3. 국내 ETH/KRW와 해외 ETH/USDT를 사용하여 USDT/KRW 역산
4. 역산된 USDT/KRW로 해외 가격 변환
5. 모든 가격의 중앙값 계산

### 테스트 기능
- 대시보드에서 USDT/KRW 가격을 게이지로 조작하여 변동성 모드 테스트 가능
- 급격한 USDT 가격 변동 시 오라클의 저항성 확인

## 주의사항

- 실제 운영 환경에서는 API 키 설정 및 속도 제한 관리가 필요할 수 있습니다.
- 네트워크 오류 시 캐시된 가격을 사용합니다.
- 변동성 임계값은 환경에 맞게 조정이 필요할 수 있습니다.

