from fastapi import FastAPI, HTTPException, Query, BackgroundTasks
from pydantic import BaseModel, validator
from typing import List, Dict, Optional, Set, Any, Union
import httpx
import logging
import asyncio
import time
import os
import random
import uuid
import re
import concurrent.futures
from enum import Enum
import threading
import socket
import socks
from datetime import datetime, timedelta

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("proxy-service")

# Initialize FastAPI
app = FastAPI(
    title="Proxy Management Service",
    description="Manages proxy acquisition, validation, and rotation",
    version="1.0.0"
)


# Global proxy storage
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
    last_checked: Optional[float] = None
    is_valid: Optional[bool] = None
    response_time: Optional[float] = None

    def __hash__(self):
        return hash((self.host, self.port, self.type))

    def __eq__(self, other):
        if not isinstance(other, Proxy):
            return False
        return (self.host, self.port, self.type) == (other.host, other.port, other.type)

    def as_url(self) -> str:
        auth = f"{self.username}:{self.password}@" if self.username and self.password else ""
        proto = "http" if self.type == ProxyType.HTTP else f"socks{self.type}"
        return f"{proto}://{auth}{self.host}:{self.port}"

    def as_dict(self) -> dict:
        return {
            "host": self.host,
            "port": self.port,
            "type": self.type,
            "username": self.username,
            "password": self.password,
            "last_checked": self.last_checked,
            "is_valid": self.is_valid,
            "response_time": self.response_time
        }


# Proxy sources configuration (would be loaded from environment or config)
PROXY_SOURCES = [
    # HTTP Proxy Sources
    {"url": "https://raw.githubusercontent.com/TheSpeedX/PROXY-List/master/http.txt", "type": ProxyType.HTTP},
    {"url": "https://api.proxyscrape.com/v2/?request=getproxies&protocol=http", "type": ProxyType.HTTP},
    {"url": "https://www.proxy-list.download/api/v1/get?type=http", "type": ProxyType.HTTP},

    # SOCKS4 Proxy Sources
    {"url": "https://raw.githubusercontent.com/TheSpeedX/PROXY-List/master/socks4.txt", "type": ProxyType.SOCKS4},
    {"url": "https://api.proxyscrape.com/v2/?request=getproxies&protocol=socks4", "type": ProxyType.SOCKS4},
    {"url": "https://www.proxy-list.download/api/v1/get?type=socks4", "type": ProxyType.SOCKS4},

    # SOCKS5 Proxy Sources
    {"url": "https://raw.githubusercontent.com/TheSpeedX/PROXY-List/master/socks5.txt", "type": ProxyType.SOCKS5},
    {"url": "https://api.proxyscrape.com/v2/?request=getproxies&protocol=socks5", "type": ProxyType.SOCKS5},
    {"url": "https://www.proxy-list.download/api/v1/get?type=socks5", "type": ProxyType.SOCKS5}
]

# Global proxy storage
proxies = {
    ProxyType.HTTP: set(),
    ProxyType.SOCKS4: set(),
    ProxyType.SOCKS5: set()
}

# IP and port regex
IP_PORT_REGEX = re.compile(r'(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}):(\d+)')

# Time variables
PROXY_REFRESH_INTERVAL = 3600  # Refresh proxies every hour
last_proxy_refresh = 0


# Counter class for statistics
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


# Statistics counters
stats = {
    "proxies_fetched": AtomicCounter(),
    "proxies_validated": AtomicCounter(),
    "valid_proxies": AtomicCounter(),
    "invalid_proxies": AtomicCounter()
}


# Helper functions
async def download_proxies_from_source(source):
    """
    Download proxies from a source URL
    """
    proxy_list = set()
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(source["url"], timeout=10.0)
            if response.status_code == 200:
                content = response.text
                matches = IP_PORT_REGEX.findall(content)

                for match in matches:
                    ip, port = match
                    try:
                        port = int(port)
                        if 0 < port <= 65535:
                            proxy = Proxy(host=ip, port=port, type=source["type"])
                            proxy_list.add(proxy)
                    except ValueError:
                        pass

                logger.info(f"Downloaded {len(proxy_list)} proxies from {source['url']}")
                stats["proxies_fetched"].increment(len(proxy_list))
                return proxy_list
            else:
                logger.warning(f"Failed to download proxies from {source['url']}: {response.status_code}")
                return set()
    except Exception as e:
        logger.error(f"Error downloading proxies from {source['url']}: {e}")
        return set()


async def refresh_proxies():
    """
    Refresh the proxy list from all sources
    """
    global last_proxy_refresh

    # Download proxies from all sources
    all_proxies = {
        ProxyType.HTTP: set(),
        ProxyType.SOCKS4: set(),
        ProxyType.SOCKS5: set()
    }

    logger.info("Refreshing proxies from all sources")

    # Download proxies from all sources in parallel
    tasks = [download_proxies_from_source(source) for source in PROXY_SOURCES]
    results = await asyncio.gather(*tasks)

    # Process results
    for proxy_list in results:
        for proxy in proxy_list:
            all_proxies[proxy.type].add(proxy)

    # Update global proxy list
    for proxy_type in all_proxies:
        proxies[proxy_type].update(all_proxies[proxy_type])

    # Update last refresh time
    last_proxy_refresh = time.time()

    logger.info(f"Proxy refresh complete. HTTP: {len(proxies[ProxyType.HTTP])}, "
                f"SOCKS4: {len(proxies[ProxyType.SOCKS4])}, "
                f"SOCKS5: {len(proxies[ProxyType.SOCKS5])}")


async def validate_proxy(proxy):
    """
    Validate a proxy by attempting to connect through it
    """
    try:
        # Use httpx to validate HTTP proxies
        if proxy.type == ProxyType.HTTP:
            async with httpx.AsyncClient(
                    proxies=proxy.as_url(),
                    timeout=10.0,
                    verify=False
            ) as client:
                start_time = time.time()
                response = await client.get("http://httpbin.org/ip")
                end_time = time.time()

                if response.status_code == 200:
                    # Create a new proxy with updated values
                    return Proxy(
                        host=proxy.host,
                        port=proxy.port,
                        type=proxy.type,
                        username=proxy.username,
                        password=proxy.password,
                        is_valid=True,
                        response_time=end_time - start_time,
                        last_checked=time.time()
                    )
                else:
                    # Create a new proxy with updated values
                    return Proxy(
                        host=proxy.host,
                        port=proxy.port,
                        type=proxy.type,
                        username=proxy.username,
                        password=proxy.password,
                        is_valid=False,
                        last_checked=time.time()
                    )

        # Use socks library to validate SOCKS proxies
        else:
            # Use a separate thread for the blocking socket operations
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(
                    validate_socks_proxy,
                    proxy.host,
                    proxy.port,
                    proxy.type
                )
                result = await asyncio.wrap_future(future)

                if result:
                    # Create a new proxy with updated values
                    return Proxy(
                        host=proxy.host,
                        port=proxy.port,
                        type=proxy.type,
                        username=proxy.username,
                        password=proxy.password,
                        is_valid=True,
                        response_time=result,
                        last_checked=time.time()
                    )
                else:
                    # Create a new proxy with updated values
                    return Proxy(
                        host=proxy.host,
                        port=proxy.port,
                        type=proxy.type,
                        username=proxy.username,
                        password=proxy.password,
                        is_valid=False,
                        last_checked=time.time()
                    )

    except Exception as e:
        # Create a new proxy with updated values
        return Proxy(
            host=proxy.host,
            port=proxy.port,
            type=proxy.type,
            username=proxy.username,
            password=proxy.password,
            is_valid=False,
            last_checked=time.time()
        )


def validate_socks_proxy(host, port, proxy_type):
    """
    Validate a SOCKS proxy by connecting to a test server
    """
    try:
        s = socks.socksocket()
        s.set_proxy(
            proxy_type=socks.PROXY_TYPES[f'SOCKS{proxy_type}'] if proxy_type in [4, 5] else socks.HTTP,
            addr=host,
            port=port
        )
        s.settimeout(10)

        start_time = time.time()
        s.connect(("httpbin.org", 80))

        # Send a simple HTTP request
        s.send(b"GET /ip HTTP/1.1\r\nHost: httpbin.org\r\n\r\n")

        # Receive response
        response = s.recv(4096)
        end_time = time.time()

        s.close()

        if b"200 OK" in response:
            return end_time - start_time
        else:
            return None

    except Exception as e:
        return None


async def validate_proxies(proxy_type=None, count=100):
    """
    Validate a batch of proxies
    """
    # Get proxies to validate
    proxies_to_validate = []
    if proxy_type is None:
        # Get from all types
        for ptype in proxies:
            proxies_to_validate.extend(list(proxies[ptype])[:count])
    else:
        # Get from specific type
        proxies_to_validate.extend(list(proxies[proxy_type])[:count])

    # Validate in parallel
    logger.info(f"Validating {len(proxies_to_validate)} proxies")
    tasks = [validate_proxy(proxy) for proxy in proxies_to_validate]
    validated_proxies = await asyncio.gather(*tasks)

    stats["proxies_validated"].increment(len(validated_proxies))

    # Update proxy list with validation results
    for proxy in validated_proxies:
        # Remove any existing proxy with same key attributes
        proxies[proxy.type].discard(proxy)

        # Add back if valid
        if proxy.is_valid:
            stats["valid_proxies"].increment()
            proxies[proxy.type].add(proxy)
        else:
            stats["invalid_proxies"].increment()

    logger.info(f"Validation complete. Valid: {stats['valid_proxies'].value()}, "
                f"Invalid: {stats['invalid_proxies'].value()}")


async def startup_event():
    """
    Startup event handler
    """
    # Refresh proxies on startup
    await refresh_proxies()

    # Start validation
    await validate_proxies()


@app.on_event("startup")
async def on_startup():
    asyncio.create_task(startup_event())


# Routes
@app.get("/proxies")
async def get_proxies(
        type: Optional[int] = Query(None, description="Proxy type (1=HTTP, 4=SOCKS4, 5=SOCKS5)"),
        count: Optional[int] = Query(100, description="Number of proxies to return"),
        valid_only: Optional[bool] = Query(True, description="Return only validated proxies")
):
    """
    Get a list of proxies of the specified type
    """
    global last_proxy_refresh

    # Check if proxies need refresh
    if time.time() - last_proxy_refresh > PROXY_REFRESH_INTERVAL:
        asyncio.create_task(refresh_proxies())

    # Get proxies
    result = []
    if type is None:
        # Get from all types
        for proxy_type in proxies:
            proxy_list = list(proxies[proxy_type])
            if valid_only:
                proxy_list = [p for p in proxy_list if p.is_valid]
            result.extend(proxy_list)
    else:
        # Check if proxy type is valid
        if type not in [1, 4, 5]:
            raise HTTPException(
                status_code=400,
                detail="Invalid proxy type. Must be 1 (HTTP), 4 (SOCKS4), or 5 (SOCKS5)"
            )

        # Get from specific type
        proxy_type = ProxyType(type)
        proxy_list = list(proxies[proxy_type])
        if valid_only:
            proxy_list = [p for p in proxy_list if p.is_valid]
        result.extend(proxy_list)

    # Limit to count
    result = result[:count]

    # If low on proxies, start validation in background
    if len(result) < count / 2:
        asyncio.create_task(validate_proxies(type))

    # Convert to dict for serialization
    return [proxy.as_dict() for proxy in result]


@app.post("/refresh")
async def refresh_proxy_list(background_tasks: BackgroundTasks):
    """
    Refresh the proxy list from all sources
    """
    background_tasks.add_task(refresh_proxies)
    return {"status": "Refreshing proxies in background"}


@app.post("/validate")
async def validate_proxy_list(
        background_tasks: BackgroundTasks,
        type: Optional[int] = Query(None, description="Proxy type (1=HTTP, 4=SOCKS4, 5=SOCKS5)"),
        count: Optional[int] = Query(100, description="Number of proxies to validate")
):
    """
    Validate a batch of proxies
    """
    if type is not None and type not in [1, 4, 5]:
        raise HTTPException(
            status_code=400,
            detail="Invalid proxy type. Must be 1 (HTTP), 4 (SOCKS4), or 5 (SOCKS5)"
        )

    proxy_type = ProxyType(type) if type else None
    background_tasks.add_task(validate_proxies, proxy_type, count)
    return {"status": "Validating proxies in background"}


@app.get("/stats")
async def get_stats():
    """
    Get service statistics
    """
    return {
        "proxies": {
            "http": len(proxies[ProxyType.HTTP]),
            "socks4": len(proxies[ProxyType.SOCKS4]),
            "socks5": len(proxies[ProxyType.SOCKS5])
        },
        "stats": {
            "proxies_fetched": stats["proxies_fetched"].value(),
            "proxies_validated": stats["proxies_validated"].value(),
            "valid_proxies": stats["valid_proxies"].value(),
            "invalid_proxies": stats["invalid_proxies"].value()
        },
        "last_refresh": datetime.fromtimestamp(last_proxy_refresh).isoformat() if last_proxy_refresh else None
    }


@app.get("/health")
async def health_check():
    """
    Health check endpoint
    """
    return {"status": "healthy"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=8010, reload=True)