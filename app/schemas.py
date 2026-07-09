from typing import Any, List, Literal, Optional

from pydantic import BaseModel, Field

Concept = Literal["default", "trainer"]

#: blog_post = 기존 블로그 글(카드뉴스 이미지 포함 가능).
#: fitness_plan = 회원 인바디/기본 데이터 기반 1주일 운동·식단 통합 프로그램 (텍스트 전용).
#: exercise_program / diet_guide는 fitness_plan 도입 이전 값으로, UI에서는 더 이상 주요 선택지로
#: 노출하지 않고 과거 저장 글 호환 조회용으로만 남겨둔다.
#: 기존 요청과의 호환을 위해 요청에 값이 없으면 항상 "blog_post"로 취급한다.
GenerationType = Literal["blog_post", "fitness_plan", "exercise_program", "diet_guide"]


class GenerateGymRequest(BaseModel):
    gym_info: str = Field(..., description="센터명, 지역, 시설 특징 등 헬스장 정보")
    keyword: str = Field(..., description="지역 + 헬스장/PT/운동명 키워드")
    # 의도적으로 Literal이 아니라 str이다. Literal이면 FastAPI/Pydantic이 잘못된 값을
    # 라우트 진입 전에 422로 걸러버려서, main.py에서 원하는 "알 수 없는 generation_type
    # -> 400" 응답을 만들 기회 자체가 없어진다. 검증은 main.py의 명시적 분기가 담당한다.
    generation_type: str = Field(
        "blog_post", description="생성 유형 (blog_post | fitness_plan | exercise_program | diet_guide), 기본값 blog_post"
    )
    concept: Concept = Field("default", description="글 작성 컨셉 (default | trainer, blog_post 전용)")
    priors: Optional[Any] = Field(None, description="UI에서 선택한 개별 조건")
    trainer_name: Optional[str] = Field(None, description="트레이너 1인칭 컨셉일 때 사용할 트레이너 이름")
    trainer_features: Optional[str] = Field(None, description="트레이너 1인칭 컨셉일 때 반영할 해당 트레이너만의 특징")
    model: Optional[str] = Field(None, description="텍스트 생성 모델 (기본: gpt-5.4-mini)")
    image_model: Optional[str] = Field(None, description="이미지 생성 모델 (기본: gpt-image-2)")
    generate_images: bool = Field(True, description="대표/본문 이미지 자동 생성 여부 (blog_post에만 적용)")

    # ---- fitness_plan 전용 회원 데이터 (그 외 generation_type에서는 무시된다) ----
    member_gender_age: Optional[str] = Field(None, description="회원 성별/나이 (예: 남성 / 31세)")
    member_weight: Optional[str] = Field(None, description="회원 체중 (예: 75kg)")
    member_muscle_mass: Optional[str] = Field(None, description="회원 골격근량 (예: 32kg)")
    member_body_fat: Optional[str] = Field(None, description="회원 체지방률 (예: 24%)")
    member_bmr: Optional[str] = Field(None, description="회원 기초대사량 BMR (예: 1,600 kcal)")
    member_tdee: Optional[str] = Field(None, description="회원 활동대사량 TDEE (예: 2,300 kcal)")
    member_available_days: Optional[str] = Field(None, description="회원 주간 출석 가능 횟수/요일 (예: 주 3회 / 월,수,금)")
    member_injury_notes: Optional[str] = Field(None, description="회원 부상 이력 및 식습관 등 특이사항")
    member_goal_type: Optional[str] = Field(
        None, description="회원 선택 목적 (예: A 타입(다이어트) | B 타입(근성장) | C 타입(린매스업))"
    )


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
    # 트레이너 1인칭(concept == "trainer")으로 저장된 글에서 실제 사용된 트레이너 이름.
    # 그 외 글이나, 이 필드가 생기기 전에 저장된 과거 트레이너 글은 None이다.
    trainer_name: Optional[str] = None
    generation_type: GenerationType = "blog_post"
    title: str
    content_length: int


class PostDetail(BaseModel):
    id: int
    created_at: str
    keyword: str
    concept: str
    trainer_name: Optional[str] = None
    generation_type: GenerationType = "blog_post"
    title: str
    content: str
    content_length: int
    images: List[ImageAsset]
    image_plan_text: str
