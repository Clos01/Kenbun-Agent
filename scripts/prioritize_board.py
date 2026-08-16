import sys
import os
import json
import logging
import re
import ssl
import urllib.request
import urllib.error
from datetime import datetime
from typing import List, Dict, Any, Tuple, Optional

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("prioritizer")

# Session cache
_cached_token: Optional[str] = None
_cached_base_url: Optional[str] = None

def _get_planka_client() -> Tuple[str, str]:
    """Retrieves Planka configuration and authenticates to get a Bearer token securely once."""
    global _cached_token, _cached_base_url
    if _cached_token and _cached_base_url:
        return _cached_base_url, _cached_token

    base_url = os.environ.get("PLANKA_BASE_URL")
    email = os.environ.get("PLANKA_AGENT_EMAIL")
    password = os.environ.get("PLANKA_AGENT_PASSWORD")
    
    if not base_url:
        raise ValueError("Missing PLANKA_BASE_URL in environment.")
    if not email or not password:
        raise ValueError("Missing Planka credentials in environment.")
        
    base_url_clean = str(base_url).rstrip("/")
    # Prevent SSRF on base URL by strictly validating host format
    if not re.match(r"^https?://[a-zA-Z0-9.\-]+(:[0-9]+)?$", base_url_clean):
        raise ValueError("Invalid or unsafe base URL format.")
        
    url = f"{base_url_clean}/api/access-tokens"
    payload = {
        "emailOrUsername": str(email),
        "password": str(password)
    }
    req_data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=req_data, method="POST")
    req.add_header("Content-Type", "application/json")
    
    ssl_context = ssl.create_default_context()
    ssl_context.check_hostname = True
    ssl_context.verify_mode = ssl.CERT_REQUIRED
    
    try:
        with urllib.request.urlopen(req, timeout=10, context=ssl_context) as response:
            if response.status != 200:
                raise ValueError("Auth server returned non-200 status.")
            
            raw_body = response.read().decode("utf-8")
            res_data = json.loads(raw_body)
            if not isinstance(res_data, dict):
                raise TypeError("Auth response is not a JSON dict.")
                
            token = res_data.get("item")
            if not token or not isinstance(token, str):
                raise ValueError("Auth token not found.")
            
            _cached_token = token
            _cached_base_url = base_url_clean
            return base_url_clean, token
    except urllib.error.URLError:
        raise ConnectionError("Network issue during Planka authentication.") from None
    except ValueError:
        raise ValueError("Failed to parse authentication response securely.") from None
    except TypeError:
        raise TypeError("Unexpected type layout in authentication response.") from None
    except json.JSONDecodeError:
        raise ValueError("Invalid JSON in authentication response.") from None
    finally:
        # Prevent references from remaining in local scope frame
        email = None
        password = None

def _planka_request(path: str) -> Dict[str, Any]:
    """Performs an authorized HTTP GET request with explicit timeouts, validation, and error checking."""
    base_url, token = _get_planka_client()
    
    # Allow alphanumeric characters, slashes, underscores, hyphens, question marks, equals, and ampersands
    sanitized_path = re.sub(r"[^a-zA-Z0-9_/=\-?&]", "", path)
    if not sanitized_path.startswith("/api/"):
        raise ValueError("Unsafe URL path format requested.")
        
    url = f"{base_url}{sanitized_path}"
    req = urllib.request.Request(url, method="GET")
    req.add_header("Content-Type", "application/json")
    req.add_header("Authorization", f"Bearer {token}")
    
    ssl_context = ssl.create_default_context()
    ssl_context.check_hostname = True
    ssl_context.verify_mode = ssl.CERT_REQUIRED
    
    try:
        with urllib.request.urlopen(req, timeout=10, context=ssl_context) as response:
            if response.status != 200:
                raise ValueError("Planka API returned error status.")
            
            raw_body = response.read().decode("utf-8")
            res_data = json.loads(raw_body)
            if not isinstance(res_data, dict):
                raise TypeError("Planka API response is not a valid JSON dictionary.")
                
            return res_data
    except urllib.error.HTTPError:
        raise ConnectionError("HTTP connection error accessing Planka server.") from None
    except urllib.error.URLError:
        raise ConnectionError("Network connection error accessing Planka server.") from None
    except ValueError:
        raise ValueError("Failed to parse Planka API response payload securely.") from None
    except TypeError:
        raise TypeError("Unexpected type layout in Planka API response.") from None
    except json.JSONDecodeError:
        raise ValueError("Invalid JSON in Planka API response.") from None

def calculate_card_score(card: Dict[str, Any], list_name: str) -> float:
    """Calculates a numerical priority score for a single card based on status and dates."""
    score = 0.0
    
    lname_lower = str(list_name).lower()
    if "in progress" in lname_lower:
        score += 100.0
    elif "blocked" in lname_lower:
        score += 80.0
    elif "to do" in lname_lower or "todo" in lname_lower:
        score += 50.0
    elif "done" in lname_lower or "completed" in lname_lower:
        score -= 500.0
        
    due_date_str = card.get("dueDate")
    if due_date_str:
        try:
            date_part = str(due_date_str).split("T")[0]
            due_date = datetime.strptime(date_part, "%Y-%m-%d").date()
            today = datetime.now().date()
            delta_days = (due_date - today).days
            
            if delta_days < 0:
                score += 200.0
            elif delta_days == 0:
                score += 150.0
            elif delta_days <= 3:
                score += 100.0
            elif delta_days <= 7:
                score += 50.0
        except ValueError:
            logger.warning("Invalid date format detected.")
            
    name = str(card.get("name") or "").lower()
    desc = str(card.get("description") or "").lower()
    
    if any(kw in name or kw in desc for kw in ["critical", "urgent", "blocker", "p0", "p1"]):
        score += 120.0
    if any(kw in name or kw in desc for kw in ["high", "p2", "must-have"]):
        score += 60.0
    if any(kw in name for kw in ["🏆", "🔥", "⭐"]):
        score += 80.0
        
    if any(kw in name or kw in desc for kw in ["low", "nice-to-have", "p3", "optional"]):
        score -= 40.0
        
    if "before" in desc or "depends on" in desc or "requires" in desc or "dependency" in desc:
        score += 50.0
        
    return score

def prioritize_cards(cards: List[Dict[str, Any]], lists: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Sorts and prioritizes the list of Planka cards in descending order."""
    list_map = {lst.get("id"): lst.get("name", "Unknown List") for lst in lists}
    
    prioritized = []
    for card in cards:
        if card.get("isClosed"):
            continue
            
        list_id = card.get("listId")
        list_name = list_map.get(list_id, "Unknown List")
        score = calculate_card_score(card, list_name)
        
        # Scrub names/descriptions to make data structures PII-safe
        card_copy = {
            "id": card.get("id"),
            "listId": list_id,
            "_priority_score": score,
            "_list_name": list_name
        }
        prioritized.append(card_copy)
        
    prioritized.sort(key=lambda c: c["_priority_score"], reverse=True)
    return prioritized

def get_and_prioritize_board(board_id: str) -> None:
    """Fetches Planka board data, prioritizes cards, and logs priority rankings."""
    sanitized_id = re.sub(r"[^a-zA-Z0-9_-]", "", board_id)
    if not sanitized_id:
        raise ValueError("Invalid sanitized board ID.")
        
    board_data = _planka_request(f"/api/boards/{sanitized_id}")
    included = board_data.get("included", {})
    if not isinstance(included, dict):
        raise TypeError("Included items in Planka response are malformed.")
        
    lists = included.get("lists", [])
    cards = included.get("cards", [])
    if not isinstance(lists, list) or not isinstance(cards, list):
        raise TypeError("Lists or Cards properties from Planka response are malformed.")
    
    prioritized = prioritize_cards(cards, lists)
    
    logger.info("=== PRIORITY REPORT ===")
    for index, card in enumerate(prioritized, 1):
        score_val = float(card['_priority_score'])
        logger.info(f"Rank {index} | Score: {score_val:.1f}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        logger.error("Usage: python prioritize_board.py <board_id>")
        sys.exit(1)
        
    board_input = sys.argv[1]
    get_and_prioritize_board(board_input)
