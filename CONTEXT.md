# 프로젝트 배경 및 작업 맥락

다른 PC/새 대화에서 이 프로젝트를 이어갈 때 빠르게 맥락을 파악하기 위한 요약 문서입니다.

## 이 앱이 하는 일

헬스장·피트니스 센터 마케팅용 네이버 블로그 스타일 글과 카드뉴스 이미지를 자동 생성하는 FastAPI 기반 웹앱입니다.

- 텍스트: OpenAI `gpt-5.4-mini` 사용
- 이미지: OpenAI `gpt-image-2` 사용
- 테스트/사용 UI: 기본 경로 `/`
- 기존 호환 경로: `/ui/`
- 별도 React/npm 프론트엔드 없이 순수 HTML/JS 사용
- UI 파일 위치: `app/static/index.html`

## 주요 설계 결정과 이유

1. **왜 OpenAI인가**

   처음엔 Anthropic Claude로 시작했으나, 사용자가 명시적으로 OpenAI로 전환 요청했습니다.

   현재 OpenAI 관련 로직은 `app/openai_client.py`에 있습니다.

   기존 Claude 관련 파일인 `app/claude_client.py`는 삭제되었습니다.

2. **글 형식이 고정된 이유**

   사용자가 실제로 쓰는 네이버 블로그 템플릿 그대로여야 해서 아래 마커를 리터럴 텍스트로 강제합니다.
   - `제목 : `
   - `인용구) `
   - `썸네일`
   - `시설위치지도사진`

   관련 규칙은 `app/prompts.py`의 `COMMON_RULES`에 있습니다.

   마크다운은 금지하고, 분량은 공백 포함 1,500~1,600자 기준으로 맞춥니다.

   글이 초과되거나 부족할 경우 자동 보정 및 안전 트렁케이션 처리가 `app/openai_client.py`의 `generate_blog_post`에 들어 있습니다.

3. **어투/톤 변경 이력**

   처음에는 `~습니다` 중심의 정보성 글이었으나, 이후 해요체 중심으로 변경했습니다.

   현재 목표 문체는 아래와 같습니다.
   - `~해요`
   - `~인데요`
   - `~하죠`
   - `~있어요`
   - `~볼 수 있어요`

   정보성 글을 유지하되, 시설 홍보 뉘앙스를 자연스럽게 넣습니다.

   단, 표시광고법 위반 가능성이 있는 과장·단정·최상급 표현은 항상 금지합니다.

4. **카드뉴스 이미지 스타일 변천사**

   관련 규칙은 `app/prompts.py`의 `IMAGE_RULES`에 있습니다.

   변경 이력은 아래와 같습니다.
   - 초기: 이미지 0~2장 자유
   - 이후: 정확히 2장 고정, 표지 1장 + 내지 1장
   - 초기 이미지: 텍스트 없는 여백 이미지
   - 이후: 추천 타이틀/본문 문구를 이미지 안에 실제로 렌더링하도록 변경
   - 중간 결과: 일러스트/애니메이션풍
   - 이후: 실사 사진 스타일로 변경
   - 최종 현재 방향:
     - 어두운 체육관 포스터 스타일 금지
     - 흰 배경 또는 아주 연한 배경
     - 파란/초록 계열 포인트 컬러 1개 중심
     - 체크포인트 박스
     - 심플 아이콘
     - 사진은 한쪽에 작게 배치
     - 밝고 clean한 정보형 카드뉴스 스타일

   도메인별 헬스장/의료/웰니스 변수 구조도 프롬프트 안에 문서화되어 있습니다.

5. **UI 라우팅 변경**

   기존에는 UI가 `/ui/`에서만 열렸습니다.

   Vercel 배포 후 기본 주소 `/`에 접속했을 때 `{"detail":"Not Found"}`가 뜨는 문제가 있어, 현재는 `/`에서 바로 UI가 열리도록 변경했습니다.

   현재 경로 구조는 아래와 같습니다.
   - `/` : 최종 기본 UI 경로
   - `/ui/` : 기존 호환용 UI 경로
   - `/api/...` : API 경로

   구현 방식:
   - `app/static/index.html`을 정적 UI로 사용
   - `app.mount("/ui", StaticFiles(...))`로 기존 `/ui/` 경로 유지
   - 모든 API 라우트 정의가 끝난 뒤 파일 마지막에 `app.mount("/", StaticFiles(...))`를 배치
   - 이렇게 해야 `/api/...` 요청은 API로 처리되고, `/` 요청은 UI로 처리됨

   `app.mount("/")`는 반드시 API 라우트들보다 아래, 파일 마지막 쪽에 있어야 합니다.

6. **저장소 추상화**

   관련 파일은 `app/repository.py`입니다.

   Vercel 서버리스 환경은 파일시스템이 호출 간에 유지되지 않기 때문에 SQLite를 운영용 저장소로 사용할 수 없습니다.

   그래서 `PostRepository` 추상 클래스를 만들었습니다.

   저장소 분기 구조:
   - 로컬 개발: `SqlitePostRepository`
   - 저장 위치: `data/posts.db`
   - 운영/Vercel: `NullPostRepository`
   - Vercel 환경에서는 `VERCEL` 환경변수를 감지해 자동으로 저장소 비활성화

7. **아임웹 자동 게시 미구현**

현재 확인한 범위에서는 아임웹 일반 게시판에 외부 서버가 자동으로 글을 등록하는 API를 운영 구조에 바로 적용하기 어렵다고 판단했습니다.

따라서 `ImwebPostRepository`는 만들지 않았고, 현재 버전에서는 수동 저장 흐름을 기본으로 합니다.

대신 `IMWEB_BOARD_WRITE_URL` 환경변수로 아임웹 게시판 글쓰기 페이지 링크만 제공합니다.

운영 흐름은 아래와 같습니다.

- 앱에서 글과 이미지 생성
- 글 복사
- 이미지 저장
- 아임웹 게시판 글쓰기 페이지로 이동
- 직접 붙여넣기
- 아임웹 게시판에서 최종 저장

8. **글 삭제 기능**

   `DELETE /api/posts/{id}`는 SQLite 개발용 저장 글만 대상으로 합니다.

   이미지가 별도 파일이 아니라 `images_json` 컬럼에 함께 저장되므로, SQLite 행 삭제만으로 연결된 이미지 정보도 같이 정리됩니다.

   아임웹에 이미 발행된 글과는 구조적으로 무관합니다.

   즉, 앱에서 SQLite 저장 글을 삭제해도 아임웹 게시판 글은 삭제되지 않습니다.

   아임웹 게시판 글의 수정/삭제는 아임웹 게시판에서 직접 처리합니다.

## 로컬 실행 방법

```
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env   # 그 다음 .env에 실제 OPENAI_API_KEY 채워넣기
uvicorn app.main:app --reload --port 8000
```

브라우저에서 `http://localhost:8000/` 접속.

기존 호환 경로로 `http://localhost:8000/ui/`도 사용할 수 있습니다.

## Vercel 배포

배포 후 기본 주소 `/`에서 바로 UI가 열려야 합니다.

예시:
`https://프로젝트명.vercel.app/`

기존 호환 경로:
`https://프로젝트명.vercel.app/ui/`

API 확인 경로:
`https://프로젝트명.vercel.app/api/config`

`vercel.json`이 이미 준비되어 있음 (`@vercel/python` 빌더, `app/static` 포함 설정).

- 환경변수 `OPENAI_API_KEY` 필수 (Vercel 대시보드 또는 `vercel env add`로 설정)
- Vercel은 `VERCEL=1`을 자동 설정하므로 배포 즉시 `NullPostRepository`로 전환됨 (별도 설정 불필요)
- `IMWEB_BOARD_WRITE_URL`은 선택 사항

## 알려진 이슈 / 주의사항

- 이미지 생성 지연시간 편차가 매우 큼 (45초~20분 이상 관찰됨). 코드 문제가 아니라 OpenAI API 자체의 변동성이며, 병렬 생성(`ThreadPoolExecutor`)으로 표지+내지 동시 요청해서 그나마 완화함.
- `OPENAI_API_KEY` 쿼터 초과 시 429 `insufficient_quota` 에러 발생 — 이건 OpenAI 계정 결제/한도 문제이며 코드로 해결 불가, https://platform.openai.com 에서 직접 확인 필요.
- `.venv/`는 이 PC의 절대경로가 박혀 있어서(`.claude/launch.json` 포함) 다른 PC로 폴더를 그대로 복사하면 안 되고, 새 PC에서 새로 `python -m venv .venv`로 만들어야 함.
- 이 저장소는 원래 `C:\Users\wldjs` 홈 디렉터리 전체를 git 루트로 잘못 잡고 있었던 적이 있음(커밋 없는 빈 상태였어서 안전하게 삭제하고 `blog_auto` 폴더 전용으로 재초기화함). 다른 PC에서 git 작업할 때도 반드시 프로젝트 폴더 안에서 `git init`했는지 확인할 것.
