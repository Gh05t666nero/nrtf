# Network Resilience Testing Framework (NRTF)

![Version](https://img.shields.io/badge/version-1.0.0-blue.svg)
![License](https://img.shields.io/badge/license-MIT-green.svg)
![Python](https://img.shields.io/badge/python-3.9+-yellow.svg)
![Docker](https://img.shields.io/badge/docker-required-blue.svg)
![Tests](https://img.shields.io/badge/tests-passing-green.svg)

A professional-grade microservices architecture for authorized network resilience testing with comprehensive testing capabilities across HTTP, TCP/UDP, and DNS protocols.

## ⚠️ IMPORTANT DISCLAIMER ⚠️

**This software is designed EXCLUSIVELY for:**
- Authorized security testing of your own systems
- Performance evaluation with explicit permission
- Educational purposes in controlled environments

**UNAUTHORIZED USAGE IS ILLEGAL**: 
Using this software against systems without explicit written permission is illegal in most jurisdictions and may result in severe civil and criminal penalties. The developers of this software accept NO LIABILITY for misuse of this software.

**YOU ARE RESPONSIBLE for ensuring all necessary permissions are obtained BEFORE conducting any tests.**

## Key Features

- **Modern Microservices Architecture**: Independently scalable and maintainable services
- **Comprehensive Test Methods**: Multiple testing methodologies across different protocols
  - HTTP-based: HTTP flood, Slow Loris, SSL flood, WAF bypass techniques
  - TCP/UDP-based: TCP/UDP flood, connection pool exhaustion, SYN flood
  - DNS-based: DNS query flood testing
- **API-First Design**: RESTful API for seamless integration with existing tooling
- **Advanced Security**: JWT-based authentication with role-based permissions
- **Detailed Metrics**: Comprehensive performance metrics with real-time reporting
- **Proxy Management**: Automatic proxy acquisition, validation, and rotation
- **Container-Ready**: Optimized for Docker deployment with compose support

## Architecture Overview

NRTF uses a modern microservices architecture designed for scalability and modularity:

```
┌─────────────────┐      ┌─────────────────┐      ┌─────────────────┐
│                 │      │                 │      │                 │
│   API Gateway   │─────▶│  Orchestrator   │─────▶│  Test Modules   │
│                 │      │                 │      │                 │
└─────────────────┘      └─────────────────┘      └─────────────────┘
        │                        │                        │
        ▼                        ▼                        ▼
┌─────────────────┐      ┌─────────────────┐      ┌─────────────────┐
│                 │      │                 │      │                 │
│  Authentication │      │  Test Manager   │      │  Result Store   │
│                 │      │                 │      │                 │
└─────────────────┘      └─────────────────┘      └─────────────────┘
```

### Components

- **API Gateway**: Central entry point handling authentication, request routing, and rate limiting
  - User authentication and authorization
  - Request validation and sanitization
  - Service discovery and request forwarding
  
- **Orchestrator**: Coordinates test execution across services
  - Test scheduling and resource allocation
  - Service health monitoring
  - Result aggregation and reporting
  
- **Test Modules**: Specialized services for different protocols and test methodologies
  - **HTTP Module**: Web service testing capabilities
    - HTTP flood, Slow Loris, SSL flood, and WAF bypass testing
  - **TCP Module**: Network protocol testing
    - TCP/UDP flood, SYN flood, and connection pool exhaustion
  - **DNS Module**: DNS service testing
    - DNS query flood with customizable parameters
    
- **Proxy Service**: Manages proxy acquisition and validation
  - Automatic proxy sourcing and validation
  - Proxy rotation and health checking
  - Support for HTTP, SOCKS4, and SOCKS5 proxies

- **Common Libraries**: Shared functionality for logging, validation, and utilities

## Comprehensive Test Methods

### HTTP Layer Tests

| Method | Description | Use Case |
|--------|-------------|----------|
| **HTTP_FLOOD** | High-volume HTTP request flood | Tests web server capacity and CDN resilience |
| **SLOW_LORIS** | Connection exhaustion through slow requests | Tests connection timeout handling |
| **SSL_FLOOD** | TLS/SSL handshake and renegotiation stress testing | Tests SSL termination efficiency |
| **HTTP_BYPASS** | WAF and protection bypass techniques | Tests defense evasion detection |

### TCP/UDP Layer Tests

| Method | Description | Use Case |
|--------|-------------|----------|
| **TCP_FLOOD** | Standard TCP connection flood | Tests TCP stack and connection handling |
| **UDP_FLOOD** | UDP packet flood | Tests UDP service capacity and filtering |
| **TCP_CONNECTION** | Connection pool exhaustion | Tests connection table capacity |
| **SYN_FLOOD** | TCP SYN packet flood | Tests SYN cookie implementation and backlog queues |

### DNS Tests

| Method | Description | Use Case |
|--------|-------------|----------|
| **DNS_FLOOD** | DNS query flood testing | Tests DNS server capacity and caching |

## Getting Started

### Prerequisites
- Docker Engine 20.10+
- Docker Compose 2.0+
- Python 3.9+
- Access to target systems with proper authorization

### Quick Start

1. Clone the repository:
```bash
git clone https://github.com/Gh05t666nero/nrtf.git
cd nrtf
```

2. Run the installation script:
```bash
chmod +x install.sh
./install.sh
```

3. Start the services:
```bash
docker-compose up -d
```

4. Access the API at:
```
http://localhost:8080/api/docs
```

### Authentication

Default credentials (change these in production):
- Username: `testuser`
- Password: `testpassword`

Get your authentication token:
```bash
curl -X POST "http://localhost:8080/token" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=testuser&password=testpassword"
```

### Running Tests

Create a new test:
```bash
curl -X POST "http://localhost:8080/api/test" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "target": "example.com",
    "method": "HTTP_FLOOD",
    "duration": 30,
    "threads": 5,
    "parameters": {
      "rpc": 5
    }
  }'
```

## Configuration

Configuration is managed through environment variables defined in the `.env` file:

| Variable | Description | Default |
|----------|-------------|---------|
| `SECRET_KEY` | Authentication secret key | Generated during install |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | Token expiration time | 30 |
| `MAX_TEST_DURATION` | Maximum allowed test duration (seconds) | 300 |
| `MAX_THREADS` | Maximum allowed threads per test | 1000 |
| `MAX_REQUESTS_PER_MINUTE` | API rate limiting | 60 |
| `MAX_CONCURRENT_TESTS` | Maximum tests running simultaneously | 5 |

See `.env.example` for all available options.

## Development

### Local Development

For local development without Docker:

1. Set up virtual environments in each service directory
```bash
# Example for gateway service
cd gateway-service
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

2. Run services individually:
```bash
uvicorn src.main:app --reload --port 8000
```

### Running Tests

Run tests for individual services:
```bash
cd gateway-service
pytest
```

### Adding New Test Methods

See [CONTRIBUTING.md](CONTRIBUTING.md) for details on adding new test methods.

## Production Deployment Considerations

For production deployments, consider the following:

1. **Security Hardening**:
   - Change all default credentials
   - Use a proper secrets management solution
   - Enable TLS for all service communication
   - Implement IP-based access controls

2. **Scaling**:
   - Deploy behind a load balancer
   - Use Kubernetes for orchestration
   - Implement horizontal scaling for test modules

3. **Monitoring**:
   - Add Prometheus metrics collection
   - Set up Grafana dashboards
   - Implement alerting for system issues

4. **Backup and Disaster Recovery**:
   - Implement proper database backups
   - Create restore procedures
   - Document disaster recovery steps

## Detailed Documentation

- [Usage Guide](USAGE_GUIDE.md): Detailed usage instructions
- [Contributing](CONTRIBUTING.md): Guidelines for contributing to the project
- [API Documentation](http://localhost:8080/docs): Available after starting the services

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Acknowledgments

- Inspired by modern security testing methodologies
- Built with best practices in microservices architecture
- Designed for professional network resilience testing

## Support & Contact

Please open an issue on the GitHub repository for bugs, feature requests, or questions.

For security-related issues, please contact us directly at `hubungi@fauzan.biz.id`.

## Roadmap

Future development plans include:

- Additional test methods for application layer testing
- Enhanced reporting with data visualization
- Integration with CI/CD pipelines
- Support for distributed testing across multiple agents

---

**Remember**: With great power comes great responsibility. Use this tool ethically and legally.