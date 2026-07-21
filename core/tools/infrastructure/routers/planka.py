"""
Planka Router
=============
Proxies requests to the local/remote Planka REST API.
Enables the dashboard Kanban Board to fetch structure, boards, columns, cards,
and submit updates/comments without exposing credentials to the browser or running into CORS.
"""

from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from tools.infrastructure.server_deps import verify_authorization
from tools.infrastructure.planka import _planka_request

router = APIRouter(prefix="/api/v1/planka", tags=["Planka"])


# --- Schemas ---

class CardCreateSchema(BaseModel):
    listId: Optional[str] = None
    name: str
    description: Optional[str] = ""
    dueDate: Optional[str] = None


class CardUpdateSchema(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    listId: Optional[str] = None
    position: Optional[float] = None
    isClosed: Optional[bool] = None
    dueDate: Optional[str] = None


class CommentCreateSchema(BaseModel):
    text: str


class ListCreateSchema(BaseModel):
    name: str
    position: Optional[float] = 65535.0


class BoardCreateSchema(BaseModel):
    name: str
    position: Optional[float] = 65535.0


# --- Helpers ---

def _move_card_to_hidden_list(card_id: str, preferred_type: str = "trash"):
    """Planka 2 has no isClosed write path: a card is closed by living in the
    board's hidden trash/archive list, so removal = moving it there."""
    card = _planka_request(f"/api/cards/{card_id}", "GET")
    board_id = card.get("item", {}).get("boardId")
    if not board_id:
        raise ValueError(f"Card {card_id} has no boardId")
    board = _planka_request(f"/api/boards/{board_id}", "GET")
    lists = board.get("included", {}).get("lists", [])
    fallback_type = "archive" if preferred_type == "trash" else "trash"
    target = next((l for l in lists if l.get("type") == preferred_type), None)
    if target is None:
        target = next((l for l in lists if l.get("type") == fallback_type), None)
    if target is None:
        raise ValueError(f"Board {board_id} has no {preferred_type}/{fallback_type} list")
    return _planka_request(f"/api/cards/{card_id}", "PATCH", {"listId": target["id"]})


# --- Endpoints ---

@router.get("/structure", dependencies=[Depends(verify_authorization)])
def get_structure():
    """Retrieves all projects and boards the authenticated agent has access to."""
    try:
        return _planka_request("/api/projects", "GET")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/board/{board_id}", dependencies=[Depends(verify_authorization)])
def get_board(board_id: str):
    """Retrieves all active columns and cards for a specific board."""
    try:
        return _planka_request(f"/api/boards/{board_id}", "GET")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/cards", dependencies=[Depends(verify_authorization)])
def create_card(card: CardCreateSchema):
    """Creates a new card in the specified list or default Inbound Leads column."""
    try:
        target_list_id = card.listId
        if not target_list_id:
            projects = _planka_request("/api/projects", "GET")
            boards = projects.get("included", {}).get("boards", [])
            if boards:
                board_data = _planka_request(f"/api/boards/{boards[0]['id']}", "GET")
                lists = board_data.get("included", {}).get("lists", [])
                if lists:
                    target_list_id = lists[0]["id"]

        if not target_list_id:
            raise HTTPException(status_code=400, detail="No listId provided and no active Planka columns found.")

        payload = {
            "name": card.name,
            "type": "story",
            "position": 65535
        }
        if card.description and card.description.strip():
            payload["description"] = card.description.strip()
        if card.dueDate:
            payload["dueDate"] = card.dueDate
            
        return _planka_request(f"/api/lists/{target_list_id}/cards", "POST", payload)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.patch("/cards/{card_id}", dependencies=[Depends(verify_authorization)])
def update_card(card_id: str, card: CardUpdateSchema):
    """Updates one or more fields of a card, including moving lists or position."""
    try:
        payload = card.dict(exclude_unset=True)
        if not payload:
            raise HTTPException(status_code=400, detail="No fields provided for update")

        # Planka 2 silently ignores isClosed on PATCH (returns 200, changes
        # nothing) — closing is done by moving the card to a hidden list.
        is_closed = payload.pop("isClosed", None)

        # Planka 2 rejects a listId change without a position (422
        # "Position must be present") — default to bottom of the target list.
        if "listId" in payload and "position" not in payload:
            payload["position"] = 65535
        result = None
        if payload:
            result = _planka_request(f"/api/cards/{card_id}", "PATCH", payload)
        if is_closed:
            result = _move_card_to_hidden_list(card_id)
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/cards/{card_id}", dependencies=[Depends(verify_authorization)])
def delete_card(card_id: str):
    """Removes a card from its board by moving it to the board's trash list
    (recoverable from Planka's trash until emptied)."""
    try:
        return _move_card_to_hidden_list(card_id, preferred_type="trash")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/cards/{card_id}/comments", dependencies=[Depends(verify_authorization)])
def get_comments(card_id: str):
    """Retrieves all comments for a specific card."""
    try:
        return _planka_request(f"/api/cards/{card_id}/comments", "GET")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/cards/{card_id}/comments", dependencies=[Depends(verify_authorization)])
def add_comment(card_id: str, comment: CommentCreateSchema):
    """Adds a new comment to a card."""
    try:
        payload = {
            "text": comment.text
        }
        return _planka_request(f"/api/cards/{card_id}/comments", "POST", payload)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/boards/{board_id}/lists", dependencies=[Depends(verify_authorization)])
def create_list(board_id: str, lst: ListCreateSchema):
    """Creates a new list (column) in a board."""
    try:
        payload = {
            "name": lst.name,
            "position": lst.position,
            "type": "active"
        }
        return _planka_request(f"/api/boards/{board_id}/lists", "POST", payload)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/projects/{project_id}/boards", dependencies=[Depends(verify_authorization)])
def create_board(project_id: str, board: BoardCreateSchema):
    """Creates a new board inside a project."""
    try:
        payload = {
            "name": board.name,
            "type": "kanban",
            "position": board.position
        }
        return _planka_request(f"/api/projects/{project_id}/boards", "POST", payload)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.patch("/boards/{board_id}", dependencies=[Depends(verify_authorization)])
def update_board(board_id: str, board: BoardCreateSchema):
    """Updates the name or properties of a board."""
    try:
        payload = {
            "name": board.name
        }
        return _planka_request(f"/api/boards/{board_id}", "PATCH", payload)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/boards/{board_id}", dependencies=[Depends(verify_authorization)])
def delete_board(board_id: str):
    """Deletes a specific board."""
    try:
        return _planka_request(f"/api/boards/{board_id}", "DELETE")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
