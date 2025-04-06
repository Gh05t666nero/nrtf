# Network Resilience Testing Framework (NRTF) - Usage Guide

This guide covers the usage of the NRTF API and its various testing capabilities.

## ⚠️ IMPORTANT: AUTHORIZED TESTING ONLY ⚠️

The Network Resilience Testing Framework is designed **EXCLUSIVELY** for:
- Testing systems you own or have **explicit written permission** to test
- Educational use in controlled lab environments
- Internal network resilience assessments

Unauthorized testing may violate local, state, and federal laws including the Computer Fraud and Abuse Act.

## Authentication

All API requests must be authenticated. The framework uses JWT token-based authentication.

```
POST /token

{
  "username": "your_username",
  "password": "your_password"
}
```

The response will include an access token:

```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer"
}
```

Use this token in all subsequent requests:

```
Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
```

## Available Test Methods

The framework provides various test methods for different protocols:

### HTTP Layer Tests

| Method | Description | Notes |
|--------|-------------|-------|
| HTTP_FLOOD | Standard HTTP request flood | General web service testing |
| SLOW_LORIS | Slow-rate HTTP connection exhauster | Tests connection handling |
| SSL_FLOOD | TLS/SSL renegotiation & handshake flood | Tests SSL termination efficiency |
| HTTP_BYPASS | WAF & protection bypass techniques | Tests defense evasion capabilities |

### TCP/UDP Layer Tests

| Method | Description | Notes |
|--------|-------------|-------|
| TCP_FLOOD | Standard TCP connection flood | Tests TCP stack robustness |
| UDP_FLOOD | UDP packet flood | Tests UDP service handling |
| TCP_CONNECTION | Connection pool exhaustion | Tests connection table capacity |
| SYN_FLOOD | TCP SYN packet flood | Requires privileged mode |

### DNS Tests (Coming Soon)

| Method | Description | Notes |
|--------|-------------|-------|
| DNS_FLOOD | DNS query flood | Tests DNS server capacity |

## Starting a Test

To start a test, make a POST request to the `/api/test` endpoint:

```
POST /api/test

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

- `target`: The target URL or host:port (depending on method)
- `method`: Test method from the available methods
- `duration`: Test duration in seconds (max 300 by default)
- `threads`: Number of concurrent workers (max 1000 by default)
- `proxy_type`: (Optional) Type of proxy to use (1=HTTP, 4=SOCKS4, 5=SOCKS5)
- `parameters`: (Optional) Method-specific parameters

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

To check the status of a test:

```
GET /api/test/{test_id}
```

Response:

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

## Stopping a Test

To stop a running test:

```
DELETE /api/test/{test_id}
```

Response:

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

To retrieve test results:

```
GET /api/test/{test_id}/results
```

Response (varies by method):

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

## Getting All Tests

To list all your tests:

```
GET /api/tests
```

Response:

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
  ...
]
```

## Method-Specific Parameters

Different test methods accept specific parameters:

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

## Best Practices

1. **Start with low intensity**: Begin with fewer threads and shorter durations to assess impact.
2. **Gradually increase**: Slowly increase test intensity to find system limits safely.
3. **Monitor target systems**: Always monitor the target system during testing.
4. **Set reasonable limits**: Use the lowest settings necessary to validate resilience.
5. **Maintain documentation**: Keep records of test authorizations and results.

## Troubleshooting

| Issue | Solution |
|-------|----------|
| Authentication errors | Check your token is valid and not expired |
| Method not found | Verify the method name matches available methods |
| Service unavailable | The test module might be overloaded or down |
| Test fails immediately | Check parameters and target accessibility |

## Need Help?

For additional assistance, consult the source code documentation or post an issue on the GitHub repository.