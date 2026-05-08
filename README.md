# Birmingham Device Bank - Workbench System

Cloud-based workflow management system for device refurbishment.

## Overview
This system manages the complete lifecycle of device refurbishment from intake to dispatch.

## Architecture
- Django backend with REST API
- PostgreSQL database
- Redis for caching/queues
- Caddy reverse proxy
- n8n for integration orchestration

## Quick Start
1. Clone repository
2. Copy `.env.example` to `.env` and configure
3. Run `docker-compose up -d`
4. Access at https://your-domain.com

## Documentation
See `/docs` directory for detailed documentation.
