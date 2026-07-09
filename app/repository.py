"""글 저장소 추상화 (PostRepository).

로컬 개발 환경에서는 SQLite에 저장해 "저장된 글 목록" 기능을 그대로 쓸 수 있게
하고, 운영 환경(Vercel 등 서버리스)에서는 파일 저장이 호출 간에 유지되지 않으므로
저장을 시도하는 대신 그 사실을 명시적으로 드러내는 NullPostRepository를 쓴다.

아임웹 Open API(Imweb Ground API v1.0, 2026-07 기준 전체 120개 엔드포인트 조사)에는
일반 게시판 글 등록/목록/상세 조회 API가 없다 — Community 카테고리는 입력폼 조회,
Q&A 답변 등록(질문 등록 아님), 구매평 작성(실구매자만) 세 가지뿐이라 블로그 게시판
용도로 쓸 수 없다. 따라서 ImwebPostRepository는 구현하지 않는다.

나중에 실제 운영 DB(Postgres 등)를 붙이거나 아임웹에 게시판 API가 추가되면,
이 PostRepository 인터페이스를 구현하는 새 클래스만 추가하고 get_post_repository()의
분기만 바꾸면 된다 — main.py나 스키마는 건드릴 필요 없다.
"""

import json
import os
import sqlite3
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

DB_PATH = Path(__file__).parent.parent / "data" / "posts.db"


class PostRepository(ABC):
    #: 이 저장소가 실제로 데이터를 보존하는지 여부. False면 save()/list()/get()은
    #: 항상 "저장된 게 없다"는 결과를 돌려주는 안전한 무동작(no-op)이다.
    available: bool = True

    @abstractmethod
    def init(self) -> None:
        """앱 시작 시 한 번 호출되는 초기화 훅 (예: 테이블 생성)."""

    @abstractmethod
    def save(
        self,
        keyword: str,
        concept: str,
        content: str,
        images: List[Dict[str, Any]],
        image_plan_text: str,
        generation_type: str = "blog_post",
        trainer_name: Optional[str] = None,
    ) -> Optional[int]:
        """글을 저장하고 새 id를 반환한다. 저장이 불가능한 환경이면 None을 반환한다.

        generation_type을 넘기지 않는 기존 호출부는 계속 "blog_post"로 저장된다.
        trainer_name은 concept == "trainer"일 때만 의미가 있고, 그 외에는 None으로 저장된다."""

    @abstractmethod
    def list(self) -> List[Dict[str, Any]]:
        """저장된 글 요약 목록을 최신순으로 반환한다."""

    @abstractmethod
    def get(self, post_id: int) -> Optional[Dict[str, Any]]:
        """저장된 글 상세를 반환한다. 없으면 None."""

    @abstractmethod
    def delete(self, post_id: int) -> bool:
        """저장된 글을 삭제한다. 삭제됐으면 True, 원래 없었으면 False."""


def _extract_title(content: str) -> str:
    for line in content.splitlines():
        line = line.strip()
        if line.startswith("제목 : "):
            return line.replace("제목 : ", "", 1)
    stripped = content.strip()
    return stripped.splitlines()[0] if stripped else "(제목 없음)"


class SqlitePostRepository(PostRepository):
    """로컬 개발용. 파일 기반이라 Vercel 같은 서버리스 환경에서는 쓰지 않는다."""

    available = True

    def _connect(self) -> sqlite3.Connection:
        DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        return conn

    def init(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS posts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    created_at TEXT NOT NULL,
                    keyword TEXT NOT NULL,
                    concept TEXT NOT NULL,
                    title TEXT NOT NULL,
                    content TEXT NOT NULL,
                    content_length INTEGER NOT NULL,
                    images_json TEXT NOT NULL,
                    image_plan_text TEXT NOT NULL
                )
                """
            )
            self._ensure_generation_type_column(conn)
            self._ensure_trainer_name_column(conn)

    def _ensure_generation_type_column(self, conn: sqlite3.Connection) -> None:
        """CREATE TABLE IF NOT EXISTS는 이미 존재하는 테이블의 컬럼을 추가해주지 않으므로,
        generation_type 기능 이전에 만들어진 기존 posts.db에 대해 수동으로 마이그레이션한다.
        이미 컬럼이 있으면(신규 DB 포함) 아무 것도 하지 않는다."""
        columns = {row["name"] for row in conn.execute("PRAGMA table_info(posts)").fetchall()}
        if "generation_type" not in columns:
            conn.execute("ALTER TABLE posts ADD COLUMN generation_type TEXT DEFAULT 'blog_post'")

    def _ensure_trainer_name_column(self, conn: sqlite3.Connection) -> None:
        """trainer_name 기능 이전에 만들어진 posts.db를 위한 마이그레이션. 기존 트레이너 글은
        어떤 트레이너였는지 기록이 없었으므로 NULL로 남는다(기본값 없음 — 저장 목록에서
        "트레이너 1인칭"으로만 표시하는 폴백으로 처리한다)."""
        columns = {row["name"] for row in conn.execute("PRAGMA table_info(posts)").fetchall()}
        if "trainer_name" not in columns:
            conn.execute("ALTER TABLE posts ADD COLUMN trainer_name TEXT")

    def save(
        self,
        keyword: str,
        concept: str,
        content: str,
        images: List[Dict[str, Any]],
        image_plan_text: str,
        generation_type: str = "blog_post",
        trainer_name: Optional[str] = None,
    ) -> Optional[int]:
        with self._connect() as conn:
            cursor = conn.execute(
                """
                INSERT INTO posts
                    (created_at, keyword, concept, trainer_name, generation_type, title, content, content_length, images_json, image_plan_text)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    datetime.now(timezone.utc).isoformat(),
                    keyword,
                    concept,
                    trainer_name,
                    generation_type,
                    _extract_title(content),
                    content,
                    len(content),
                    json.dumps(images, ensure_ascii=False),
                    image_plan_text,
                ),
            )
            return cursor.lastrowid

    def list(self) -> List[Dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT id, created_at, keyword, concept, trainer_name, generation_type, title, content_length "
                "FROM posts ORDER BY id DESC"
            ).fetchall()
            return [self._with_generation_type(dict(row)) for row in rows]

    def get(self, post_id: int) -> Optional[Dict[str, Any]]:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM posts WHERE id = ?", (post_id,)).fetchone()
            if row is None:
                return None
            data = dict(row)
            data["images"] = json.loads(data.pop("images_json"))
            return self._with_generation_type(data)

    @staticmethod
    def _with_generation_type(data: Dict[str, Any]) -> Dict[str, Any]:
        """generation_type 컬럼 추가 이전에 저장된 행은 값이 None일 수 있으므로 blog_post로 보정한다."""
        if not data.get("generation_type"):
            data["generation_type"] = "blog_post"
        return data

    def delete(self, post_id: int) -> bool:
        # 이미지가 파일이 아니라 images_json 컬럼에 함께 저장되므로,
        # 행 하나를 지우면 글과 이미지가 한 번에 정리된다.
        with self._connect() as conn:
            cursor = conn.execute("DELETE FROM posts WHERE id = ?", (post_id,))
            return cursor.rowcount > 0


class NullPostRepository(PostRepository):
    """운영 환경(Vercel 등)용. 지속 저장소가 없다는 걸 숨기지 않고 명시적으로 드러낸다.

    아임웹 Open API가 게시판 쓰기를 지원하지 않아 자동 저장이 불가능한 동안 쓴다.
    프론트는 available=False를 보고 "게시판 글쓰기 페이지로 이동" 같은 수동 흐름을 안내한다.
    """

    available = False

    def init(self) -> None:
        pass

    def save(self, *args: Any, **kwargs: Any) -> Optional[int]:
        return None

    def list(self) -> List[Dict[str, Any]]:
        return []

    def get(self, post_id: int) -> Optional[Dict[str, Any]]:
        return None

    def delete(self, post_id: int) -> bool:
        return False


def get_post_repository() -> PostRepository:
    """Vercel은 런타임에 VERCEL=1을 자동으로 설정한다. APP_ENV=production으로도 강제 가능."""
    is_production = os.environ.get("VERCEL") == "1" or os.environ.get("APP_ENV") == "production"
    return NullPostRepository() if is_production else SqlitePostRepository()
