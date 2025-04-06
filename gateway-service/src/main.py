from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from pydantic import BaseModel
from typing import List, Optional
import uvicorn
import os
import logging
import httpx
import json
from datetime import datetime, timedelta
import jwt
from passlib.context import CryptContext

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("api-gateway")

# Initialize FastAPI
app = FastAPI(
    title="Network Resilience Testing Framework",
    description="API Gateway for network resilience testing",
    version="1.0.0"
)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Restrict in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Authentication configuration
SECRET_KEY = os.getenv("SECRET_KEY", "development_secret_key_change_in_production")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

# Service URLs (would be environment variables in production)
ORCHESTRATOR_URL = os.getenv("ORCHESTRATOR_URL", "http://orchestrator:8000")

# HTTP client settings
HTTP_TIMEOUT = float(os.getenv("HTTP_TIMEOUT", "30.0"))  # 30 seconds default timeout


# Models
class Token(BaseModel):
    access_token: str
    token_type: str


class TokenData(BaseModel):
    username: Optional[str] = None


class User(BaseModel):
    username: str
    email: Optional[str] = None
    full_name: Optional[str] = None
    disabled: Optional[bool] = None


class UserInDB(User):
    hashed_password: str


class TestRequest(BaseModel):
    target: str
    method: str
    duration: int
    threads: int
    proxy_type: Optional[int] = None
    parameters: Optional[dict] = None


# Mock database for demo purposes
# In production, use a real database
fake_users_db = {
    "testuser": {
        "username": "testuser",
        "full_name": "Test User",
        "email": "test@example.com",
        "hashed_password": pwd_context.hash("testpassword"),
        "disabled": False,
    }
}


# Authentication functions
def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)


def get_user(db, username: str):
    if username in db:
        user_dict = db[username]
        return UserInDB(**user_dict)


def authenticate_user(fake_db, username: str, password: str):
    user = get_user(fake_db, username)
    if not user:
        return False
    if not verify_password(password, user.hashed_password):
        return False
    return user


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


async def get_current_user(token: str = Depends(oauth2_scheme)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
        token_data = TokenData(username=username)
    except jwt.PyJWTError:
        raise credentials_exception
    user = get_user(fake_users_db, username=token_data.username)
    if user is None:
        raise credentials_exception
    return user


async def get_current_active_user(current_user: User = Depends(get_current_user)):
    if current_user.disabled:
        raise HTTPException(status_code=400, detail="Inactive user")
    return current_user


# Helper function for making HTTP requests with retry
async def make_request(method, url, **kwargs):
    """Make an HTTP request with retry logic"""
    max_retries = 3
    timeout = kwargs.pop('timeout', HTTP_TIMEOUT)

    for attempt in range(max_retries):
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                if method.lower() == 'get':
                    response = await client.get(url, **kwargs)
                elif method.lower() == 'post':
                    response = await client.post(url, **kwargs)
                elif method.lower() == 'delete':
                    response = await client.delete(url, **kwargs)
                else:
                    raise ValueError(f"Unsupported HTTP method: {method}")

                return response
        except httpx.RequestError as e:
            logger.error(f"Request error (attempt {attempt + 1}/{max_retries}): {e}")
            if attempt == max_retries - 1:  # Last attempt
                raise
            # Wait a bit before retrying
            await asyncio.sleep(1 * (attempt + 1))  # Exponential backoff


# Routes
@app.post("/token", response_model=Token)
async def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends()):
    user = authenticate_user(fake_users_db, form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.username}, expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer"}


@app.get("/users/me/", response_model=User)
async def read_users_me(current_user: User = Depends(get_current_active_user)):
    return current_user


@app.post("/api/test")
async def create_test(
        test_request: TestRequest,
        current_user: User = Depends(get_current_active_user)
):
    """
    Create a new test with the specified parameters
    """
    logger.info(f"User {current_user.username} initiated test against {test_request.target}")

    # Input validation
    if test_request.duration > 300:  # Example limit of 5 minutes
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Test duration exceeds maximum allowed (300 seconds)"
        )

    # Forward request to orchestrator
    try:
        response = await make_request(
            'post',
            f"{ORCHESTRATOR_URL}/test",
            json=test_request.dict(),
            headers={"X-User": current_user.username}
        )
        return response.json()
    except httpx.RequestError as e:
        logger.error(f"Error communicating with orchestrator: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Service temporarily unavailable"
        )


@app.get("/api/tests")
async def get_tests(current_user: User = Depends(get_current_active_user)):
    """
    Get all tests for the current user
    """
    try:
        response = await make_request(
            'get',
            f"{ORCHESTRATOR_URL}/tests",
            headers={"X-User": current_user.username}
        )
        return response.json()
    except httpx.RequestError as e:
        logger.error(f"Error communicating with orchestrator: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Service temporarily unavailable"
        )


@app.get("/api/test/{test_id}")
async def get_test(
        test_id: str,
        current_user: User = Depends(get_current_active_user)
):
    """
    Get details for a specific test
    """
    try:
        response = await make_request(
            'get',
            f"{ORCHESTRATOR_URL}/test/{test_id}",
            headers={"X-User": current_user.username}
        )
        if response.status_code == 404:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Test not found"
            )
        return response.json()
    except httpx.RequestError as e:
        logger.error(f"Error communicating with orchestrator: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Service temporarily unavailable"
        )


@app.delete("/api/test/{test_id}")
async def stop_test(
        test_id: str,
        current_user: User = Depends(get_current_active_user)
):
    """
    Stop a running test
    """
    try:
        logger.info(f"User {current_user.username} attempting to stop test {test_id}")

        # Increase timeout for stop operations
        response = await make_request(
            'delete',
            f"{ORCHESTRATOR_URL}/test/{test_id}",
            headers={"X-User": current_user.username},
            timeout=60.0  # Longer timeout for stopping tests
        )

        if response.status_code == 404:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Test not found"
            )

        logger.info(f"Successfully stopped test {test_id}")
        return response.json()
    except httpx.RequestError as e:
        logger.error(f"Error communicating with orchestrator when stopping test {test_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Service temporarily unavailable. Error: {str(e)}"
        )


@app.get("/api/test/{test_id}/results")
async def get_test_results(
        test_id: str,
        current_user: User = Depends(get_current_active_user)
):
    """
    Get results for a specific test
    """
    try:
        response = await make_request(
            'get',
            f"{ORCHESTRATOR_URL}/test/{test_id}/results",
            headers={"X-User": current_user.username}
        )
        if response.status_code == 404:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Test results not found"
            )
        return response.json()
    except httpx.RequestError as e:
        logger.error(f"Error communicating with orchestrator: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Service temporarily unavailable"
        )


@app.get("/api/methods")
async def get_methods(current_user: User = Depends(get_current_active_user)):
    """
    Get all available test methods
    """
    try:
        response = await make_request(
            'get',
            f"{ORCHESTRATOR_URL}/methods"
        )
        return response.json()
    except httpx.RequestError as e:
        logger.error(f"Error communicating with orchestrator: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Service temporarily unavailable"
        )


@app.get("/health")
async def health_check():
    """
    Health check endpoint
    """
    try:
        response = await make_request(
            'get',
            f"{ORCHESTRATOR_URL}/health",
            timeout=5.0
        )
        orchestrator_status = response.json().get("status", "unknown")
        return {
            "status": "healthy",
            "orchestrator": orchestrator_status
        }
    except Exception as e:
        logger.warning(f"Health check failed: {e}")
        return {
            "status": "degraded",
            "orchestrator": "unreachable",
            "error": str(e)
        }


import asyncio

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8080, reload=True)