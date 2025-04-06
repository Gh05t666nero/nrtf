# Network Resilience Testing Framework (NRTF) - Usage Guide

This comprehensive guide covers the usage of the NRTF API and its various testing capabilities, including detailed examples, best practices, and troubleshooting.

## ⚠️ IMPORTANT: AUTHORIZED TESTING ONLY ⚠️

The Network Resilience Testing Framework is designed **EXCLUSIVELY** for:
- Testing systems you own or have **explicit written permission** to test
- Educational use in controlled lab environments
- Internal network resilience assessments

Unauthorized testing may violate local, state, and federal laws including the Computer Fraud and Abuse Act in the US and similar legislation worldwide.

## Table of Contents

1. [Authentication](#authentication)
2. [Available Test Methods](#available-test-methods)
3. [Starting a Test](#starting-a-test)
4. [Monitoring Tests](#monitoring-tests)
5. [Stopping a Test](#stopping-a-test)
6. [Getting Test Results](#getting-test-results)
7. [Getting All Tests](#getting-all-tests)
8. [Method-Specific Parameters](#method-specific-parameters)
9. [Using Proxies](#using-proxies)
10. [Best Practices](#best-practices)
11. [Advanced Scenarios](#advanced-scenarios)
12. [Troubleshooting](#troubleshooting)
13. [API Reference](#api-reference)

## Authentication

All API requests must be authenticated using JWT token-based authentication. The framework implements a secure authentication flow.

### Obtaining a Token

```http
POST /token
Content-Type: application/x-www-form-urlencoded

username=your_username&password=your_password
```

The response will include an access token:

```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer"
}
```

### Using the Token

Use this token in all subsequent requests by adding the Authorization header:

```
Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
```

### Token Expiration

Tokens are valid for 30 minutes by default. When a token expires, you'll need to request a new one.

## Available Test Methods

The framework provides various test methods for different protocols, each designed to test specific aspects of network resilience.

### HTTP Layer Tests

| Method | Description | Parameters | Notes |
|--------|-------------|------------|-------|
| **HTTP_FLOOD** | Standard HTTP request flood | `rpc`: Requests per connection | General web service capacity testing |
| **SLOW_LORIS** | Slow-rate HTTP connection exhauster | `delay`: Delay between headers (seconds) | Tests connection handling and timeouts |
| **SSL_FLOOD** | TLS/SSL renegotiation & handshake flood | None | Tests SSL termination efficiency |
| **HTTP_BYPASS** | WAF & protection bypass techniques | None | Tests defense evasion capabilities |

### TCP/UDP Layer Tests

| Method | Description | Parameters | Notes |
|--------|-------------|------------|-------|
| **TCP_FLOOD** | Standard TCP connection flood | None | Tests TCP stack robustness |
| **UDP_FLOOD** | UDP packet flood | `packet_size`: Size in bytes | Tests UDP service handling |
| **TCP_CONNECTION** | Connection pool exhaustion | `max_connections`: Connections per thread | Tests connection table capacity |
| **SYN_FLOOD** | TCP SYN packet flood | None | Requires privileged mode |

### DNS Tests

| Method | Description | Parameters | Notes |
|--------|-------------|------------|-------|
| **DNS_FLOOD** | DNS query flood | `query_type`: Record type (A, AAAA, etc.) | Tests DNS server capacity |

## Starting a Test

To start a test, make a POST request to the `/api/test` endpoint with the required parameters.

### Basic Example

```http
POST /api/test
Authorization: Bearer YOUR_TOKEN
Content-Type: application/json

{
  "target": "example.com",
  "method": "HTTP_FLOOD",
  "duration": 60,
  "threads": 10,
  "parameters": {
    "rpc": 5
  }
}
```

### Complete Example

```http
POST /api/test
Authorization: Bearer YOUR_TOKEN
Content-Type: application/json

{
  "target": "example.com",
  "method": "HTTP_FLOOD",
  "duration": 60,
  "threads": 10,
  "proxy_type": 1,
  "parameters": {
    "rpc": 5
  }
}
```

### Request Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `target` | string | Yes | The target URL or host:port (format depends on method) |
| `method` | string | Yes | Test method from the available methods |
| `duration` | integer | Yes | Test duration in seconds (max 300 by default) |
| `threads` | integer | Yes | Number of concurrent workers (max 1000 by default) |
| `proxy_type` | integer | No | Type of proxy to use (1=HTTP, 4=SOCKS4, 5=SOCKS5) |
| `parameters` | object | No | Method-specific parameters |

### Response

```json
{
  "id": "f47ac10b-58cc-4372-a567-0e02b2c3d479",
  "target": "example.com",
  "method": "HTTP_FLOOD",
  "status": "queued",
  "user": "testuser"
}
```

## Monitoring Tests

To check the status of a test, use the GET endpoint with the test ID:

```http
GET /api/test/f47ac10b-58cc-4372-a567-0e02b2c3d479
Authorization: Bearer YOUR_TOKEN
```

### Response

```json
{
  "id": "f47ac10b-58cc-4372-a567-0e02b2c3d479",
  "target": "example.com",
  "method": "HTTP_FLOOD",
  "status": "running",
  "start_time": 1650123456.789,
  "user": "testuser"
}
```

### Test States

A test can be in one of the following states:

- `queued`: Test is waiting to start
- `running`: Test is currently running
- `completed`: Test finished successfully
- `failed`: Test encountered an error
- `stopped`: Test was manually stopped

## Stopping a Test

To stop a running test, use the DELETE endpoint:

```http
DELETE /api/test/f47ac10b-58cc-4372-a567-0e02b2c3d479
Authorization: Bearer YOUR_TOKEN
```

### Response

```json
{
  "id": "f47ac10b-58cc-4372-a567-0e02b2c3d479",
  "target": "example.com",
  "method": "HTTP_FLOOD",
  "status": "stopped",
  "start_time": 1650123456.789,
  "end_time": 1650123486.789,
  "user": "testuser"
}
```

## Getting Test Results

To retrieve detailed test results:

```http
GET /api/test/f47ac10b-58cc-4372-a567-0e02b2c3d479/results
Authorization: Bearer YOUR_TOKEN
```

### Response (HTTP Methods)

```json
{
  "test_id": "f47ac10b-58cc-4372-a567-0e02b2c3d479",
  "target": "example.com",
  "duration": 30.0,
  "metrics": {
    "requests_sent": 15000,
    "bytes_sent": 2500000,
    "successful_requests": 14500,
    "failed_requests": 500,
    "requests_per_second": 500.0,
    "success_rate": 96.67
  }
}
```

### Response (TCP/UDP Methods)

```json
{
  "test_id": "f47ac10b-58cc-4372-a567-0e02b2c3d479",
  "target": "example.com:80",
  "duration": 30.0,
  "metrics": {
    "packets_sent": 25000,
    "bytes_sent": 1500000,
    "successful_connects": 24000,
    "failed_connects": 1000,
    "packets_per_second": 833.33,
    "success_rate": 96.0
  }
}
```

### Response (DNS Methods)

```json
{
  "test_id": "f47ac10b-58cc-4372-a567-0e02b2c3d479",
  "target": "8.8.8.8:53",
  "duration": 30.0,
  "metrics": {
    "queries_sent": 30000,
    "bytes_sent": 3000000,
    "successful_queries": 29500,
    "failed_queries": 500,
    "queries_per_second": 1000.0,
    "success_rate": 98.33
  }
}
```

## Getting All Tests

To list all your tests:

```http
GET /api/tests
Authorization: Bearer YOUR_TOKEN
```

### Response

```json
[
  {
    "id": "f47ac10b-58cc-4372-a567-0e02b2c3d479",
    "target": "example.com",
    "method": "HTTP_FLOOD",
    "status": "completed",
    "start_time": 1650123456.789,
    "end_time": 1650123486.789,
    "user": "testuser"
  },
  {
    "id": "a47bc10b-58cc-4372-a567-0e02b2c3d480",
    "target": "example.org",
    "method": "TCP_FLOOD",
    "status": "running",
    "start_time": 1650123556.789,
    "user": "testuser"
  }
]
```

## Method-Specific Parameters

Different test methods accept specific parameters to customize behavior:

### HTTP_FLOOD

```json
{
  "parameters": {
    "rpc": 10  // Requests per connection
  }
}
```

### SLOW_LORIS

```json
{
  "parameters": {
    "delay": 10  // Delay between partial headers in seconds
  }
}
```

### TCP_CONNECTION

```json
{
  "parameters": {
    "max_connections": 100  // Maximum connections per thread
  }
}
```

### UDP_FLOOD

```json
{
  "parameters": {
    "packet_size": 512  // UDP packet size in bytes
  }
}
```

### DNS_FLOOD

```json
{
  "parameters": {
    "query_type": "A"  // DNS record type (A, AAAA, MX, etc.)
  }
}
```

## Using Proxies

The framework supports proxying tests through HTTP, SOCKS4, and SOCKS5 proxies to distribute the source of requests.

### Enabling Proxies

To use proxies, set the `proxy_type` parameter in your test request:

```json
{
  "target": "example.com",
  "method": "HTTP_FLOOD",
  "duration": 30,
  "threads": 10,
  "proxy_type": 5,  // 1=HTTP, 4=SOCKS4, 5=SOCKS5
  "parameters": {
    "rpc": 5
  }
}
```

### Proxy Selection

When proxies are enabled, the framework will:

1. Automatically fetch appropriate proxies from the proxy service
2. Validate proxy connectivity and performance
3. Distribute test traffic across available proxies
4. Replace failed proxies during the test

## Best Practices

Follow these best practices to perform effective and safe testing:

### 1. Start with Low Intensity

Always begin with fewer threads and shorter durations to assess impact:

```json
{
  "target": "example.com",
  "method": "HTTP_FLOOD",
  "duration": 10,
  "threads": 2,
  "parameters": {
    "rpc": 1
  }
}
```

### 2. Gradually Increase

Incrementally increase test intensity to find system limits safely:

```json
{
  "target": "example.com",
  "method": "HTTP_FLOOD",
  "duration": 30,
  "threads": 5,
  "parameters": {
    "rpc": 3
  }
}
```

### 3. Monitor Target Systems

Always actively monitor the target system during testing:
- Resource utilization (CPU, memory, network)
- Error rates and response times
- Service availability

### 4. Use Method-Appropriate Parameters

Different methods may require specific parameters:
- For HTTP tests, use appropriate `rpc` values based on connection capacity
- For TCP tests, adjust `max_connections` based on service limits
- For DNS tests, use relevant `query_type` values

### 5. Document Everything

Maintain comprehensive records:
- Test authorizations
- Test parameters
- Test results
- System observations

## Advanced Scenarios

### Concurrent Tests

Run multiple tests simultaneously to simulate diverse attack vectors:

```bash
# First test - HTTP flood
curl -X POST "http://localhost:8080/api/test" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "target": "example.com",
    "method": "HTTP_FLOOD",
    "duration": 300,
    "threads": 10,
    "parameters": {
      "rpc": 5
    }
  }'

# Second test - TCP flood
curl -X POST "http://localhost:8080/api/test" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "target": "example.com:80",
    "method": "TCP_FLOOD",
    "duration": 300,
    "threads": 10
  }'
```

### Extended Duration Tests

For long-running resilience assessment:

```json
{
  "target": "example.com",
  "method": "HTTP_FLOOD",
  "duration": 300,  // Maximum duration
  "threads": 50,
  "parameters": {
    "rpc": 2
  }
}
```

### WAF Testing Pattern

For testing Web Application Firewall effectiveness:

```bash
# Step 1: Baseline HTTP flood
curl -X POST "http://localhost:8080/api/test" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "target": "example.com",
    "method": "HTTP_FLOOD",
    "duration": 60,
    "threads": 5
  }'

# Step 2: HTTP bypass techniques
curl -X POST "http://localhost:8080/api/test" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "target": "example.com",
    "method": "HTTP_BYPASS",
    "duration": 60,
    "threads": 5
  }'

# Step 3: Compare results
curl -X GET "http://localhost:8080/api/test/{test_id1}/results" -H "Authorization: Bearer YOUR_TOKEN"
curl -X GET "http://localhost:8080/api/test/{test_id2}/results" -H "Authorization: Bearer YOUR_TOKEN"
```

## Troubleshooting

| Issue | Possible Cause | Solution |
|-------|----------------|----------|
| Authentication errors | Expired or invalid token | Request a new token |
| Method not found | Invalid method name | Check available methods with GET /api/methods |
| Service unavailable | Module overload or crash | Check service logs and restart if necessary |
| Test fails immediately | Parameter validation failure | Check parameters against method requirements |
| Low success rate | Network issues or target filtering | Use proxies or adjust test parameters |
| "Forbidden" response | Unauthorized access attempt | Ensure you have permission for the target |
| Connection errors to service | Network configuration issue | Check Docker network and port mappings |

### Common Error Messages

**401 Unauthorized**
```json
{
  "detail": "Could not validate credentials"
}
```
Solution: Refresh your authentication token.

**400 Bad Request**
```json
{
  "detail": "Test duration exceeds maximum allowed (300 seconds)"
}
```
Solution: Reduce the requested test duration.

**404 Not Found**
```json
{
  "detail": "Test not found"
}
```
Solution: Verify the test ID is correct.

## API Reference

### Authentication

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/token` | POST | Obtain authentication token |
| `/users/me/` | GET | Get current user information |

### Test Management

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/test` | POST | Create a new test |
| `/api/tests` | GET | List all tests |
| `/api/test/{test_id}` | GET | Get test details |
| `/api/test/{test_id}` | DELETE | Stop a running test |
| `/api/test/{test_id}/results` | GET | Get test results |

### Service Information

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/methods` | GET | List available test methods |
| `/health` | GET | Check service health |

## Need Help?

For additional assistance, consult the source code documentation or post an issue on the GitHub repository.