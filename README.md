# Network Resilience Testing Framework (NRTF)

![Version](https://img.shields.io/badge/version-1.0.0-blue.svg)
![License](https://img.shields.io/badge/license-MIT-green.svg)

A professional-grade microservices architecture for authorized network resilience testing.

## ⚠️ IMPORTANT DISCLAIMER ⚠️

**This software is designed EXCLUSIVELY for:**
- Authorized security testing of your own systems
- Performance evaluation with explicit permission
- Educational purposes in controlled environments

**UNAUTHORIZED USAGE IS ILLEGAL**: 
Using this software against systems without explicit written permission is illegal in most jurisdictions and may result in severe civil and criminal penalties. The developers of this software accept NO LIABILITY for misuse of this software.

**YOU ARE RESPONSIBLE for ensuring all necessary permissions are obtained BEFORE conducting any tests.**

## Features

- **Modern Microservices Architecture**: Scalable and modular design
- **Comprehensive Test Methods**: HTTP, TCP/UDP, and DNS based testing capabilities
- **API-First Design**: Full REST API for integration with existing tools and automation
- **Advanced Security**: Token-based authentication with role-based permissions
- **Detailed Metrics**: Comprehensive performance metrics and reporting
- **Proxy Support**: Automatic proxy acquisition and validation
- **Container-Ready**: Designed for Docker deployment

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

- **API Gateway**: Central entry point handling authentication and request routing
- **Orchestrator**: Coordinates test execution across services
- **Test Modules**: Specialized services for different protocols and test methodologies
  - **HTTP Module**: Web service testing capabilities
  - **TCP Module**: Network protocol testing
  - **DNS Module**: DNS service testing
- **Proxy Service**: Manages proxy acquisition and validation
- **Common Libraries**: Shared functionality for logging, validation, and utilities

## Test Methods

### HTTP Layer Tests

- **HTTP_FLOOD**: High-volume HTTP request flood
- **SLOW_LORIS**: Connection exhaustion through slow requests
- **SSL_FLOOD**: TLS/SSL handshake and renegotiation stress testing
- **HTTP_BYPASS**: WAF and protection bypass techniques

### TCP/UDP Layer Tests

- **TCP_FLOOD**: Standard TCP connection flood
- **UDP_FLOOD**: UDP packet flood
- **TCP_CONNECTION**: Connection pool exhaustion
- **SYN_FLOOD**: TCP SYN packet flood

### DNS Tests

- **DNS_FLOOD**: DNS query flood testing

## Getting Started

### Prerequisites
- Docker and Docker Compose
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

- `SECRET_KEY`: Authentication secret key
- `ACCESS_TOKEN_EXPIRE_MINUTES`: Token expiration time
- `MAX_TEST_DURATION`: Maximum allowed test duration
- `MAX_THREADS`: Maximum allowed threads per test

See `.env.example` for all available options.

## Development

### Local Development

For local development without Docker:

1. Set up virtual environments in each service directory
2. Install requirements:
```bash
pip install -r requirements.txt
```
3. Run services individually:
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

## Contact & Support

Please open an issue on the GitHub repository for bugs, feature requests, or questions.

---

**Remember**: With great power comes great responsibility. Use this tool ethically and legally.