"""OpenAI API 호출 로직 (텍스트: chat completions / 이미지: images)."""

import json
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Dict, List, Optional

import openai

MIN_CHARS = 1500
MAX_CHARS = 1600

REPRESENTATIVE_IMAGE_ITEM_SCHEMA = {
    "type": "object",
    "properties": {
        "insert_position": {
            "type": "string",
            "description": "항상 '글 최상단 (대표 이미지)'라는 고정 문자열을 반환한다.",
        },
        "recommended_title": {
            "type": "string",
            "description": "카드뉴스 표지 이미지 안에 실제로 렌더링할 타이틀 문구 (예: '공복 유산소, 진짜 살이 더 빠질까?')",
        },
        "prompt": {
            "type": "string",
            "description": "카드뉴스 표지 프롬프트 기본 형식을 따른 완성된 한국어 문장. recommended_title 값을 큰따옴표로 그대로 인용해 포함해서, 이미지 안에 그 텍스트가 실제로 렌더링되게 한다 (1:1 정사각형).",
        },
        "filename": {
            "type": "string",
            "description": "영어 소문자와 하이픈만 사용하고 '-cardnews-cover'로 끝나는 파일명",
        },
        "alt": {
            "type": "string",
            "description": "이미지에 실제로 보이는 내용을 짧고 사실적으로 설명하는 ALT 텍스트",
        },
    },
    "required": ["insert_position", "recommended_title", "prompt", "filename", "alt"],
    "additionalProperties": False,
}

BODY_IMAGE_ITEM_SCHEMA = {
    "type": "object",
    "properties": {
        "insert_position": {
            "type": "string",
            "description": "본문 중 가장 핵심이 되는 소제목(인용구) 문장을 그대로 옮겨적는다.",
        },
        "recommended_body_text": {
            "type": "string",
            "description": "카드뉴스 내지 이미지 안에 실제로 렌더링할 본문/팁 문구 (예: '1. 운동 후 30분 이내 단백질 20g 섭취 / 2. 정제 탄수화물 대신 복합 탄수화물 선택')",
        },
        "prompt": {
            "type": "string",
            "description": "카드뉴스 내지 프롬프트 기본 형식을 따른 완성된 한국어 문장. recommended_body_text 값을 큰따옴표로 그대로 인용해 포함해서, 이미지 안에 그 텍스트가 실제로 렌더링되게 한다 (1:1 정사각형).",
        },
        "filename": {
            "type": "string",
            "description": "영어 소문자와 하이픈만 사용하고 '-cardnews-content'로 끝나는 파일명",
        },
        "alt": {
            "type": "string",
            "description": "이미지에 실제로 보이는 내용을 짧고 사실적으로 설명하는 ALT 텍스트",
        },
    },
    "required": ["insert_position", "recommended_body_text", "prompt", "filename", "alt"],
    "additionalProperties": False,
}

BLOG_POST_SCHEMA = {
    "name": "gym_blog_post",
    "schema": {
        "type": "object",
        "properties": {
            "content": {
                "type": "string",
                "description": "완성된 블로그 글 본문 전체 (공백 포함 1,500~1,600자)",
            },
            "representative_image": REPRESENTATIVE_IMAGE_ITEM_SCHEMA,
            "body_image": BODY_IMAGE_ITEM_SCHEMA,
        },
        "required": ["content", "representative_image", "body_image"],
        "additionalProperties": False,
    },
    "strict": True,
}


def _call_chat(client, model: str, system_prompt: str, messages_history: list) -> Dict[str, Any]:
    response = client.chat.completions.create(
        model=model,
        messages=[{"role": "system", "content": system_prompt}] + messages_history,
        response_format={"type": "json_schema", "json_schema": BLOG_POST_SCHEMA},
    )
    raw = response.choices[0].message.content
    return json.loads(raw)


MAX_LENGTH_ATTEMPTS = 3  # 최초 1회 + 보정 최대 2회
CLOSING_MARKER = "시설위치지도사진"
SENTENCE_END_CHARS = ".!?"


def _truncate_to_max_chars(content: str) -> str:
    """모델이 보정 요청을 거쳐도 끝내 MAX_CHARS를 못 맞추면 마지막 안전장치로
    문장 경계에서 강제로 잘라 상한선을 지킨다. 마지막 줄의 마감 마커
    ("시설위치지도사진")는 항상 보존한다."""
    lines = content.rstrip("\n").split("\n")
    if lines and lines[-1].strip() == CLOSING_MARKER:
        marker_line = lines[-1]
        body = "\n".join(lines[:-1])
    else:
        marker_line = None
        body = content

    budget = MAX_CHARS - (len(marker_line) + 1 if marker_line else 0)
    if len(body) <= budget:
        trimmed_body = body
    else:
        window = body[:budget]
        cut = max(window.rfind(ch) for ch in SENTENCE_END_CHARS)
        trimmed_body = window[: cut + 1] if cut > 0 else window

    return f"{trimmed_body}\n{marker_line}" if marker_line else trimmed_body


def generate_blog_post(
    client,
    model: str,
    system_prompt: str,
    user_message: str,
) -> Dict[str, Any]:
    """블로그 글(content)과 카드뉴스 이미지 계획(representative_image, body_image)을 생성한다.

    content의 분량(공백 포함 1,500~1,600자) 요구가 매우 중요하므로, 범위를
    벗어나면 정확한 초과/부족 글자수를 알려주며 최대 MAX_LENGTH_ATTEMPTS번까지
    같은 대화 맥락에서 분량만 교정하는 보정 요청을 보낸다.
    """
    history = [{"role": "user", "content": user_message}]
    data = _call_chat(client, model, system_prompt, history)

    for _ in range(MAX_LENGTH_ATTEMPTS - 1):
        length = len(data["content"])
        if MIN_CHARS <= length <= MAX_CHARS:
            break

        if length > MAX_CHARS:
            diff_instruction = f"{length - MAX_CHARS}자만큼 초과했으니 그만큼 줄여주세요."
        else:
            diff_instruction = f"{MIN_CHARS - length}자만큼 부족하니 그만큼 늘려주세요."

        correction = (
            f"방금 작성한 content는 공백 포함 {length}자입니다. {diff_instruction} "
            f"형식과 내용, 어투는 그대로 유지하면서 content 분량만 공백 포함 {MIN_CHARS}자 이상 "
            f"{MAX_CHARS}자 이내로 다시 작성해 주세요. representative_image와 body_image는 그대로 유지해도 됩니다."
        )
        history = history + [
            {"role": "assistant", "content": json.dumps(data, ensure_ascii=False)},
            {"role": "user", "content": correction},
        ]
        data = _call_chat(client, model, system_prompt, history)

    content = data["content"]
    if len(content) > MAX_CHARS:
        content = _truncate_to_max_chars(content)

    return {
        "content": content,
        "representative_image": data["representative_image"],
        "body_image": data["body_image"],
    }


def generate_image(
    client,
    model: str,
    prompt: str,
    size: str = "1024x1024",
) -> Optional[Dict[str, str]]:
    """카드뉴스 이미지를 생성해 base64 또는 url을 반환한다. 실패 시 None."""
    response = client.images.generate(model=model, prompt=prompt, size=size, n=1)
    item = response.data[0]
    if getattr(item, "b64_json", None):
        return {"type": "base64", "data": item.b64_json}
    if getattr(item, "url", None):
        return {"type": "url", "data": item.url}
    return None


def generate_images_parallel(
    client,
    model: str,
    prompts: List[str],
    size: str = "1024x1024",
) -> List[Dict[str, Optional[str]]]:
    """여러 이미지 프롬프트를 동시에(병렬로) 생성한다.

    대표 이미지 1장 + 본문 이미지 1장을 순차로 생성하면 대기 시간이 늘어나므로,
    스레드풀로 동시에 요청해 전체 대기 시간을 "가장 느린 이미지 1장" 수준으로
    줄인다. 결과는 입력 prompts와 같은 순서로, 각 항목은
    {"image": {...} | None, "error": str | None} 형태다.
    """
    results: List[Dict[str, Optional[str]]] = [None] * len(prompts)  # type: ignore[list-item]

    def _run(index: int, prompt: str) -> None:
        try:
            image = generate_image(client, model, prompt, size=size)
            if image is None:
                results[index] = {"image": None, "error": "이미지 생성 응답에서 이미지 데이터를 찾을 수 없습니다."}
            else:
                results[index] = {"image": image, "error": None}
        except openai.OpenAIError as e:
            # 한 이미지의 실패가 다른 이미지나 전체 요청에 전파되지 않게 한다.
            results[index] = {"image": None, "error": str(e)}

    if not prompts:
        return results

    with ThreadPoolExecutor(max_workers=len(prompts)) as executor:
        futures = [executor.submit(_run, i, prompt) for i, prompt in enumerate(prompts)]
        for future in futures:
            future.result()

    return results


def format_image_plan_text(representative_image: Dict[str, str], body_image: Dict[str, str]) -> str:
    """사용자가 지정한 카드뉴스 출력 규칙([대표 이미지] / [본문 이미지] 블록)대로
    사람이 읽기 좋은 텍스트를 조립한다."""
    blocks = [
        "\n".join(
            [
                "[대표 이미지 (카드뉴스 표지)]",
                f"삽입 위치: {representative_image['insert_position']}",
                f"카드뉴스 추천 타이틀 문구: {representative_image['recommended_title']}",
                f"이미지 생성 프롬프트: {representative_image['prompt']}",
                f"파일명: {representative_image['filename']}",
                f"ALT: {representative_image['alt']}",
            ]
        ),
        "\n".join(
            [
                "[본문 이미지 (카드뉴스 내지)]",
                f"삽입 위치: {body_image['insert_position']}",
                f"카드뉴스 추천 본문 문구: {body_image['recommended_body_text']}",
                f"이미지 생성 프롬프트: {body_image['prompt']}",
                f"파일명: {body_image['filename']}",
                f"ALT: {body_image['alt']}",
            ]
        ),
    ]
    return "\n\n".join(blocks)
