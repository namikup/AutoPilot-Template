# app/routers/ai.py
"""
AI Management Router - Connects frontend AI Manager to external Supervity AI workflow API.
"""

import json
import logging
import os
import httpx
from fastapi import APIRouter, Depends, HTTPException, status

from ..schemas.ai import AIChatRequest, AIChatResponse
from ..security import get_current_user

log = logging.getLogger(__name__)

router = APIRouter(prefix="/ai", tags=["AI Manager"])

# Configuration defaults from environment variables
SUPERVITY_API_URL = os.getenv(
    "SUPERVITY_API_URL",
    "https://auto-workflow-api.supervity.ai/api/v1/workflow-runs/execute/stream",
)
SUPERVITY_WORKFLOW_ID = os.getenv(
    "SUPERVITY_WORKFLOW_ID", "019f7cc4-552a-7000-8d0f-d226fe29f247"
)
SUPERVITY_API_KEY = os.getenv("SUPERVITY_API_KEY", "")
SUPERVITY_ACTIVE_ORG = os.getenv(
    "SUPERVITY_ACTIVE_ORG", "LIM Jia Xian Workspace"
)
SUPERVITY_ACTIVE_TEAM = os.getenv("SUPERVITY_ACTIVE_TEAM", "Gang Intelligence")
SUPERVITY_TEAM_KEY = os.getenv("SUPERVITY_TEAM_KEY", "Gang Intelligence")
SUPERVITY_USER_TIMEZONE = os.getenv(
    "SUPERVITY_USER_TIMEZONE", "Asia/Kuala_Lumpur"
)


def parse_supervity_output(raw_text: str) -> str:
    """
    Parse raw response or SSE stream chunks from Supervity AI API output.
    """
    if not raw_text or not raw_text.strip():
        return "Workflow executed successfully, but returned an empty response."

    # 1. Attempt JSON parse directly
    try:
        data = json.loads(raw_text)
        if isinstance(data, dict):
            for key in [
                "output",
                "response",
                "result",
                "message",
                "text",
                "content",
            ]:
                if key in data and data[key]:
                    return str(data[key])
            return json.dumps(data, indent=2)
    except Exception:
        pass

    # 2. Attempt SSE (Server-Sent Events) stream line-by-line parsing
    lines = raw_text.splitlines()
    extracted_text_parts = []
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("data:"):
            content_part = stripped[5:].strip()
            if content_part == "[DONE]":
                continue
            try:
                data = json.loads(content_part)
                if isinstance(data, dict):
                    val = (
                        data.get("text")
                        or data.get("content")
                        or data.get("output")
                        or data.get("response")
                        or content_part
                    )
                    extracted_text_parts.append(str(val))
                else:
                    extracted_text_parts.append(str(data))
            except Exception:
                extracted_text_parts.append(content_part)
        elif (
            stripped
            and not stripped.startswith("event:")
            and not stripped.startswith("id:")
        ):
            extracted_text_parts.append(stripped)

    if extracted_text_parts:
        return "\n".join(extracted_text_parts)

    return raw_text


@router.post("/chat", response_model=AIChatResponse)
async def ai_chat(
    payload: AIChatRequest,
    current_user: dict = Depends(get_current_user),
):
    """
    Triggers external Supervity AI workflow via API and returns response to Chat UI.
    """
    user_email = (
        current_user.get("email") or payload.reporter_email or "user@example.com"
    )

    log.info(
        f"AI Manager triggering workflow {SUPERVITY_WORKFLOW_ID} for user: {user_email}"
    )

    api_key = os.getenv("SUPERVITY_API_KEY", SUPERVITY_API_KEY)
    if not api_key:
        log.warning(
            "SUPERVITY_API_KEY is not configured in environment variables."
        )

    # Headers matching Supervity API specification
    headers = {
        "Authorization": f"Bearer {api_key}",
        "x-source": "external",
        "x-active-org": SUPERVITY_ACTIVE_ORG,
        "x-active-team": SUPERVITY_ACTIVE_TEAM,
        "x-teamKey": SUPERVITY_TEAM_KEY,
        "x-user-timezone": SUPERVITY_USER_TIMEZONE,
    }

    # Multipart form-data fields matching Supervity API -F parameters
    form_fields = {
        "workflowId": (None, SUPERVITY_WORKFLOW_ID),
        "inputs[issue_key]": (None, payload.issue_key or "ISSUE-101"),
        "inputs[ticket_description]": (None, payload.message),
        "inputs[reporter_email]": (None, user_email),
        "inputs[inactive_days_threshold]": (
            None,
            str(payload.inactive_days_threshold),
        ),
        "inputs[sla_threshold_hours]": (None, str(payload.sla_threshold_hours)),
        "inputs[it_team_slack]": (None, payload.it_team_slack or "#it-support"),
    }

    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                SUPERVITY_API_URL,
                headers=headers,
                files=form_fields,
            )

            if response.status_code != 200:
                log.error(
                    f"Supervity API error (status {response.status_code}): {response.text}"
                )
                raise HTTPException(
                    status_code=status.HTTP_502_BAD_GATEWAY,
                    detail=f"Supervity AI Workflow call failed with status {response.status_code}: {response.text}",
                )

            ai_message = parse_supervity_output(response.text)

            return AIChatResponse(
                response=ai_message,
                status="success",
                workflow_id=SUPERVITY_WORKFLOW_ID,
            )

    except httpx.RequestError as err:
        log.error(f"HTTP connection error triggering Supervity AI workflow: {err}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Unable to reach Supervity AI Workflow service: {str(err)}",
        )
