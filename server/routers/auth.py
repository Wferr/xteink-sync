import time
import uuid

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from server.core import config
from server.core.auth import LoginRequest
from server.core.data import load_tokens, save_tokens

router = APIRouter()


@router.post("/auth/login")
async def login_route(request: Request):
    try:
        data = await request.json()
        login_req = LoginRequest(**data)
    except Exception:
        return JSONResponse({"success": False, "error": "Invalid JSON"}, status_code=400)

    user_account = None
    for user in config.SERVER_CONFIG["auth"]["users"]:
        if user["email"] == login_req.email and user["password"] == login_req.password:
            user_account = user
            break
    if user_account:
        new_token = uuid.uuid4().hex
        user_id = uuid.uuid4().hex
        tokens = load_tokens()
        tokens[new_token] = {
            "id": user_id,
            "email": login_req.email,
            "nickname": "Admin",
            "created_at": int(time.time()),
        }
        save_tokens(tokens)

        print(f"LOGIN SUCCESS: {login_req.email}")
        return {
            "success": True,
            "access_token": new_token,
            "refresh_token": new_token,
            "user_id": user_id,
            "user": {
                "id": user_id,
                "email": login_req.email,
                "nickname": "Admin",
                "role": "admin",
                "is_active": True,
            },
        }
    else:
        print(f"LOGIN FAILED: {login_req.email}")
        return JSONResponse({"success": False, "message": "Invalid credentials"}, status_code=401)


@router.post("/auth/refresh")
async def refresh_token(request: Request):
    # Retrieve token from header
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        return JSONResponse({"success": False, "error": "Missing token"}, status_code=401)

    old_token = auth_header.split(" ")[1]
    tokens = load_tokens()

    if old_token not in tokens:
        return JSONResponse({"success": False, "error": "Invalid token"}, status_code=401)

    user_info = tokens[old_token]

    # Generate new token
    new_token = uuid.uuid4().hex
    tokens[new_token] = user_info
    tokens[new_token]["created_at"] = int(time.time())

    del tokens[old_token]
    save_tokens(tokens)

    return {"success": True, "access_token": new_token, "refresh_token": new_token}
