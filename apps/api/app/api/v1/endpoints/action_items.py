"""Workspace Action Items management endpoints."""

import math
import uuid
from typing import Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies.workspace import resolve_workspace_context
from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.user import User
from app.schemas.intelligence import (
    ActionItemCreate,
    ActionItemListResponse,
    ActionItemResponse,
    ActionItemUpdate,
)
from app.services.intelligence_service import IntelligenceService

from sqlalchemy import inspect

router = APIRouter()


def _to_action_item_response(item) -> ActionItemResponse:
    """Helper to convert ActionItem ORM instance into ActionItemResponse with meeting_title."""
    resp = ActionItemResponse.model_validate(item)
    insp = inspect(item)
    if insp and hasattr(insp, "unloaded"):
        if "meeting" not in insp.unloaded and item.meeting:
            resp.meeting_title = item.meeting.title
    elif hasattr(item, "meeting") and item.__dict__.get("meeting"):
        resp.meeting_title = item.meeting.title
    return resp


@router.get(
    "",
    response_model=ActionItemListResponse,
    status_code=status.HTTP_200_OK,
    summary="List workspace action items",
    description="Retrieve paginated, workspace-isolated action items with search, filters, and sorting.",
)
async def list_workspace_action_items(
    workspace_id: Optional[uuid.UUID] = Query(None, description="Workspace UUID"),
    search: Optional[str] = Query(None, description="Search term for title, description, or assignee"),
    status_filter: Optional[str] = Query(None, alias="status", description="OPEN, IN_PROGRESS, OVERDUE, COMPLETED, CANCELLED"),
    assignee_id: Optional[uuid.UUID] = Query(None, description="Assignee user UUID"),
    assignee_name: Optional[str] = Query(None, description="Assignee name, UNASSIGNED, or MY_TASKS"),
    priority_filter: Optional[str] = Query(None, alias="priority", description="LOW, MEDIUM, HIGH, URGENT"),
    meeting_id: Optional[uuid.UUID] = Query(None, description="Filter by meeting UUID"),
    due_date_filter: Optional[str] = Query(None, description="OVERDUE, TODAY, THIS_WEEK, THIS_MONTH, NO_DUE_DATE"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Page size"),
    sort_by: str = Query("due_date", description="Sort column: due_date, priority, status, created_at, title"),
    sort_order: str = Query("asc", description="Sort direction: asc or desc"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ActionItemListResponse:
    """Fetch paginated action items scoped to workspace."""
    target_workspace_id = await resolve_workspace_context(
        db=db,
        current_user=current_user,
        workspace_id=workspace_id,
    )

    items, total = await IntelligenceService.get_workspace_action_items(
        db=db,
        workspace_id=target_workspace_id,
        current_user=current_user,
        search=search,
        status_filter=status_filter,
        assignee_id=assignee_id,
        assignee_name=assignee_name,
        priority_filter=priority_filter,
        meeting_id=meeting_id,
        due_date_filter=due_date_filter,
        page=page,
        page_size=page_size,
        sort_by=sort_by,
        sort_order=sort_order,
    )

    total_pages = math.ceil(total / page_size) if total > 0 else 1

    return ActionItemListResponse(
        items=[_to_action_item_response(i) for i in items],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )


@router.get(
    "/metrics",
    response_model=Dict[str, int],
    status_code=status.HTTP_200_OK,
    summary="Get workspace action item summary metrics",
    description="Compute total, my_tasks, overdue, and completed action item counts for a workspace.",
)
async def get_action_item_metrics(
    workspace_id: Optional[uuid.UUID] = Query(None, description="Workspace UUID"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Dict[str, int]:
    """Return workspace task metrics."""
    target_workspace_id = await resolve_workspace_context(
        db=db,
        current_user=current_user,
        workspace_id=workspace_id,
    )

    return await IntelligenceService.get_workspace_action_item_metrics(
        db=db,
        workspace_id=target_workspace_id,
        current_user=current_user,
    )



@router.post(
    "",
    response_model=ActionItemResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create action item",
    description="Create a new action item under a workspace meeting.",
)
async def create_action_item(
    payload: ActionItemCreate,
    meeting_id: uuid.UUID = Query(..., description="Associated meeting UUID"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ActionItemResponse:
    """Create a new action item."""
    action_item = await IntelligenceService.create_action_item(
        db=db,
        meeting_id=meeting_id,
        payload=payload,
        current_user=current_user,
    )
    return _to_action_item_response(action_item)


@router.patch(
    "/{action_item_id}",
    response_model=ActionItemResponse,
    status_code=status.HTTP_200_OK,
    summary="Update action item",
    description="Update task title, description, assignee, priority, status, or due date.",
)
async def update_action_item(
    action_item_id: uuid.UUID,
    payload: ActionItemUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ActionItemResponse:
    """Update an action item."""
    action_item = await IntelligenceService.update_action_item(
        db=db,
        action_item_id=action_item_id,
        payload=payload,
        current_user=current_user,
    )
    return _to_action_item_response(action_item)


@router.delete(
    "/{action_item_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete action item",
    description="Delete an existing action item.",
)
async def delete_action_item(
    action_item_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Delete an action item."""
    await IntelligenceService.delete_action_item(
        db=db,
        action_item_id=action_item_id,
        current_user=current_user,
    )
