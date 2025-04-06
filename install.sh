#!/bin/bash

# Network Resilience Testing Framework Installation Script
# This script prepares the environment for NRTF

set -e

# Colors for terminal output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${GREEN}====================================${NC}"
echo -e "${GREEN}Network Resilience Testing Framework${NC}"
echo -e "${GREEN}Installation Script${NC}"
echo -e "${GREEN}====================================${NC}"
echo ""

# Check if Docker is installed
if ! command -v docker &> /dev/null; then
    echo -e "${RED}Error: Docker is not installed${NC}"
    echo "Please install Docker first: https://docs.docker.com/get-docker/"
    exit 1
fi

# Check if Docker Compose is installed
if ! command -v docker-compose &> /dev/null; then
    echo -e "${RED}Error: Docker Compose is not installed${NC}"
    echo "Please install Docker Compose first: https://docs.docker.com/compose/install/"
    exit 1
fi

# Check if running with sudo/root
if [ "$(id -u)" -eq 0 ]; then
    echo -e "${YELLOW}Warning: Running as root/sudo.${NC}"
    echo "This may cause permission issues with Docker volumes."
    echo "Consider running without sudo if you encounter issues."
    echo ""
    read -p "Continue? (y/n): " -n 1 -r
    echo ""
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

# Create directory structure
echo -e "${GREEN}Creating directory structure...${NC}"
mkdir -p gateway-service/src
mkdir -p orchestrator-service/src
mkdir -p test-modules/http-module/src
mkdir -p test-modules/tcp-module/src
mkdir -p test-modules/dns-module/src
mkdir -p proxy-service/src

# Copy .env.example to .env if it doesn't exist
if [ ! -f .env ]; then
    echo -e "${GREEN}Creating .env file from example...${NC}"
    cp .env.example .env

    # Generate a random secret key
    SECRET_KEY=$(openssl rand -hex 32)
    sed -i "s/supersecretkey_replace_in_production/$SECRET_KEY/g" .env

    echo -e "${YELLOW}Please review the .env file and adjust settings as needed${NC}"
fi

# Ensure the correct permissions
echo -e "${GREEN}Setting permissions...${NC}"
chmod +x install.sh

# Build Docker images
echo -e "${GREEN}Building Docker images...${NC}"
docker-compose build

echo ""
echo -e "${GREEN}Installation completed successfully!${NC}"
echo ""
echo -e "To start the system:"
echo -e "  ${YELLOW}docker-compose up -d${NC}"
echo ""
echo -e "To view logs:"
echo -e "  ${YELLOW}docker-compose logs -f${NC}"
echo ""
echo -e "The API will be available at:"
echo -e "  ${YELLOW}http://localhost:8080${NC}"
echo ""
echo -e "API Documentation will be available at:"
echo -e "  ${YELLOW}http://localhost:8080/docs${NC}"
echo ""
echo -e "${GREEN}====================================${NC}"
echo -e "${YELLOW}IMPORTANT: This tool is designed for authorized testing only.${NC}"
echo -e "${YELLOW}Always obtain explicit permission before testing any system.${NC}"
echo -e "${GREEN}====================================${NC}"