## Tarot API

FastAPI 기반의 타로 리딩 API.

### 빠른 시작
1) Poetry 설치 후 의존성 설치:
```
poetry install
```
2) 개발 서버 실행:
```
poetry run uvicorn app.main:app --reload
```
3) 테스트:
```
poetry run pytest
```

### 환경 변수
`.env.example`를 참고해 `.env`를 루트에 생성하세요.

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
