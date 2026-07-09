# 프로젝트 배경 및 작업 맥락

다른 PC/새 대화에서 이 프로젝트를 이어갈 때 빠르게 맥락을 파악하기 위한 요약 문서입니다.

## 이 앱이 하는 일

헬스장·피트니스 센터 마케팅·상담용 콘텐츠(블로그 글 / 운동·식단 통합 프로그램)를 자동 생성하는 FastAPI 기반 웹앱입니다.

- 텍스트: OpenAI `gpt-5.4-mini` 사용
- 이미지: OpenAI `gpt-image-2` 사용 (블로그 글 전용, 운동·식단 통합 프로그램은 이미지 생성 없음)
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

   이 마커 형식은 `generation_type == "blog_post"` 전용입니다. 운동 프로그램/식단 가이드는 이 마커를 쓰지 않는 순수 텍스트입니다 (9번 항목 참고).

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

9. **생성 유형(`generation_type`) 추가**

   기존 블로그 글 생성 기능은 그대로 두고, 같은 화면·같은 `/api/generate-gym` 엔드포인트 안에 운동 프로그램/식단 가이드 생성을 추가했습니다.

   - `generation_type` 값: `blog_post`(기본값) / `exercise_program` / `diet_guide`
   - 요청에 `generation_type`이 없으면 항상 `blog_post`로 처리되어 기존 클라이언트 호출이 그대로 작동합니다.
   - `blog_post`는 기존 로직(`build_system_prompt`, `generate_blog_post`, `COMMON_RULES`/`IMAGE_RULES`/`TRAINER_ADDENDUM`/`GENERAL_ADDENDUM`, 카드뉴스 이미지 생성) 그대로 사용합니다. `app/main.py`의 `_generate_blog_post` 함수가 이 로직을 감싸고 있을 뿐 내용은 바뀌지 않았습니다.
   - `exercise_program`/`diet_guide`는 블로그 글 마커("제목 : " 등)를 쓰지 않는 순수 텍스트(900~1,300자)이고, 완전히 별도의 프롬프트(`build_exercise_program_prompt`/`build_diet_guide_prompt`, `app/prompts.py`)와 별도의 생성 함수(`generate_exercise_program`/`generate_diet_guide`, `app/openai_client.py`)를 씁니다. 이미지는 생성하지 않습니다(`images=[]`, `image_plan_text=""`).
   - 응답 스키마는 `GenerateGymResponse`를 그대로 재사용합니다(`images`가 빈 배열, `image_plan_text`가 빈 문자열일 뿐 구조는 동일).
   - **의도적으로 `Literal`이 아니라 `str`인 필드**: `GenerateGymRequest.generation_type`은 `str`입니다. `Literal`로 하면 FastAPI/Pydantic이 알 수 없는 값을 라우트 진입 전에 422로 걸러버려서, "알 수 없는 `generation_type`이면 400을 반환한다"는 요구사항을 `app/main.py`에서 구현할 기회 자체가 없어집니다. 반면 `PostSummary`/`PostDetail`의 `generation_type`은 우리 코드가 DB에 쓴 값만 읽으므로 `Literal`을 그대로 씁니다.
   - **프론트엔드**: `app/static/index.html`에 "생성 유형" 라디오(블로그 글/운동 프로그램/식단 가이드)를 추가했습니다. 블로그 글이 아니면 컨셉 영역과 카드뉴스 이미지 체크박스를 숨기고 `generate_images`를 강제로 `false`로 보냅니다. 결과 렌더링은 기존 `renderArticle`(블로그 글 전용, 마커 매칭 기반)을 건드리지 않고, 순수 텍스트용 `renderPlainContent`(pre-wrap으로 그대로 출력)를 새로 추가해 분기했습니다. 저장된 글 목록에는 `[블로그 글]`/`[운동 프로그램]`/`[식단 가이드]` 라벨이 붙습니다.
   - **SQLite 마이그레이션**: 이 기능 이전에 만들어진 로컬 `data/posts.db`에는 `generation_type` 컬럼이 없습니다. `SqlitePostRepository.init()`이 `CREATE TABLE IF NOT EXISTS` 직후 `PRAGMA table_info(posts)`로 컬럼 존재 여부를 확인하고, 없으면 `ALTER TABLE posts ADD COLUMN generation_type TEXT DEFAULT 'blog_post'`를 실행합니다. 기존 저장 글은 전부 `blog_post`로 간주됩니다. 실제 운영 중이던 `data/posts.db`(저장 글 14건)에 대해 이 마이그레이션을 실행해 데이터 손실 없이 검증했습니다.

   > `exercise_program`/`diet_guide`는 10번 항목에서 `fitness_plan`으로 대체되어 UI에서 더 이상 주요 선택지가 아닙니다. 아래 10번 항목을 함께 참고하세요.

10. **`fitness_plan`(운동·식단 통합 프로그램) 추가 — `exercise_program`/`diet_guide` 대체**

   9번 항목의 `exercise_program`/`diet_guide`는 운동과 식단을 각각 따로 생성해서, 실제 회원에게 전달할 수 있는 하나로 연결된 프로그램이 되지 못하는 문제가 있었습니다. 그래서 회원의 인바디/기본 데이터를 입력받아 운동과 식단을 하나의 목적(다이어트/근성장/린매스업)으로 연결해 한 번에 생성하는 `fitness_plan`을 새로 추가하고, UI의 주요 선택지를 블로그 글 / 운동·식단 통합 프로그램 2개로 정리했습니다.

   - `generation_type` 값에 `fitness_plan`이 추가되어 현재는 `blog_post`(기본값) / `fitness_plan` / `exercise_program` / `diet_guide` 네 가지입니다. UI 라디오는 `blog_post`/`fitness_plan` 둘만 노출하고, `exercise_program`/`diet_guide`는 과거 저장 글 상세 조회 호환용으로만 스키마·백엔드에 남아 있습니다(새로 생성할 방법은 UI에 없음).
   - `blog_post` 로직(`_generate_blog_post`, `build_system_prompt`, `generate_blog_post`, 카드뉴스 이미지 생성)은 이번에도 전혀 건드리지 않았습니다.
   - `fitness_plan` 전용 요청 필드(`app/schemas.py`): `member_gender_age`, `member_weight`, `member_muscle_mass`, `member_body_fat`, `member_bmr`, `member_tdee`, `member_available_days`, `member_injury_notes`, `member_goal_type`(예: "A 타입(다이어트)" / "B 타입(근성장)" / "C 타입(린매스업)"). 전부 `Optional[str]`이며 `fitness_plan`이 아닌 다른 generation_type에서는 무시됩니다.
   - 전용 프롬프트 `FITNESS_PLAN_RULES` / `build_fitness_plan_prompt()`(`app/prompts.py`)는 COMMON_RULES/IMAGE_RULES와 완전히 무관하며, 블로그 마커·홍보 유도 문장·네이버 블로그식 도입부를 명시적으로 금지합니다. 결과는 회원 데이터 요약 → 목적 설정 → 식단 조건·하루 총량 가이드(TDEE 기준 칼로리, 체중 기준 단백질 목표, 탄단지 비율) → 하루 식단 예시 → 요일별 운동 프로그램(마크다운 table) → 트레이너 피드백 가이드 → 실전 체크리스트 순서로 구성되며, 분량은 1,800~2,800자입니다.
   - 전용 생성 함수 `generate_fitness_plan`(`app/openai_client.py`)은 `FITNESS_PLAN_SCHEMA`(content 단일 필드)를 쓰고, 분량 보정 로직은 `_generate_short_text`에 `min_chars`/`max_chars` 인자를 추가해 재사용했습니다(`exercise_program`/`diet_guide`의 900~1,300자 기본값은 그대로 유지).
   - 전용 user message `build_fitness_plan_user_message(req)`(`app/main.py`)는 기존 `build_user_message`("블로그 글을 작성해 주세요" 문구 포함)를 재사용하지 않고 별도로 만들었습니다. 시설 정보/키워드는 각각 "시설 참고 정보"/"프로그램 방향 참고값"으로, 개별 조건과 회원 데이터 9개 필드를 함께 담아 전달합니다.
   - `repository.py`는 수정하지 않았습니다 — `generation_type`이 이미 일반 `str`로 저장/조회되고 있어서 `"fitness_plan"` 값도 별도 변경 없이 그대로 저장됩니다.
   - **프론트엔드**: "생성 유형" 라디오를 블로그 글 / 운동·식단 통합 프로그램 2개로 줄이고, `fitness_plan` 선택 시에만 보이는 회원 데이터 입력 영역(`#fitnessPlanSection`)을 추가했습니다. 시설 정보/키워드/개별 조건 라벨과 placeholder는 `generation_type`에 따라 JS로 바뀝니다(`FIELD_LABELS`). 컨셉/카드뉴스 이미지 체크박스/트레이너 섹션은 `blog_post`가 아니면 숨깁니다. 결과 렌더링은 `blog_post`만 기존 `renderArticle`을 쓰고, 그 외(`fitness_plan` 포함 모든 값)는 기존에 추가해 둔 `renderPlainContent`로 처리하도록 되어 있어 별도 분기 추가 없이 자연스럽게 커버됩니다. 저장 목록 라벨에 `fitness_plan: "운동·식단 통합 프로그램"`을 추가했고, `exercise_program`/`diet_guide` 라벨은 과거 저장 글 표시를 위해 그대로 남겨뒀습니다.

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
