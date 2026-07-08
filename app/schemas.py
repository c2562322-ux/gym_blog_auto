from typing import Any, List, Literal, Optional

from pydantic import BaseModel, Field

Concept = Literal["default", "trainer"]


class GenerateGymRequest(BaseModel):
    gym_info: str = Field(..., description="센터명, 지역, 시설 특징 등 헬스장 정보")
    keyword: str = Field(..., description="지역 + 헬스장/PT/운동명 키워드")
    concept: Concept = Field("default", description="글 작성 컨셉 (default | trainer)")
    priors: Optional[Any] = Field(None, description="UI에서 선택한 개별 조건")
    model: Optional[str] = Field(None, description="텍스트 생성 모델 (기본: gpt-5.4-mini)")
    image_model: Optional[str] = Field(None, description="이미지 생성 모델 (기본: gpt-image-2)")
    generate_images: bool = Field(True, description="대표/본문 이미지 자동 생성 여부")


class ImageAsset(BaseModel):
    type: Literal["대표 이미지", "본문 이미지"]
    insert_position: str
    recommended_title: Optional[str] = None  # 대표 이미지(카드뉴스 표지)에만 사용
    recommended_body_text: Optional[str] = None  # 본문 이미지(카드뉴스 내지)에만 사용
    prompt: str
    filename: str
    alt: str
    image_base64: Optional[str] = None
    image_url: Optional[str] = None
    image_error: Optional[str] = None


class GenerateGymResponse(BaseModel):
    id: Optional[int] = Field(None, description="저장소가 없는 환경(예: Vercel 운영)에서는 null")
    content: str
    content_length: int
    images: List[ImageAsset]
    image_plan_text: str


class AppConfig(BaseModel):
    storage_available: bool = Field(..., description="글 목록/상세 저장·조회 기능 사용 가능 여부")
    board_write_url: Optional[str] = Field(None, description="아임웹 게시판 글쓰기 페이지 URL (설정된 경우)")


class PostSummary(BaseModel):
    id: int
    created_at: str
    keyword: str
    concept: str
    title: str
    content_length: int


class PostDetail(BaseModel):
    id: int
    created_at: str
    keyword: str
    concept: str
    title: str
    content: str
    content_length: int
    images: List[ImageAsset]
    image_plan_text: str
