from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from jose import JWTError, jwt
from passlib.context import CryptContext
from pydantic import BaseModel
from datetime import datetime, timedelta
import ollama
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from safety_filter.filter import check_safety

# --- Config ---
SECRET_KEY = "your-secret-key-change-in-production"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

# --- Fake user DB (replace with real DB later) ---
USERS_DB = {
    "admin": {
        "username": "admin",
        "hashed_password": "$2b$12$EixZaYVK1fsbw1ZfbX3OXePaWxn96p36WQoeG6Lruj3vjPGga31lW",  # "secret"
        "role": "operator"
    }
}

SYSTEM_PROMPT = """You are a robot navigation controller.
Convert natural language instructions into robot commands.
Always respond with a JSON object containing:
- "action": the movement type (navigate, stop, rotate)
- "target": destination as a string
- "speed": slow/medium/fast
- "reasoning": brief explanation"""

# --- Setup ---
app = FastAPI(title="Safety Co-Pilot Gateway", version="1.0")
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto", bcrypt__rounds=12)
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

# --- Models ---
class CommandRequest(BaseModel):
    instruction: str

class Token(BaseModel):
    access_token: str
    token_type: str

# --- Auth helpers ---
# Simplified for development — replace with proper hashing in production
USERS_DB = {
    "admin": {
        "username": "admin",
        "password": "secret",  # plain for dev only
        "role": "operator"
    }
}

def authenticate_user(username: str, password: str):
    user = USERS_DB.get(username)
    if not user or user["password"] != password:
        return None
    return user


def create_access_token(data: dict):
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

async def get_current_user(token: str = Depends(oauth2_scheme)):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username = payload.get("sub")
        if username is None:
            raise HTTPException(status_code=401, detail="Invalid token")
        return username
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")

# --- Routes ---
@app.post("/token", response_model=Token)
async def login(form_data: OAuth2PasswordRequestForm = Depends()):
    user = authenticate_user(form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password"
        )
    token = create_access_token({"sub": user["username"]})
    return {"access_token": token, "token_type": "bearer"}

@app.post("/command")
async def send_command(
    request: CommandRequest,
    current_user: str = Depends(get_current_user)
):
    # Step 1: Send to LLM
    response = ollama.chat(
        model='llama3.1:8b',
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": request.instruction}
        ]
    )
    raw = response['message']['content']

    # Step 2: Run through safety filter
    result = check_safety(raw)

    return {
        "user": current_user,
        "instruction": request.instruction,
        "status": result["status"],
        "command": result["command"] if result["status"] == "ALLOWED" else None,
        "violations": result["violations"],
        "timestamp": result["timestamp"]
    }

@app.get("/health")
async def health():
    return {"status": "online", "service": "Safety Co-Pilot Gateway"}
