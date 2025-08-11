## Tarot API

FastAPI 기반의 타로 리딩 API.

### 빠른 시작
1) 가상환경/의존성 설치:
```
python3 -m venv .venv && source .venv/bin/activate
pip install -U pip
pip install -r requirements.txt
```
2) 환경 변수 준비: 프로젝트 루트에 `.env` 생성 (`.env.example` 참고)
3) 개발 서버 실행:
```
uvicorn app.main:app --reload
```
4) 테스트:
```
pytest
```

### 환경 변수
- `ENV`: 실행 환경(`local|dev|prod`). dev/prod에서는 `CORS_ORIGINS` 필수
- `LOG_LEVEL`: 로깅 레벨
- `CORS_ORIGINS`: 허용 오리진(쉼표구분). 예: https://your.pages.dev,https://www.example.com
- `DATA_PATH`: 카드 데이터 경로
- `RATE_LIMIT_*`: 레이트리밋 정책 조정
- `USE_DB`: true 시 DB 리포지토리 사용
- `DB_URL`: Postgres 연결 문자열 (예: `postgresql://user:pass@host:5432/db`)

### 컨테이너 실행
- Docker:
```
make docker-up
```
- Podman:
```
# macOS: 최초 1회
podman machine init && podman machine start

# 빌드/실행
make podman-build
make podman-up
```
- 중지:
```
make docker-down   # 또는
make podman-down
```

Podman은 `Containerfile`을 사용하며, 기존 `docker-compose.yml`을 그대로 활용할 수 있습니다(`podman-compose` 또는 `podman compose`).

### 데이터 업데이트
- 원격 소스(`metabismuth/tarot-json`)에서 78장 전체 동기화:
```
make data-update
```
- 검증만:
```
make data-validate
```
