# 코드작성은 설계원칙, SOLID원칙을 지키며, 클린코드 기반으로 한다. 
# 이 프로젝트 폴더 내에서는 백엔드 작업만 한다.

# 0) 목표 정의

* **MVP 핵심**: 사용자가 고민 입력 → 3그룹 선택/섞기 횟수 지정 → 8장 스프레드(솔루션 포함) 표시 → 카드별 의미/정·역방향 해석 출력 → 결과 저장/공유
* **룰(스프레드)**:

  ```
          1 2        8(솔루션)
         3 4 5
         6 7
  ```

  * 1: 이슈, 2: 숨은 영향, 3\~5: 과거·현재·근미래, 6: 내면, 7: 외부, 8: 솔루션

# 1) 데이터/소스

* **카드 데이터 소스**: `metabismuth/tarot-json`의 `tarot-images.json`(이미지 경로+메타)
* **라이선스**: RWS 퍼블릭 도메인 스캔 기반 → 상업 사용 OK (출처 표기 권장)
* **프로젝트 포함 방식**: 초기엔 `data/tarot-images.json` 로컬 고정 → 추후 빌드 타임 fetch로 전환

# 2) 프런트엔드 (MVP)

* **스택**: Next.js + TypeScript + Tailwind + Framer Motion
* **화면 흐름**

  1. 고민 입력 → 2) 그룹 순서(A/B/C) 선택 → 3) 섞기 횟수 입력 → 4) 카드 뽑기 → 5) 결과 화면
* **기능**

  * 카드 애니메이션(뒤집기/정·역 표시), 카드 상세 패널(키워드/의미)
  * 결과 이미지/PDF 저장(선택), 공유 링크
* **상태관리**: 서버 응답을 단일 소스(React Query or SWR)로 캐시

# 3) 백엔드 (MVP)

* **스택**: FastAPI + Pydantic + Uvicorn
* **엔드포인트**

  * `GET /health`
  * `GET /cards` : 카드 개수 등 메타
  * `POST /reading` : 입력(질문/그룹순서/섞기횟수/seed/역방향 여부) → 8장 배치 반환
* **서비스 레이어**

  * 78장 → 3그룹 분할 → 사용자 순서 병합 → Fisher–Yates n회 셔플 → 8장 픽 → 포지션 매핑
  * 역방향 플래그 50% 확률(옵션/seed로 재현성)
* **저장(DB)**

  * 1차: 저장 없음(메모리) → 2차: Postgres(Supabase)로 `readings`, `reading_cards`, (옵션) `interpretations`

# 3-1) 백엔드 진행상태

## 완료

- [x] 앱 초기화: `FastAPI` 앱 생성, `setup_logging` 적용, 버전/타이틀 설정
- [x] 미들웨어: `CORS`(env 기반), `request_id` 부여/로그, `SlowAPI` 레이트리밋, 보안 헤더(`X-Content-Type-Options` 등)
- [x] 에러 처리: 전역 Exception/Validation 핸들러(JSON 구조화, `request_id` 포함)
- [x] 데이터 로딩: `DeckLoader`로 `data/tarot-images.json` 지연 로드+메모리 캐시(78장 확인 경고)
- [x] 유틸: 재현성 가능한 셔플(`fisher_yates_shuffle_with_rng` + `seed`)
- [x] 서비스: 78장→3그룹 분할→사용자 순서 병합→N회 셔플→8장 드로우(정/역방향 옵션)
- [x] 스키마: `Card`, `CardsResponse`, `ReadingRequest/Response`, `DrawnCard`(검증 포함)
- [x] 라우터:
  - `GET /health/` (버스트 레이트리밋 5/sec)
  - `GET /cards/` (전체 카드 메타 반환)
  - `POST /reading/` (질문/그룹순서/섞기횟수/seed/역방향 → 8장 결과)
- [x] 테스트: health/cards/reading 기본·재현성·검증, observability(요청 ID 헤더)
- [x] 설정: `.env` 기반 `ENV/LOG_LEVEL/CORS_ORIGINS/DATA_PATH` 지원
- [x] 배포 준비물: `Dockerfile`, `docker-compose.yml`, `render.yaml`

## 진행해야 할 것

- [ ] 운영 CORS 원본 확정 및 `CORS_ORIGINS` 환경변수 설정(Cloudflare Pages 도메인 포함)
- [x] 엔드포인트별 레이트리밋 정책 세분화(예: `POST /reading` 10/min/IP, `GET /cards` 120/min/IP)
- [x] 관측성 강화: 구조화 로그 필드(`request_id`, `client_ip`, `duration_ms`) 추가
- [x] 성능: 콜드스타트 방지용 Deck 예열 로딩
- [ ] 스키마 i18n 대비(의미 필드 키 기반 확장 설계) 및 `upright/reversed_meaning` 데이터 소스 확정
- [x] 1차 영속화(인메모리): `ReadingRepository` 추가, `POST /reading` 저장 + `GET /reading/{id}` 조회
- [ ] DB 단계(2차): Postgres(Supabase) 스키마 설계/마이그레이션(`readings`, `reading_cards`), TTL/익명세션, `GET /reading/{id}` 유지
- [ ] (옵션) LLM 해석 API 설계/구현: `POST /reading/{id}/interpret`(레이트리밋/서명/감사 로그)
- [ ] 배포: Render 환경변수 세팅(`CORS_ORIGINS`, `DATA_PATH` 등) 및 헬스체크/오토스케일 파라미터 점검

# 4) 해석(옵션 단계)

* **LLM 없이도 동작**: `meaning_up/meaning_rev` 출력
* **LLM 추가 시**

  * `POST /reading/{id}/interpret` : 질문+8장+포지션 텍스트 → 감성 해석 생성
  * 지침: 8번 솔루션 중심, 흐름 요약, 실행가능한 조언 3개, 단정 표현 금지
  * 비용 절감: 프런트에서 직접 호출(서명/레이트리밋은 서버)

# 5) 배포/운영

* **프런트**: Vercel
* **백엔드**: Render/Fly.io/Cloud Run(무료/저비용)
* **이미지 서빙**: 프런트가 `img` URL 직접 로드(백엔드는 URL만 전달)
* **운영 체크**: CORS, Rate-limit(slowapi), 로그(PII 주의), 헬스체크, 에러 핸들링
* **형상관리**: 모노레포기반 작업, 더좋은 방법있으면 진행가능.
'마지막 액션
Cloudflare
새 Pages 프로젝트를 tarot-front 레포로 연결
GitHub Secrets 설정:
CF_API_TOKEN, CF_ACCOUNT_ID, NEXT_PUBLIC_API_BASE_URL(백엔드 Render URL)
배포 트리거 후 Pages 도메인을 CORS에 추가(백엔드 CORS_ORIGINS)'


# 6) 폴더/레포 템플릿

```
/tarot-front (Next.js)
  /app (pages or app router)
  /components
  /lib
  /public/cards (필요 시)
  /styles
  .env.local (API_BASE_URL)

# API
/tarot-api (FastAPI)
  /app
    /core (config/logging/deps)
    /routers (health/cards/reading)
    /schemas (reading/cards)
    /services (deck_loader/reading_service)
    /utils (rand)
    main.py
  /data/tarot-images.json
  requirements.txt / Dockerfile / docker-compose.yml
```

# 7) 품질/확장 포인트

* **테스트**: FastAPI TestClient로 e2e 최소 3건(health/reading happy-path/seed 재현성)
* **관측성**: 구조화 로깅, 요청 ID, 에러 스택
* **i18n**: 카드 의미/해석 다국어 확장 대비(키 기반)
* **A/B**: 역방향 사용 여부, 솔루션 카드 강조 방식 실험
* **성능**: 데이터 로컬 캐시(@lru\_cache), 프런트 정적 최적화

# 8) 법·라이선스

* RWS 원본 스캔(퍼블릭 도메인) 사용 → **페이지 하단 출처 문구** 삽입(예의+분쟁 예방)
* 외부 생성 이미지 사용 시 각 라이선스 재확인

---

## 실행 계획(타임라인 제안)

* 레포 2개 생성(`tarot-front`, `tarot-api`)
* FastAPI 골격 생성 + `tarot-images.json` 배치 + `/reading` 동작 확인
* Next.js 프로젝트 init + 폼(UI 초안) + API 호출 연동

* 카드 애니메이션/레이아웃(스프레드) 완성
* 정/역방향 표기 + 상세패널
* 결과 저장/공유(간단 이미지 캡처 or 텍스트 복사)

* Supabase 붙여 리딩 기록 저장(익명 세션 기준)
* 기본 분석(페이지뷰/리딩수/완료율) + 간단 GA4
* 에러/성능 로그 정리, 배포 자동화

* LLM 해석 API 추가
* 결제/광고/커뮤니티 기능
* 오늘의 운세/데일리 카드 위젯

---
