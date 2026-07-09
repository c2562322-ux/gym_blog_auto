import os
from pathlib import Path
from typing import Any, Dict, List, Optional

import openai
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from openai import OpenAI

from .openai_client import (
    format_image_plan_text,
    generate_blog_post,
    generate_diet_guide,
    generate_exercise_program,
    generate_fitness_plan,
    generate_images_parallel,
)
from .prompts import (
    build_diet_guide_prompt,
    build_exercise_program_prompt,
    build_fitness_plan_prompt,
    build_system_prompt,
)
from .repository import get_post_repository
from .schemas import (
    AppConfig,
    GenerateGymRequest,
    GenerateGymResponse,
    ImageAsset,
    PostDetail,
    PostSummary,
)

load_dotenv()

DEFAULT_TEXT_MODEL = "gpt-5.4-mini"
DEFAULT_IMAGE_MODEL = "gpt-image-2"

# 지점별 아임웹 게시판 글쓰기 페이지 URL. 아임웹 Open API가 게시판 글쓰기를
# 지원하지 않아 자동 등록이 불가능하므로, 생성 결과를 복사해 이 페이지에
# 직접 붙여넣는 수동 흐름을 안내하는 용도로만 쓴다. API 키/토큰이 아니라
# 사람이 클릭해서 여는 공개 페이지 링크이므로 프론트에 노출해도 안전하다.
IMWEB_BOARD_WRITE_URL = os.environ.get("IMWEB_BOARD_WRITE_URL")

app = FastAPI(title="Gym & Fitness Blog Generator")

app.add_middleware(
    CORSMiddleware,
    allow_origins=os.environ.get("FRONTEND_ORIGINS", "http://localhost:3000").split(","),
    allow_methods=["GET", "POST", "DELETE"],
    allow_headers=["*"],
)

repository = get_post_repository()
repository.init()

# OPENAI_API_KEY 환경변수에서 자동으로 인증 정보를 읽는다.
client = OpenAI()

# npm/React 없이 바로 써볼 수 있는 간단한 테스트 페이지
# 기존 /ui/ 경로도 유지한다.
STATIC_DIR = Path(__file__).parent / "static"
app.mount("/ui", StaticFiles(directory=STATIC_DIR, html=True), name="ui")


def build_user_message(
    gym_info: str,
    keyword: str,
    priors: Optional[Any],
    trainer_name: Optional[str] = None,
    trainer_features: Optional[str] = None,
) -> str:
    lines = [f"키워드: {keyword}", f"시설 정보: {gym_info}"]
    if priors:
        lines.append(f"개별 조건: {priors}")
    if trainer_name or trainer_features:
        trainer_parts = []
        if trainer_name:
            trainer_parts.append(f"이름: {trainer_name}")
        if trainer_features:
            trainer_parts.append(f"특징: {trainer_features}")
        lines.append("트레이너 정보: " + " / ".join(trainer_parts))
    lines.append("위 키워드, 시설 정보, 개별 조건을 반영하여 시스템 지침에 따라 블로그 글을 작성해 주세요.")
    return "\n".join(lines)


def build_fitness_plan_user_message(req: GenerateGymRequest) -> str:
    """fitness_plan 전용 user message. build_user_message와 달리 "블로그 글을 작성해
    주세요"라는 문구를 포함하지 않는다 — 회원 인바디/기본 데이터를 바탕으로 한 실전
    운동·식단 통합 프로그램 문서를 요청하는 별도 메시지다."""
    lines = [
        "아래 회원 기본 데이터와 시설 참고 정보를 바탕으로 실제 1주일 운동·식단 통합 프로그램을 작성해 주세요.",
        "블로그 글이 아닙니다. 홍보 원고가 아닙니다. 회원에게 전달할 수 있는 실전 프로그램 문서입니다.",
        "",
        f"시설 참고 정보: {req.gym_info}",
        f"프로그램 방향 참고값: {req.keyword}",
    ]
    if req.priors:
        lines.append(f"개별 조건: {req.priors}")

    member_fields = [
        ("성별/나이", req.member_gender_age),
        ("체중", req.member_weight),
        ("골격근량", req.member_muscle_mass),
        ("체지방률", req.member_body_fat),
        ("BMR", req.member_bmr),
        ("TDEE", req.member_tdee),
        ("출석 가능 횟수/요일", req.member_available_days),
        ("부상 이력 및 특이사항", req.member_injury_notes),
        ("선택 목적", req.member_goal_type),
    ]
    for label, value in member_fields:
        if value:
            lines.append(f"{label}: {value}")

    lines.append("운동과 식단은 선택 목적에 맞춰 서로 연결되도록 작성해 주세요.")
    return "\n".join(lines)


def _make_image_asset(image_type: str, plan: Dict[str, str]) -> ImageAsset:
    return ImageAsset(
        type=image_type,
        insert_position=plan["insert_position"],
        recommended_title=plan.get("recommended_title"),
        recommended_body_text=plan.get("recommended_body_text"),
        prompt=plan["prompt"],
        filename=plan["filename"],
        alt=plan["alt"],
    )


@app.get("/api/config", response_model=AppConfig)
def get_config() -> AppConfig:
    return AppConfig(storage_available=repository.available, board_write_url=IMWEB_BOARD_WRITE_URL)


def _generate_blog_post(req: GenerateGymRequest, text_model: str, image_model: str) -> GenerateGymResponse:
    """기존 블로그 글 생성 흐름. generation_type 분기가 생기기 전과 동일한 로직이다."""
    system_prompt = build_system_prompt(req.concept)
    user_message = build_user_message(
        req.gym_info,
        req.keyword,
        req.priors,
        req.trainer_name if req.concept == "trainer" else None,
        req.trainer_features if req.concept == "trainer" else None,
    )

    try:
        post = generate_blog_post(client, text_model, system_prompt, user_message)
    except openai.APIStatusError as e:
        raise HTTPException(status_code=e.status_code, detail=str(e)) from e
    except openai.APIConnectionError as e:
        raise HTTPException(status_code=503, detail="OpenAI API 연결에 실패했습니다.") from e

    plans = [("대표 이미지", post["representative_image"]), ("본문 이미지", post["body_image"])]
    images = [_make_image_asset(image_type, plan) for image_type, plan in plans]

    if req.generate_images:
        # 이미지들을 하나씩 순서대로 기다리지 않고 동시에 요청해 전체 대기 시간을 줄인다.
        results = generate_images_parallel(client, image_model, [plan["prompt"] for _, plan in plans])
        for asset, result in zip(images, results):
            if result["error"]:
                asset.image_error = result["error"]
            elif result["image"]["type"] == "base64":
                asset.image_base64 = result["image"]["data"]
            else:
                asset.image_url = result["image"]["data"]

    image_plan_text = format_image_plan_text(post["representative_image"], post["body_image"])

    # 저장소가 없는 환경(예: Vercel 운영)에서는 post_id가 None으로 돌아온다.
    post_id = repository.save(
        keyword=req.keyword,
        concept=req.concept,
        content=post["content"],
        images=[image.model_dump() for image in images],
        image_plan_text=image_plan_text,
        generation_type="blog_post",
        trainer_name=req.trainer_name if req.concept == "trainer" else None,
    )

    return GenerateGymResponse(
        id=post_id,
        content=post["content"],
        content_length=len(post["content"]),
        images=images,
        image_plan_text=image_plan_text,
    )


def _generate_short_form(
    req: GenerateGymRequest,
    text_model: str,
    generation_type: str,
    build_prompt,
    generate_fn,
) -> GenerateGymResponse:
    """운동 프로그램/식단 가이드 공용 흐름. 이미지는 만들지 않고 content만 생성한다."""
    system_prompt = build_prompt()
    user_message = build_user_message(req.gym_info, req.keyword, req.priors)

    try:
        result = generate_fn(client, text_model, system_prompt, user_message)
    except openai.APIStatusError as e:
        raise HTTPException(status_code=e.status_code, detail=str(e)) from e
    except openai.APIConnectionError as e:
        raise HTTPException(status_code=503, detail="OpenAI API 연결에 실패했습니다.") from e

    content = result["content"]

    post_id = repository.save(
        keyword=req.keyword,
        concept=req.concept,
        content=content,
        images=[],
        image_plan_text="",
        generation_type=generation_type,
    )

    return GenerateGymResponse(
        id=post_id,
        content=content,
        content_length=len(content),
        images=[],
        image_plan_text="",
    )


def _generate_fitness_plan(req: GenerateGymRequest, text_model: str) -> GenerateGymResponse:
    """운동·식단 통합 프로그램(fitness_plan) 흐름. 회원 인바디/기본 데이터를 바탕으로
    운동과 식단이 하나의 목적에 맞춰 연결된 1주일 프로그램을 한 번에 생성한다.
    blog_post와 완전히 분리된 로직이며, 이미지는 생성하지 않는다."""
    system_prompt = build_fitness_plan_prompt()
    user_message = build_fitness_plan_user_message(req)

    try:
        result = generate_fitness_plan(client, text_model, system_prompt, user_message)
    except openai.APIStatusError as e:
        raise HTTPException(status_code=e.status_code, detail=str(e)) from e
    except openai.APIConnectionError as e:
        raise HTTPException(status_code=503, detail="OpenAI API 연결에 실패했습니다.") from e

    content = result["content"]

    post_id = repository.save(
        keyword=req.keyword,
        concept=req.concept,
        content=content,
        images=[],
        image_plan_text="",
        generation_type="fitness_plan",
    )

    return GenerateGymResponse(
        id=post_id,
        content=content,
        content_length=len(content),
        images=[],
        image_plan_text="",
    )


@app.post("/api/generate-gym", response_model=GenerateGymResponse)
def generate_gym_post(req: GenerateGymRequest) -> GenerateGymResponse:
    text_model = req.model or DEFAULT_TEXT_MODEL
    image_model = req.image_model or DEFAULT_IMAGE_MODEL

    if req.generation_type == "blog_post":
        return _generate_blog_post(req, text_model, image_model)
    if req.generation_type == "fitness_plan":
        return _generate_fitness_plan(req, text_model)
    if req.generation_type == "exercise_program":
        return _generate_short_form(
            req, text_model, "exercise_program", build_exercise_program_prompt, generate_exercise_program
        )
    if req.generation_type == "diet_guide":
        return _generate_short_form(
            req, text_model, "diet_guide", build_diet_guide_prompt, generate_diet_guide
        )

    raise HTTPException(status_code=400, detail=f"알 수 없는 generation_type입니다: {req.generation_type}")


@app.get("/api/posts", response_model=List[PostSummary])
def list_saved_posts() -> List[PostSummary]:
    return [PostSummary(**row) for row in repository.list()]


@app.get("/api/posts/{post_id}", response_model=PostDetail)
def get_saved_post(post_id: int) -> PostDetail:
    if not repository.available:
        raise HTTPException(
            status_code=501,
            detail="이 환경에서는 글 저장 기능을 사용할 수 없습니다. 생성 결과를 복사해서 아임웹 게시판에 직접 붙여넣어 주세요.",
        )

    row = repository.get(post_id)

    if row is None:
        raise HTTPException(status_code=404, detail="해당 글을 찾을 수 없습니다.")

    return PostDetail(**row)


@app.delete("/api/posts/{post_id}", status_code=204)
def delete_saved_post(post_id: int) -> None:
    # SQLite 개발용 저장 글만 대상. 아임웹 게시판에 이미 발행된 글은 이 저장소와
    # 무관하므로 여기서 지운다고 해서 게시판 글이 함께 삭제되지 않는다.
    # 게시판 글의 수정/삭제는 아임웹 게시판에서 직접 처리해야 한다.
    if not repository.available:
        raise HTTPException(
            status_code=501,
            detail="이 환경에서는 글 저장 기능을 사용할 수 없습니다.",
        )

    deleted = repository.delete(post_id)

    if not deleted:
        raise HTTPException(status_code=404, detail="해당 글을 찾을 수 없습니다.")


# 중요:
# API 라우트 정의가 모두 끝난 뒤 마지막에 루트 UI를 연결한다.
# 이렇게 해야 /api/... 요청은 API로 처리되고, / 는 정적 UI로 열린다.
app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="root-ui")