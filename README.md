# 헬스장 & 피트니스 블로그 생성기

헬스장/피트니스 센터 마케팅용 네이버 블로그 스타일 글과 카드뉴스 이미지를 자동으로 생성하는 FastAPI 백엔드입니다. OpenAI로 블로그 본문과 카드뉴스 이미지(표지 1장 + 내지 1장)를 함께 생성하고, 별도 프론트엔드 빌드 없이 바로 써볼 수 있는 테스트 화면(`/ui/`)을 제공합니다.

## 주요 기능

- **블로그 글 생성**: "제목 : ", "인용구) ", "썸네일", "시설위치지도사진" 마커를 포함한 고정 형식, 1,500~1,600자 분량 자동 조절
- **어투/톤**: 해요체 중심, 시설 홍보 뉘앙스를 살짝 곁들인 정보성 글 (표시광고법 위반 과장 표현 금지)
- **컨셉 선택**: 일반(`default`) / 트레이너 1인칭(`trainer`)
- **카드뉴스 이미지 자동 생성**: 표지 1장 + 내지 1장(1:1 비율), 흰 배경·포인트 컬러 1개·체크포인트 박스 형태의 밝고 깔끔한 정보형 디자인, 추천 타이틀/본문 문구가 이미지 안에 실제로 렌더링됨
- **글 저장/조회/삭제**: 로컬 개발 환경에서는 SQLite에 저장 (운영 환경에서는 자동으로 비활성화, 아래 참고)
- **아임웹 연동(수동)**: 아임웹 Open API가 게시판 자동 등록을 지원하지 않아, 생성 결과를 복사해 아임웹 게시판 글쓰기 페이지에 붙여넣는 수동 흐름을 안내

## 기술 스택

- FastAPI + Pydantic
- OpenAI API — 텍스트: `gpt-5.4-mini`, 이미지: `gpt-image-2`
- SQLite (로컬 개발용 저장소)
- 순수 HTML/JS 테스트 페이지 (`app/static/index.html`, 별도 npm 빌드 불필요)

## 시작하기

### 1. 준비물

- Python 3.10 이상
- OpenAI API 키 ([platform.openai.com](https://platform.openai.com)에서 발급, 결제 수단 등록 및 사용 한도 확인 필요)

### 2. 설치

```bash
python -m venv .venv
.venv\Scripts\activate        # Windows
# source .venv/bin/activate   # macOS/Linux

pip install -r requirements.txt
```

### 3. 환경변수 설정

`.env.example`을 복사해 `.env`를 만들고 값을 채워주세요.

```bash
copy .env.example .env        # Windows
# cp .env.example .env        # macOS/Linux
```

| 변수 | 필수 | 설명 |
|---|---|---|
| `OPENAI_API_KEY` | 필수 | OpenAI API 키 |
| `FRONTEND_ORIGINS` | 선택 | CORS 허용 origin (쉼표로 구분, 기본값 `http://localhost:3000`) |
| `APP_ENV` | 선택 | `production`으로 설정하면 저장소가 비활성화됨(운영 환경 시뮬레이션용) |
| `IMWEB_BOARD_WRITE_URL` | 선택 | 아임웹 게시판 글쓰기 페이지 URL. 설정 시 UI에 "게시판 글쓰기 페이지로 이동" 버튼이 노출됨 |

### 4. 로컬 서버 실행

```bash
uvicorn app.main:app --reload --port 8000
```

브라우저에서 `http://localhost:8000/ui/` 접속하면 바로 테스트할 수 있습니다.

## 사용 방법 (`/ui/` 테스트 화면)

1. **시설 정보**: 센터명, 지역, 시설 특징 등을 자유 서술로 입력
2. **키워드**: 제목/본문에 반영할 검색 키워드 (예: "강남 PT")
3. **개별 조건**: 이번 글에서 강조하고 싶은 조건(예: "체지방 감량과 근력 운동에 초점, 초보자 대상")
4. **컨셉**: 일반 / 트레이너 1인칭 중 선택
5. **카드뉴스 이미지 생성 여부** 체크 후 "블로그 글 생성하기" 클릭
   - 이미지까지 생성하면 시간이 더 걸립니다(수십 초~수분, 드물게 더 오래 걸릴 수 있음)
6. 결과 화면에서
   - **글 복사**: 생성된 글 전체를 클립보드로 복사
   - **이미지 저장**: 카드뉴스 이미지를 파일로 다운로드
   - **아임웹 게시판 글쓰기 페이지로 이동**: `IMWEB_BOARD_WRITE_URL` 설정 시에만 노출, 클릭하면 아임웹 글쓰기 페이지가 새 탭으로 열림 → 복사한 글/이미지를 직접 붙여넣기
7. **저장된 글 목록 보기**: 이전에 생성한 글 목록 확인, 클릭 시 상세 보기, 각 항목의 "삭제" 버튼으로 개별 삭제 가능 (로컬 SQLite 저장 글만 대상)

## API 개요

| 메서드 | 경로 | 설명 |
|---|---|---|
| `POST` | `/api/generate-gym` | 블로그 글 + 카드뉴스 이미지 생성 |
| `GET` | `/api/posts` | 저장된 글 목록 조회 |
| `GET` | `/api/posts/{id}` | 저장된 글 상세 조회 |
| `DELETE` | `/api/posts/{id}` | 저장된 글 삭제 (로컬 SQLite 전용) |
| `GET` | `/api/config` | 프론트엔드용 설정값(저장 기능 사용 가능 여부, 아임웹 링크) 조회 |

## 배포 (Vercel)

`vercel.json`이 포함되어 있어 별도 설정 없이 배포할 수 있습니다.

```bash
npm install -g vercel
vercel login
vercel env add OPENAI_API_KEY   # Production/Preview/Development 모두 체크
vercel --prod
```

Vercel은 런타임에 `VERCEL=1`을 자동으로 설정하는데, 이 값을 감지해 저장소가 자동으로 비활성화됩니다(서버리스 환경은 파일시스템이 호출 간 유지되지 않아 SQLite를 쓸 수 없기 때문). 운영 환경에서는 "저장된 글 목록" 기능 대신 "글 복사" 흐름을 사용해주세요.

## 알아두면 좋은 점

- 이미지 생성 소요 시간은 OpenAI API 자체의 특성상 편차가 큽니다(수십 초~수분, 드물게 더 오래 걸릴 수 있음). 표지/내지 이미지는 병렬로 요청해 대기 시간을 줄였습니다.
- `429 insufficient_quota` 오류가 뜨면 코드 문제가 아니라 OpenAI 계정의 결제/사용 한도 문제입니다. [OpenAI 대시보드](https://platform.openai.com/settings/organization/billing/overview)에서 확인해주세요.
- 더 자세한 설계 배경과 의사결정 이력은 [CONTEXT.md](CONTEXT.md)를 참고해주세요.
