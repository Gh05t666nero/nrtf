from fastapi import FastAPI, Depends, HTTPException, status, Header
from pydantic import BaseModel, validator
from typing import List, Dict, Optional, Set, Any
import httpx
import uuid
import logging
import asyncio
import os
import json
import time
from datetime import datetime
from enum import Enum

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("orchestrator")

# Initialize FastAPI
app = FastAPI(
    title="Network Resilience Test Orchestrator",
    description="Coordinates test execution across services",
    version="1.0.0"
)

# Service URLs (would come from environment variables in production)
HTTP_MODULE_URL = os.getenv("HTTP_MODULE_URL", "http://http-module:8001")
TCP_MODULE_URL = os.getenv("TCP_MODULE_URL", "http://tcp-module:8002")
DNS_MODULE_URL = os.getenv("DNS_MODULE_URL", "http://dns-module:8003")
PROXY_SERVICE_URL = os.getenv("PROXY_SERVICE_URL", "http://proxy-service:8010")

# Test storage
# In production, this would be a database
tests = {}
test_results = {}


# Models
class TestStatus(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    STOPPED = "stopped"


class ProtocolType(str, Enum):
    HTTP = "http"
    TCP = "tcp"
    UDP = "udp"
    DNS = "dns"
    ICMP = "icmp"


class TestRequest(BaseModel):
    target: str
    method: str
    duration: int
    threads: int
    proxy_type: Optional[int] = None
    parameters: Optional[dict] = None

    @validator('duration')
    def validate_duration(cls, v):
        if v > 300:  # Maximum 5 minutes for safety
            raise ValueError('Duration cannot exceed 300 seconds')
        return v

    @validator('threads')
    def validate_threads(cls, v):
        if v > 1000:  # Maximum 1000 threads
            raise ValueError('Threads cannot exceed 1000')
        return v

    @validator('target')
    def validate_target(cls, v):
        # Basic validation - in production you'd have a more
        # comprehensive check and authorization verification
        if not v:
            raise ValueError('Target cannot be empty')
        return v


class TestResponse(BaseModel):
    id: str
    target: str
    method: str
    status: TestStatus
    start_time: Optional[float] = None
    end_time: Optional[float] = None
    user: str


class MethodInfo(BaseModel):
    name: str
    protocol: ProtocolType
    description: str
    parameters: Optional[Dict[str, Any]] = None


# Available methods - these would be fetched dynamically from modules in production
AVAILABLE_METHODS = {
    # HTTP Methods
    "HTTP_FLOOD": MethodInfo(
        name="HTTP_FLOOD",
        protocol=ProtocolType.HTTP,
        description="High volume HTTP GET request flood",
        parameters={"rpc": "Requests per connection"}
    ),
    "HTTP_BYPASS": MethodInfo(
        name="HTTP_BYPASS",
        protocol=ProtocolType.HTTP,
        description="HTTP request flood with WAF bypass techniques"
    ),
    "SSL_FLOOD": MethodInfo(
        name="SSL_FLOOD",
        protocol=ProtocolType.HTTP,
        description="HTTPS request flood with TLS renegotiation"
    ),
    "SLOW_LORIS": MethodInfo(
        name="SLOW_LORIS",
        protocol=ProtocolType.HTTP,
        description="Slow-rate HTTP request flood that keeps connections open"
    ),

    # TCP Methods
    "TCP_FLOOD": MethodInfo(
        name="TCP_FLOOD",
        protocol=ProtocolType.TCP,
        description="High volume TCP SYN flood"
    ),
    "TCP_CONNECTION": MethodInfo(
        name="TCP_CONNECTION",
        protocol=ProtocolType.TCP,
        description="TCP connection flood that establishes full connections"
    ),

    # UDP Methods
    "UDP_FLOOD": MethodInfo(
        name="UDP_FLOOD",
        protocol=ProtocolType.UDP,
        description="High volume UDP packet flood"
    ),

    # DNS Methods
    "DNS_FLOOD": MethodInfo(
        name="DNS_FLOOD",
        protocol=ProtocolType.DNS,
        description="DNS query flood targeting DNS servers"
    ),

    # ICMP Methods
    "ICMP_FLOOD": MethodInfo(
        name="ICMP_FLOOD",
        protocol=ProtocolType.ICMP,
        description="ICMP echo request flood"
    )
}


# Helper functions
def get_service_url(method: str) -> str:
    """
    Determine which service to route a test to based on the method
    """
    protocol = AVAILABLE_METHODS.get(method)
    if not protocol:
        raise ValueError(f"Unknown method: {method}")

    if protocol.protocol == ProtocolType.HTTP:
        return HTTP_MODULE_URL
    elif protocol.protocol in [ProtocolType.TCP, ProtocolType.UDP]:
        return TCP_MODULE_URL
    elif protocol.protocol == ProtocolType.DNS:
        return DNS_MODULE_URL
    else:
        raise ValueError(f"Unsupported protocol: {protocol.protocol}")


async def check_method_exists(method: str):
    """
    Verify that the requested method exists
    """
    if method not in AVAILABLE_METHODS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unknown method: {method}. Available methods: {', '.join(AVAILABLE_METHODS.keys())}"
        )


async def get_proxies(proxy_type: int, count: int):
    """
    Get proxies from the proxy service
    """
    try:
        params = {"count": count}

        # Jika proxy_type tidak sama dengan 0, sertakan dalam parameter
        # Proxy type 0 berarti "semua tipe", jadi kita tidak mengirim parameter type
        # sehingga proxy service akan mengembalikan semua tipe
        if proxy_type is not None and proxy_type != 0:
            params["type"] = proxy_type

        logger.info(f"Requesting proxies with params: {params}")

        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{PROXY_SERVICE_URL}/proxies",
                params=params
            )

            # Check for error response
            if response.status_code >= 400:
                logger.error(f"Proxy service error: {response.text}")
                return []

            proxies_data = response.json()

            # Pastikan data yang dikembalikan adalah list
            if not isinstance(proxies_data, list):
                logger.error(f"Proxy service returned non-list data: {proxies_data}")
                return []

            # Pastikan hanya field yang diperlukan oleh modul tes yang disertakan
            cleaned_proxies = []
            for proxy in proxies_data:
                cleaned_proxy = {
                    "host": proxy.get("host"),
                    "port": proxy.get("port"),
                    "type": proxy.get("type"),
                    "username": proxy.get("username", None),
                    "password": proxy.get("password", None)
                }
                cleaned_proxies.append(cleaned_proxy)

            logger.info(f"Received {len(cleaned_proxies)} proxies from proxy service")
            return cleaned_proxies
    except httpx.RequestError as e:
        logger.error(f"Error communicating with proxy service: {e}")
        return []


# Request verification
async def verify_user(x_user: str = Header(...)):
    """
    Verify the user from the X-User header
    This would be more comprehensive in a production system
    """
    if not x_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="X-User header is required"
        )
    return x_user


# Routes
@app.post("/test", response_model=TestResponse)
async def create_test(
        test_request: TestRequest,
        user: str = Depends(verify_user)
):
    """
    Create a new test with the specified parameters
    """
    # Validate method
    await check_method_exists(test_request.method)

    # Generate test ID
    test_id = str(uuid.uuid4())

    # Create test record
    test = {
        "id": test_id,
        "target": test_request.target,
        "method": test_request.method,
        "status": TestStatus.QUEUED,
        "duration": test_request.duration,
        "threads": test_request.threads,
        "proxy_type": test_request.proxy_type,
        "parameters": test_request.parameters or {},
        "user": user,
        "created_at": time.time()
    }

    tests[test_id] = test

    # Start test execution asynchronously
    asyncio.create_task(execute_test(test_id, test))

    return TestResponse(
        id=test_id,
        target=test_request.target,
        method=test_request.method,
        status=TestStatus.QUEUED,
        user=user
    )


async def execute_test(test_id: str, test: dict):
    """
    Execute a test by sending it to the appropriate service and monitor its progress
    """
    try:
        # Update test status
        test["status"] = TestStatus.RUNNING
        test["start_time"] = time.time()

        # Get service URL based on method
        service_url = get_service_url(test["method"])

        # Get proxies if needed
        proxies = None
        if test["proxy_type"] is not None:
            proxies = await get_proxies(test["proxy_type"], test["threads"])

        # Prepare test parameters
        test_params = {
            "target": test["target"],
            "method": test["method"],
            "duration": test["duration"],
            "threads": test["threads"],
            "parameters": test["parameters"]
        }

        if proxies:
            # Pastikan proxies berupa list sebelum ditambahkan ke test_params
            if isinstance(proxies, list):
                test_params["proxies"] = proxies
                logger.info(f"Using {len(proxies)} proxies for test {test_id}")
            else:
                logger.error(f"Proxies is not a list, type: {type(proxies)}, value: {proxies}")
                # Jangan tambahkan proxies jika bukan list untuk menghindari error validasi

        # Send test to appropriate service to initiate
        async with httpx.AsyncClient() as client:
            # Initiate the test but don't wait for completion
            response = await client.post(
                f"{service_url}/execute",
                json=test_params,
                timeout=30  # Short timeout for just starting the test
            )

            if response.status_code != 200:
                raise Exception(f"Failed to start test: {response.text}")

            # Get the test_id from the module
            module_test_id = response.json().get("test_id")
            if not module_test_id:
                raise Exception("Module didn't return a test_id")

            logger.info(f"Test {test_id} started on {service_url} with module_test_id {module_test_id}")

            # Poll the test status until it completes or the duration (plus buffer) has elapsed
            expected_end_time = test["start_time"] + test["duration"] + 60  # Add 60 second buffer
            polling_interval = 5  # Poll every 5 seconds

            while time.time() < expected_end_time:
                # Check if test was manually stopped
                if test["status"] == TestStatus.STOPPED:
                    logger.info(f"Test {test_id} was manually stopped")
                    break

                # Poll status from the service
                try:
                    status_response = await client.get(
                        f"{service_url}/status/{module_test_id}",
                        timeout=10
                    )

                    if status_response.status_code == 200:
                        module_status = status_response.json()

                        # If test is completed or failed in the module, we're done
                        if module_status.get("status") in ["completed", "failed", "stopped"]:
                            logger.info(f"Test {test_id} completed with status {module_status.get('status')}")

                            # Update our status and store results
                            test["status"] = TestStatus.COMPLETED if module_status.get(
                                "status") == "completed" else TestStatus.FAILED
                            test["end_time"] = time.time()

                            # Store results if available
                            if "results" in module_status:
                                test_results[test_id] = module_status["results"]
                            break

                except httpx.RequestError as e:
                    logger.warning(f"Error polling test status: {e}")

                # Wait before polling again
                await asyncio.sleep(polling_interval)

            # If we've reached here and test is still running, it's probably timed out
            if test["status"] == TestStatus.RUNNING:
                logger.warning(f"Test {test_id} timed out after expected duration")

                # Try to stop the test
                try:
                    await client.delete(
                        f"{service_url}/execute/{module_test_id}",
                        timeout=10
                    )
                except Exception as e:
                    logger.error(f"Error stopping timed out test: {e}")

                test["status"] = TestStatus.COMPLETED
                test["end_time"] = time.time()
                test_results[test_id] = {"message": "Test completed after maximum duration"}

    except Exception as e:
        logger.error(f"Error executing test {test_id}: {e}")
        test["status"] = TestStatus.FAILED
        test["end_time"] = time.time()
        test_results[test_id] = {"error": str(e)}


@app.get("/test/{test_id}", response_model=TestResponse)
async def get_test(
        test_id: str,
        user: str = Depends(verify_user)
):
    """
    Get details for a specific test
    """
    if test_id not in tests:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Test not found"
        )

    test = tests[test_id]

    # Check if user has access to this test
    if test["user"] != user:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have access to this test"
        )

    return TestResponse(
        id=test_id,
        target=test["target"],
        method=test["method"],
        status=test["status"],
        start_time=test.get("start_time"),
        end_time=test.get("end_time"),
        user=test["user"]
    )


@app.get("/tests", response_model=List[TestResponse])
async def get_tests(
        user: str = Depends(verify_user)
):
    """
    Get all tests for the current user
    """
    user_tests = []
    for test_id, test in tests.items():
        if test["user"] == user:
            user_tests.append(
                TestResponse(
                    id=test_id,
                    target=test["target"],
                    method=test["method"],
                    status=test["status"],
                    start_time=test.get("start_time"),
                    end_time=test.get("end_time"),
                    user=test["user"]
                )
            )

    return user_tests


@app.delete("/test/{test_id}", response_model=TestResponse)
async def stop_test(
        test_id: str,
        user: str = Depends(verify_user)
):
    """
    Stop a running test
    """
    logger.info(f"Received request to stop test {test_id} from user {user}")

    if test_id not in tests:
        logger.warning(f"Test {test_id} not found")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Test not found"
        )

    test = tests[test_id]

    # Check if user has access to this test
    if test["user"] != user:
        logger.warning(f"User {user} does not have access to test {test_id}")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have access to this test"
        )

    # Allow stopping tests in any state, but only mark as stopped if running
    if test["status"] != TestStatus.RUNNING:
        logger.info(f"Test {test_id} is not running (current status: {test['status']}). Returning current state.")
        return TestResponse(
            id=test_id,
            target=test["target"],
            method=test["method"],
            status=test["status"],
            start_time=test.get("start_time"),
            end_time=test.get("end_time"),
            user=test["user"]
        )

    # Attempt to stop the test
    try:
        service_url = get_service_url(test["method"])
        logger.info(f"Stopping test {test_id} on service {service_url}")

        # Find the module_test_id (either from the test info or results)
        module_test_id = test.get("module_test_id")

        if not module_test_id:
            for result_id, result in test_results.items():
                if isinstance(result, dict) and result.get("test_id") == test_id:
                    module_test_id = result_id
                    break

        if not module_test_id:
            # If we can't find it, use the test_id as fallback
            module_test_id = test_id
            logger.warning(f"Could not find module_test_id for test {test_id}, using test_id as fallback")

        # Use a longer timeout for the stop request
        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                logger.info(f"Sending DELETE request to {service_url}/execute/{module_test_id}")
                response = await client.delete(
                    f"{service_url}/execute/{module_test_id}"
                )

                if response.status_code >= 400:
                    logger.warning(
                        f"Received error response when stopping test: {response.status_code} - {response.text}")
                    # Continue with marking test as stopped even if module reports an error

                logger.info(f"Successfully sent stop request for test {test_id}")
            except Exception as e:
                logger.error(f"Error communicating with module service: {str(e)}")
                # Continue with marking test as stopped even if communication fails

        # Mark the test as stopped regardless of the module response
        test["status"] = TestStatus.STOPPED
        test["end_time"] = time.time()
        logger.info(f"Marked test {test_id} as stopped")

    except Exception as e:
        logger.error(f"Error stopping test {test_id}: {str(e)}")
        # Still mark test as stopped even if there was an error
        test["status"] = TestStatus.STOPPED
        test["end_time"] = time.time()
        logger.info(f"Marked test {test_id} as stopped despite error")

    return TestResponse(
        id=test_id,
        target=test["target"],
        method=test["method"],
        status=test["status"],
        start_time=test.get("start_time"),
        end_time=test.get("end_time"),
        user=test["user"]
    )


@app.get("/methods", response_model=Dict[str, MethodInfo])
async def get_methods():
    """
    Get all available test methods
    """
    return AVAILABLE_METHODS


@app.get("/test/{test_id}/results")
async def get_test_results(
        test_id: str,
        user: str = Depends(verify_user)
):
    """
    Get results for a specific test
    """
    if test_id not in tests:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Test not found"
        )

    test = tests[test_id]

    # Check if user has access to this test
    if test["user"] != user:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have access to this test"
        )

    # Check if test is completed
    if test["status"] not in [TestStatus.COMPLETED, TestStatus.FAILED, TestStatus.STOPPED]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Test results not available for test with status {test['status']}"
        )

    # Return test results
    if test_id in test_results:
        return test_results[test_id]
    else:
        return {"message": "No results available"}


@app.get("/health")
async def health_check():
    """
    Health check endpoint
    """
    return {"status": "healthy"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)