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


def _get_clean_env(key: str, default: str = "") -> str:
    """Retrieve environment variable and strip extraneous quotes/spaces."""
    val = os.getenv(key, default)
    if val:
        return val.strip().strip('"').strip("'")
    return default


def parse_supervity_output(raw_text: str) -> str:
    """
    Parse raw response or SSE stream chunks from Supervity AI API output.
    """
    if not raw_text or not raw_text.strip():
        return "Workflow executed successfully, but returned an empty response."

    lines = raw_text.splitlines()
    extracted_text_parts = []
    is_error = False

    for line in lines:
        stripped = line.strip()
        if stripped.startswith("event:"):
            evt = stripped[6:].strip()
            if evt in ["error", "quota-exceeded"]:
                is_error = True
        elif stripped.startswith("data:"):
            content_part = stripped[5:].strip()
            if content_part == "[DONE]":
                continue
            try:
                data = json.loads(content_part)
                if isinstance(data, dict):
                    msg = (
                        data.get("message")
                        or data.get("error")
                        or data.get("text")
                        or data.get("content")
                        or data.get("output")
                        or data.get("response")
                    )
                    if msg:
                        extracted_text_parts.append(str(msg))
                    elif content_part:
                        extracted_text_parts.append(content_part)
                else:
                    extracted_text_parts.append(str(data))
            except Exception:
                extracted_text_parts.append(content_part)

    if extracted_text_parts:
        text = "\n".join(extracted_text_parts)
        if is_error:
            return f"⚠️ Supervity AI Notice: {text}"
        return text

    # 1. Attempt JSON parse directly
    try:
        data = json.loads(raw_text)
        if isinstance(data, dict):
            if "error" in data and data["error"]:
                return f"Supervity Workflow Error: {data.get('message') or data['error']}"
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

    return raw_text


@router.post("/chat", response_model=AIChatResponse)
async def ai_chat(
    payload: AIChatRequest,
    current_user: dict = Depends(get_current_user),
):
    """
    Triggers external Supervity AI workflow via API and returns response to Chat UI.
    """
    api_url = _get_clean_env(
        "SUPERVITY_API_URL",
        "https://auto-workflow-api.supervity.ai/api/v1/workflow-runs/execute/stream",
    )
    workflow_id = _get_clean_env(
        "SUPERVITY_WORKFLOW_ID", "019f7cc4-552a-7000-8d0f-d226fe29f247"
    )
    api_key = _get_clean_env("SUPERVITY_API_KEY", "")
    active_org = _get_clean_env("SUPERVITY_ACTIVE_ORG", "")
    active_team = _get_clean_env("SUPERVITY_ACTIVE_TEAM", "")
    team_key = _get_clean_env("SUPERVITY_TEAM_KEY", "")
    user_timezone = _get_clean_env("SUPERVITY_USER_TIMEZONE", "Asia/Kuala_Lumpur")

    user_email = (
        current_user.get("email") or payload.reporter_email or "user@example.com"
    )

    log.info(
        f"AI Manager triggering workflow {workflow_id} for user: {user_email}"
    )

    if not api_key:
        log.warning(
            "SUPERVITY_API_KEY is not configured in environment variables."
        )

    # Headers matching Supervity API specification
    headers = {
        "Authorization": f"Bearer {api_key}",
        "x-source": "external",
        "x-user-timezone": user_timezone,
    }

    # Only include organization & team headers if configured to avoid 403 Forbidden errors
    if active_org:
        headers["x-active-org"] = active_org
    if active_team:
        headers["x-active-team"] = active_team
    if team_key:
        headers["x-teamKey"] = team_key

    # Multipart form-data fields matching Supervity API -F parameters
    form_fields = {
        "workflowId": (None, workflow_id),
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
        async with httpx.AsyncClient(timeout=180.0) as client:
            response = await client.post(
                api_url,
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
                workflow_id=workflow_id,
            )

    except httpx.RequestError as err:
        log.error(f"HTTP connection error triggering Supervity AI workflow: {err}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Unable to reach Supervity AI Workflow service: {str(err)}",
        )

