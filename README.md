# FastAPI Monitoring System

Simple monitoring system designed to track and monitor FastAPI applications deployed in Kubernetes.

## Features

- API endpoint availability monitoring
- Resource metrics collection
- Automated log collection when issues are detected
- Kubernetes pod status monitoring

## Prerequisites

- Python 3.9+
- Docker and Docker Compose
- Access to a Kubernetes cluster with the client's FastAPI application
- Metrics Server installed in the Kubernetes cluster

## Configuration

Edit the `config/config.yaml` file to configure:
- API endpoints to monitor
- Monitoring intervals
- Kubernetes namespace and label selectors

## Installation

### Using Docker

```bash
# Build and run with Docker Compose
docker-compose up -d
