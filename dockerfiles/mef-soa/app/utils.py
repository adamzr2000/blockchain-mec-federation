import httpx
import time
from jose import jwt, JWTError

async def post_json(url, data, token=None):
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    async with httpx.AsyncClient() as client:
        r = await client.post(url, json=data, headers=headers)
        r.raise_for_status()
        return r.json()

async def call_meo(meo_url, endpoint, params):
    # Helper to call MEO (your existing orchestrator)
    url = f"{meo_url}/{endpoint}"
    async with httpx.AsyncClient() as client:
        r = await client.post(url, params=params, timeout=60)
        r.raise_for_status()
        return r.json()

# Shared secret for demo (in real deployments each domain would have its own)
SECRET_KEY = "super-secret-demo-key"
ALGORITHM = "HS256"

def create_access_token(data: dict, expires_in: int = 60) -> str:
    to_encode = data.copy()
    expire = int(time.time()) + expires_in
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

def verify_access_token(token: str) -> dict:
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except JWTError as e:
        raise ValueError(f"Invalid token: {e}")