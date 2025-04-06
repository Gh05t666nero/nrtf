# Contributing to Network Resilience Testing Framework

Thank you for your interest in contributing to the Network Resilience Testing Framework! This document provides guidelines and instructions for contributing to this project.

## Code of Conduct

By participating in this project, you agree to maintain a respectful and inclusive environment. We expect all contributors to:

- Use welcoming and inclusive language
- Be respectful of differing viewpoints and experiences
- Gracefully accept constructive criticism
- Focus on what is best for the community
- Show empathy towards other community members

## How Can I Contribute?

### Reporting Bugs

If you find a bug, please create an issue on our GitHub repository with the following information:

1. **Title**: A clear, descriptive title
2. **Description**: What happened vs. what you expected to happen
3. **Steps to Reproduce**: Detailed steps to reproduce the issue
4. **Environment**: Docker version, OS, etc.
5. **Logs**: Relevant logs or error messages
6. **Possible Solution**: If you have suggestions for fixing the bug

### Suggesting Enhancements

We welcome suggestions for improving the framework. Please create an issue with:

1. **Title**: A clear, descriptive title
2. **Use Case**: How this enhancement would be used
3. **Current Limitations**: Why the current functionality is insufficient
4. **Proposed Solution**: Your ideas for implementing the enhancement
5. **Alternatives**: Any alternative solutions you've considered

### Pull Requests

We actively welcome pull requests:

1. Fork the repository
2. Create a new branch (`git checkout -b feature/amazing-feature`)
3. Make your changes
4. Run tests to ensure your changes don't break existing functionality
5. Commit your changes (`git commit -m 'Add some amazing feature'`)
6. Push to the branch (`git push origin feature/amazing-feature`)
7. Open a Pull Request

## Development Environment Setup

To set up your development environment:

1. Clone the repository
   ```bash
   git clone https://github.com/yourusername/nrtf.git
   cd nrtf
   ```

2. Create a virtual environment (optional but recommended)
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows, use: venv\Scripts\activate
   ```

3. Start the development environment with Docker
   ```bash
   docker-compose up -d
   ```

4. For local development without Docker, install dependencies in each service directory
   ```bash
   cd gateway-service
   pip install -r requirements.txt
   ```

## Project Structure

The project follows a microservice architecture:

- `gateway-service/`: API Gateway - entry point and authentication
- `orchestrator-service/`: Test orchestration and coordination
- `test-modules/`: Individual test implementations
  - `http-module/`: HTTP-based tests
  - `tcp-module/`: TCP/UDP-based tests
  - `dns-module/`: DNS-based tests
- `proxy-service/`: Proxy acquisition and management
- `common/`: Shared code and utilities

## Coding Guidelines

### Python Style Guide

- Follow [PEP 8](https://www.python.org/dev/peps/pep-0008/) guidelines
- Use 4 spaces for indentation (no tabs)
- Use docstrings for functions, classes, and modules
- Maximum line length of 100 characters
- Use type hints when possible

### Commit Messages

- Use clear, descriptive commit messages
- Start with a verb in the present tense (e.g., "Add", "Fix", "Update")
- Reference issue numbers when applicable

Example:
```
Add DNS amplification test method (#42)

- Implement DNS reflection test
- Add documentation for new method
- Add unit tests for DNS amplification
```

## Adding New Test Methods

When adding new test methods:

1. Choose the appropriate module (HTTP, TCP/UDP, DNS)
2. Implement the test method following the existing patterns
3. Add method to the `TEST_METHODS` dictionary
4. Update documentation in USAGE_GUIDE.md
5. Add appropriate validation
6. Include unit tests

## Testing

Before submitting a pull request, ensure:

1. All tests pass
2. New functionality includes tests
3. Documentation is updated
4. No new security vulnerabilities are introduced

## Documentation

When making changes, please update the relevant documentation:

- README.md for general information
- USAGE_GUIDE.md for user-facing functionality
- Code comments and docstrings for implementation details

## Ethical Guidelines

This framework is designed for authorized testing only. All contributions must:

1. Include appropriate safeguards against misuse
2. Not enable illegal activities
3. Maintain the ethical focus of the project
4. Include appropriate warnings and disclaimers

## Getting Help

If you need help or have questions:

1. Check existing documentation
2. Look through closed issues for similar questions
3. Open a new issue with your question

## License

By contributing, you agree that your contributions will be licensed under the project's MIT License.

Thank you for contributing to the Network Resilience Testing Framework!