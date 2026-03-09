from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from jose import JWTError, jwt
from passlib.context import CryptContext
from pydantic import BaseModel
from datetime import datetime, timedelta
import ollama
import sys
import os
import time

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from safety_filter.filter import check_safety


# --- Config ---
SECRET_KEY = "your-secret-key-change-in-production"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30


# --- Setup ---
app = FastAPI(title="Safety Co-Pilot Gateway", version="1.0")
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto", bcrypt__rounds=12)
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")


SYSTEM_PROMPT = """You are a robot navigation controller.
Convert natural language instructions into robot commands.
Always respond with a JSON object containing:
- "action": the movement type (navigate, stop, rotate)
- "target": destination as a string
- "speed": slow/medium/fast
- "reasoning": brief explanation"""


# --- Models ---
class CommandRequest(BaseModel):
    instruction: str


class Token(BaseModel):
    access_token: str
    token_type: str


# --- Fake user DB ---
USERS_DB = {
    "admin": {
        "username": "admin",
        "password": "secret",  # plain for dev only
        "role": "operator"
    }
}


# --- Auth helpers ---
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
    total_start = time.perf_counter()

    # Step 1: Send to LLM
    llm_start = time.perf_counter()
    response = ollama.chat(
        model='llama3.1:8b',
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": request.instruction}
        ]
    )
    raw = response['message']['content']
    llm_latency_ms = round((time.perf_counter() - llm_start) * 1000, 2)

    # Step 2: Run through safety filter
    filter_start = time.perf_counter()
    result = check_safety(raw)
    filter_latency_ms = round((time.perf_counter() - filter_start) * 1000, 2)

    total_latency_ms = round((time.perf_counter() - total_start) * 1000, 2)

    print(f"[LATENCY] LLM: {llm_latency_ms}ms | Filter: {filter_latency_ms}ms | Total: {total_latency_ms}ms")

    return {
        "user": current_user,
        "instruction": request.instruction,
        "status": result["status"],
        "command": result["command"] if result["status"] == "ALLOWED" else None,
        "violations": result["violations"],
        "timestamp": result["timestamp"],
        "latency": {
            "llm_ms": llm_latency_ms,
            "filter_ms": filter_latency_ms,
            "total_ms": total_latency_ms
        }
    }


@app.get("/health")
async def health():
    return {"status": "online", "service": "Safety Co-Pilot Gateway"}
