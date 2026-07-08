# 프로젝트 배경 및 작업 맥락

다른 PC/새 대화에서 이 프로젝트를 이어갈 때 빠르게 맥락을 파악하기 위한 요약 문서입니다.

## 이 앱이 하는 일

헬스장·피트니스 센터 마케팅용 네이버 블로그 스타일 글과 카드뉴스 이미지를 자동 생성하는 FastAPI 백엔드입니다.

- 텍스트: OpenAI `gpt-5.4-mini` (chat.completions, json_schema strict 모드)
- 이미지: OpenAI `gpt-image-2`
- 테스트 UI: `/ui/` (React/npm 없이 순수 HTML/JS, `app/static/index.html`)

## 주요 설계 결정과 이유

1. **왜 OpenAI인가**: 처음엔 Anthropic Claude로 시작했으나, 사용자가 명시적으로 OpenAI로 전환 요청 (`app/openai_client.py`가 그 결과물, `app/claude_client.py`는 삭제됨).

2. **글 형식이 고정된 이유**: 사용자가 실제로 쓰는 네이버 블로그 템플릿 그대로여야 해서 "제목 : ", "인용구) ", "썸네일", "시설위치지도사진" 마커를 리터럴 텍스트로 강제함 (`app/prompts.py`의 `COMMON_RULES`). 마크다운 금지, 분량 1,500~1,600자 강제(초과/부족 시 자동 보정 + 안전 트렁케이션, `app/openai_client.py`의 `generate_blog_post`).

3. **어투/톤 변경 이력**: 처음엔 "~습니다"체 정보성 글 → 이후 해요체 중심 + 시설 홍보 뉘앙스를 살짝 넣도록 변경 (`[어투]`, `[시설 홍보 반영]` 블록). 표시광고법 위반 표현(과장·단정·최상급)은 항상 금지.

4. **카드뉴스 이미지 스타일 변천사** (`IMAGE_RULES`):
   - 초기: 이미지 0~2장 자유 → 이후 정확히 2장 고정(표지+내지)
   - 텍스트 없는 여백 이미지 → 추천 타이틀/본문 문구를 이미지 안에 실제로 렌더링하도록 변경
   - 일러스트/애니메이션풍 → 실사(사진) 스타일로 변경
   - **최종(현재)**: 실사 사진이 프레임을 꽉 채우는 어두운 "체육관 포스터" 스타일을 버리고, **흰 배경 + 파란/초록 포인트 컬러 1개 + 체크포인트 박스 + 심플 아이콘 + 사진은 한쪽에 작게** 배치하는 밝고 clean한 정보형 카드뉴스 스타일로 최종 확정. 도메인별(헬스장/의료/웰니스) 변수 구조도 프롬프트 안에 문서화되어 있음.

5. **저장소 추상화 (`app/repository.py`)**: Vercel 서버리스 환경은 파일시스템이 호출 간에 유지되지 않아 SQLite를 못 씀. `PostRepository` 추상 클래스를 만들고, 로컬 개발은 `SqlitePostRepository`(`data/posts.db`), 운영(Vercel)은 `NullPostRepository`(무저장, 저장 관련 API가 501/no-op)로 `get_post_repository()`가 `VERCEL` 환경변수를 보고 자동 분기함.

6. **아임웹(Imweb) 자동 게시 미구현**: 아임웹 Open API 전체 스펙을 조사한 결과 게시판 글쓰기 API가 없음(확인 완료, 재조사 불필요). 그래서 `ImwebPostRepository`는 만들지 않았고, 대신 `IMWEB_BOARD_WRITE_URL` 환경변수로 게시판 글쓰기 페이지 링크만 제공 → 사용자가 "글 복사" 후 수동으로 붙여넣는 흐름.

7. **글 삭제 기능**: `DELETE /api/posts/{id}`는 SQLite 개발용 저장 글만 대상. 이미지가 별도 파일이 아니라 `images_json` 컬럼에 함께 저장되므로 행 삭제만으로 이미지도 같이 정리됨. 아임웹에 이미 발행된 글과는 구조적으로 무관(연결점 자체가 없음).

## 로컬 실행 방법

```
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env   # 그 다음 .env에 실제 OPENAI_API_KEY 채워넣기
uvicorn app.main:app --reload --port 8000
```

브라우저에서 `http://localhost:8000/ui/` 접속.

## Vercel 배포

`vercel.json`이 이미 준비되어 있음 (`@vercel/python` 빌더, `app/static` 포함 설정).

- 환경변수 `OPENAI_API_KEY` 필수 (Vercel 대시보드 또는 `vercel env add`로 설정)
- Vercel은 `VERCEL=1`을 자동 설정하므로 배포 즉시 `NullPostRepository`로 전환됨 (별도 설정 불필요)
- `IMWEB_BOARD_WRITE_URL`은 선택 사항

## 알려진 이슈 / 주의사항

- 이미지 생성 지연시간 편차가 매우 큼 (45초~20분 이상 관찰됨). 코드 문제가 아니라 OpenAI API 자체의 변동성이며, 병렬 생성(`ThreadPoolExecutor`)으로 표지+내지 동시 요청해서 그나마 완화함.
- `OPENAI_API_KEY` 쿼터 초과 시 429 `insufficient_quota` 에러 발생 — 이건 OpenAI 계정 결제/한도 문제이며 코드로 해결 불가, https://platform.openai.com 에서 직접 확인 필요.
- `.venv/`는 이 PC의 절대경로가 박혀 있어서(`.claude/launch.json` 포함) 다른 PC로 폴더를 그대로 복사하면 안 되고, 새 PC에서 새로 `python -m venv .venv`로 만들어야 함.
- 이 저장소는 원래 `C:\Users\wldjs` 홈 디렉터리 전체를 git 루트로 잘못 잡고 있었던 적이 있음(커밋 없는 빈 상태였어서 안전하게 삭제하고 `blog_auto` 폴더 전용으로 재초기화함). 다른 PC에서 git 작업할 때도 반드시 프로젝트 폴더 안에서 `git init`했는지 확인할 것.
