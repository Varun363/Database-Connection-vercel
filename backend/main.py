from datetime import datetime, timedelta, timezone
from pathlib import Path
import json
import os
import secrets
import ai

from fastapi.templating import Jinja2Templates
from fastapi.requests import Request
from dotenv import load_dotenv
load_dotenv()
import bcrypt
import jwt
import resort_db
from db import Base
from db import engine, get_db
from sqlalchemy.orm import Session
from fastapi import FastAPI, HTTPException, Depends, Header
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, EmailStr, Field
from vercel.blob import BlobClient, BlobNotFoundError

Base.metadata.create_all(bind=engine)

BASE = Path(__file__).resolve().parent.parent
SECRET = os.getenv("JWT_SECRET", "dev-secret-change-me")
BLOB_ACCESS = "private"
USERS_PREFIX = "registered-users/"
templates = Jinja2Templates(directory=BASE / "frontend")



ROLES = {
    "resort": "Resort Admin",
    "owner": "Resort Owner",
    "manager": "Resort Manager",
    "reception": "Reception Staff",
    "housekeeping": "Housekeeping Staff",
    "maintenance": "Maintenance Team",
}



def blob_client():
    
    if not (
        os.getenv("BLOB_STORE_ID")
        or os.getenv("BLOB_READ_WRITE_TOKEN")
    ):
        raise HTTPException(
            503,
            "Vercel Blob is not configured. Connect a Blob store to this Vercel project.",
        )
    return BlobClient()


def user_path(user_id: str) -> str:
    return f"{USERS_PREFIX}{user_id}.json"


def user_public(user: dict) -> dict:
    return {
        "user_id": user["user_id"],
        "full_name": user["full_name"],
        "email": user["email"],
        "role": user["role"],
        "role_name": user["role_name"],
        "resort_name": user["resort_name"],
        "created_at": user.get("created_at"),
    }


def save_user(user: dict):
    client = blob_client()
    body = json.dumps(user, ensure_ascii=False).encode("utf-8")
    try:
        client.put(
            user_path(user["user_id"]),
            body,
            access=BLOB_ACCESS,
            content_type="application/json",
            overwrite=False,
        )
    except Exception as e:
        raise HTTPException(500, f"Could not save registration file: {e}")


def load_user(user_id: str):
    client = blob_client()
    try:
        result = client.get(user_path(user_id), access=BLOB_ACCESS)
    except BlobNotFoundError:
        return None
    except Exception as e:
        raise HTTPException(500, f"Could not read registration file: {e}")

    if result is None or result.status_code != 200 or result.stream is None:
        return None

    chunks = []
    for chunk in result.stream:
        chunks.append(chunk)
    return json.loads(b"".join(chunks).decode("utf-8"))


def all_users():
    client = blob_client()
    users = []
    cursor = None
    try:
        while True:
            page = client.list_objects(prefix=USERS_PREFIX, cursor=cursor, limit=1000)
            for item in page.blobs:
                user_id = item.pathname[len(USERS_PREFIX):-5]
                user = load_user(user_id)
                if user:
                    users.append(user)
            if not page.has_more:
                break
            cursor = page.cursor
        return users
    except Exception as e:
        raise HTTPException(500, f"Could not check registration files: {e}")


class Register(BaseModel):
    full_name: str = Field(min_length=2, max_length=80)
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    role: str
    resort_name: str = Field(min_length=2, max_length=100)


class Login(BaseModel):
    user_id: str
    password: str


def token(u):
    return jwt.encode(
        {
            "sub": u["user_id"],
            "user_id": u["user_id"],
            "role": u["role"],
            "name": u["full_name"],
            "exp": datetime.now(timezone.utc) + timedelta(hours=12),
        },
        SECRET,
        algorithm="HS256",
    )


def demo(role):
    return {
        "_id": "demo",
        "user_id": "DEMO-" + role.upper(),
        "full_name": "Demo User",
        "email": "demo@resortos.local",
        "role": role,
        "role_name": ROLES[role],
        "resort_name": "Ocean View Resort",
    }


def current(authorization: str | None = Header(default=None)):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(401, "Missing authentication token")
    try:
        payload = jwt.decode(authorization[7:], SECRET, algorithms=["HS256"])
    except jwt.PyJWTError:
        raise HTTPException(401, "Invalid or expired token")

    if payload.get("sub") == "demo":
        return demo(payload["role"])

    user = load_user(payload.get("sub", ""))
    if not user:
        raise HTTPException(401, "User not found")
    return user_public(user)


app = FastAPI(title="Resort OS")
app.mount("/static", StaticFiles(directory=BASE / "frontend"), name="static")





@app.get("/")
def home(request: Request):
    return templates.TemplateResponse(
        "landing.html",
        {"request": request}
    )

@app.get("/ai")
def AI():
    return ai._call_ai

@app.post("/users")
def create_db(
    gst_id: int,
    gst_name: str,
    rooms_alt: int,
    amt:int,
    status:str,
    transaction_due: datetime,
    db: Session = Depends(get_db),
):
    database = resort_db.dashboard(
        gst_id=gst_id,
        gst_name=gst_name,
        rooms_alt=rooms_alt,
        amt=amt,
        status=status,
        transaction_due=transaction_due,
    )

    db.add(database)
    db.commit()
    db.refresh(database)

    return database

@app.get("/db")
def get_users(db: Session = Depends(get_db)):
    return db.query(resort_db.dashboard).all()

@app.get("/dashboard")
def dashboard(request: Request):
    return templates.TemplateResponse(
        "dashboard.html",
        {
            "request": request,
            "current_user": {
                "name": "Admin",
                "role": "admin"
            }
        }
    )

@app.get("/rooms")
def rooms(request: Request):
    rooms_data = []

    return templates.TemplateResponse(
        "rooms.html",
        {
            "request": request,
            "rooms": rooms_data
        }
    )

@app.get("/bookings")
def bookings(request: Request):
    bookings_data = []

    return templates.TemplateResponse(
        "bookings.html",
        {
            "request": request,
            "bookings": bookings_data
        }
    )

@app.post("/api/auth/register")
def register(x: Register):
    if x.role not in ROLES:
        raise HTTPException(400, "Invalid role")

    email = str(x.email).strip().lower()
    resort_name = x.resort_name.strip()
    full_name = x.full_name.strip()

    # Prevent duplicate email registrations by checking the persisted Blob files.
    for existing in all_users():
        if existing.get("email", "").lower() == email:
            raise HTTPException(409, "Email already registered")

    # Stable, readable User ID without relying on a database counter.
    prefix = x.role.upper()[:4]
    for _ in range(10):
        uid = f"{prefix}-{secrets.token_hex(3).upper()}"
        if load_user(uid) is None:
            break
    else:
        raise HTTPException(500, "Could not generate a unique User ID")

    password_hash = bcrypt.hashpw(x.password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
    user = {
        "user_id": uid,
        "full_name": full_name,
        "email": email,
        "password_hash": password_hash,
        "role": x.role,
        "role_name": ROLES[x.role],
        "resort_name": resort_name,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }

    save_user(user)
    public_user = user_public(user)
    return {"token": token(public_user), "user": public_user}


@app.post("/api/auth/login")
def login(x: Login):
    uid = x.user_id.strip().upper()
    if uid.startswith("DEMO-") and uid[5:].lower() in ROLES and x.password == "demo1234":
        user = demo(uid[5:].lower())
        return {"token": token(user), "user": user}

    user = load_user(uid)
    if not user or not bcrypt.checkpw(
        x.password.encode("utf-8"), user["password_hash"].encode("utf-8")
    ):
        raise HTTPException(401, "Invalid User ID or password")

    public_user = user_public(user)
    return {"token": token(public_user), "user": public_user}


@app.get("/api/auth/me")
def me(u=Depends(current)):
    return u


@app.get("/api/auth/registered-users")
def registered_users(u=Depends(current)):
    # Kept as an authenticated endpoint for future admin screens.
    return {"users": [user_public(user) for user in all_users()]}


@app.get("/{path:path}")
def frontend(path: str):
    if path.startswith("api/"):
        raise HTTPException(404)
    return FileResponse(BASE / "frontend" / "index.html")
