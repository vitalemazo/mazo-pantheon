# Deployment Guide

Complete deployment instructions for Mazo Pantheon across different platforms.

---

## Table of Contents

1. [Docker Compose (Recommended)](#docker-compose)
2. [Unraid](#unraid)
3. [Kubernetes (EKS/AKS/GKE)](#kubernetes)
4. [Local Development](#local-development)
5. [Environment Variables](#environment-variables)
6. [Post-Deployment](#post-deployment)

---

## Docker Compose

The simplest deployment method for any server with Docker installed.

### Prerequisites

- Docker 20.10+
- Docker Compose 2.0+
- 2GB RAM minimum
- API keys (see [Environment Variables](#environment-variables))

### Steps

```bash
# 1. Clone repository
git clone https://github.com/yourusername/mazo-pantheon.git
cd mazo-pantheon

# 2. Create environment file
cp .env.example .env

# 3. Edit .env with your API keys
nano .env

# 4. Start all services
cd docker
docker-compose -f docker-compose.unraid.yml up -d

# 5. Check status
docker-compose -f docker-compose.unraid.yml ps
```

### Services Started

| Container | Port | Purpose |
|-----------|------|---------|
| mazo-frontend | 5173 | React Web UI |
| mazo-backend | 8000 | FastAPI + Trading Engine |
| mazo-postgres | 5432 | Trade History Database |
| mazo-redis | 6379 | Caching Layer |

### Management Commands

```bash
# View logs
docker-compose -f docker-compose.unraid.yml logs -f

# Stop all
docker-compose -f docker-compose.unraid.yml down

# Restart backend only
docker-compose -f docker-compose.unraid.yml restart backend

# Rebuild after code changes
docker-compose -f docker-compose.unraid.yml build --no-cache
docker-compose -f docker-compose.unraid.yml up -d
```

---

## Unraid

Perfect for home labs with Unraid NAS/Server.

### Prerequisites

- Unraid 6.10+
- Docker enabled in Unraid
- SSH access to server

### Installation

```bash
# SSH to Unraid
ssh root@tower.local.lan

# Install docker-compose (if not installed)
curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-linux-x86_64" \
  -o /usr/local/bin/docker-compose
chmod +x /usr/local/bin/docker-compose

# Clone to appdata
cd /mnt/user/appdata
git clone https://github.com/yourusername/mazo-pantheon.git
cd mazo-pantheon

# Configure
cp .env.example .env
nano .env
```

### Important .env Settings for Unraid

```bash
# CRITICAL: Use container path, not host path
MAZO_PATH=/app/mazo

# Database password
POSTGRES_PASSWORD=your-secure-password

# Your API keys
FINANCIAL_DATASETS_API_KEY=xxx
OPENAI_API_KEY=xxx
ALPACA_API_KEY=xxx
ALPACA_SECRET_KEY=xxx
```

### Deploy

```bash
cd docker
docker-compose -f docker-compose.unraid.yml --env-file ../.env up -d
```

### Access

- **Web UI**: http://tower.local.lan:5173
- **API**: http://tower.local.lan:8000
- **API Docs**: http://tower.local.lan:8000/docs

### Persist Through Reboots

Add to Unraid's "User Scripts" plugin to start on boot:

```bash
#!/bin/bash
cd /mnt/user/appdata/mazo-pantheon/docker
docker-compose -f docker-compose.unraid.yml --env-file ../.env up -d
```

---

## Kubernetes

Deploy to AWS EKS, Azure AKS, or Google GKE.

### Prerequisites

- `kubectl` configured for your cluster
- Container registry access (ECR, ACR, GCR)
- Ingress controller (nginx-ingress recommended)

### 1. Build and Push Images

```bash
# Build images
docker build -t mazo-pantheon-backend:latest -f docker/Dockerfile.backend .
docker build -t mazo-pantheon-frontend:latest -f docker/Dockerfile.frontend .

# Tag for your registry (example: ECR)
docker tag mazo-pantheon-backend:latest 123456789.dkr.ecr.us-east-1.amazonaws.com/mazo-backend:latest
docker tag mazo-pantheon-frontend:latest 123456789.dkr.ecr.us-east-1.amazonaws.com/mazo-frontend:latest

# Push
docker push 123456789.dkr.ecr.us-east-1.amazonaws.com/mazo-backend:latest
docker push 123456789.dkr.ecr.us-east-1.amazonaws.com/mazo-frontend:latest
```

### 2. Create Kubernetes Manifests

#### namespace.yaml
```yaml
apiVersion: v1
kind: Namespace
metadata:
  name: mazo-pantheon
```

#### secrets.yaml
```yaml
apiVersion: v1
kind: Secret
metadata:
  name: mazo-secrets
  namespace: mazo-pantheon
type: Opaque
stringData:
  FINANCIAL_DATASETS_API_KEY: "your-key"
  OPENAI_API_KEY: "your-key"
  ALPACA_API_KEY: "your-key"
  ALPACA_SECRET_KEY: "your-secret"
  POSTGRES_PASSWORD: "your-db-password"
```

#### postgres.yaml
```yaml
apiVersion: apps/v1
kind: StatefulSet
metadata:
  name: postgres
  namespace: mazo-pantheon
spec:
  serviceName: postgres
  replicas: 1
  selector:
    matchLabels:
      app: postgres
  template:
    metadata:
      labels:
        app: postgres
    spec:
      containers:
      - name: postgres
        image: postgres:16-alpine
        ports:
        - containerPort: 5432
        env:
        - name: POSTGRES_USER
          value: "mazo"
        - name: POSTGRES_PASSWORD
          valueFrom:
            secretKeyRef:
              name: mazo-secrets
              key: POSTGRES_PASSWORD
        - name: POSTGRES_DB
          value: "mazo_pantheon"
        volumeMounts:
        - name: postgres-data
          mountPath: /var/lib/postgresql/data
  volumeClaimTemplates:
  - metadata:
      name: postgres-data
    spec:
      accessModes: ["ReadWriteOnce"]
      resources:
        requests:
          storage: 10Gi
---
apiVersion: v1
kind: Service
metadata:
  name: postgres
  namespace: mazo-pantheon
spec:
  ports:
  - port: 5432
  selector:
    app: postgres
```

#### backend.yaml
```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: backend
  namespace: mazo-pantheon
spec:
  replicas: 1
  selector:
    matchLabels:
      app: backend
  template:
    metadata:
      labels:
        app: backend
    spec:
      containers:
      - name: backend
        image: YOUR_REGISTRY/mazo-backend:latest
        ports:
        - containerPort: 8000
        env:
        - name: MAZO_PATH
          value: "/app/mazo"
        - name: DATABASE_URL
          value: "postgresql://mazo:$(POSTGRES_PASSWORD)@postgres:5432/mazo_pantheon"
        envFrom:
        - secretRef:
            name: mazo-secrets
        resources:
          requests:
            memory: "512Mi"
            cpu: "250m"
          limits:
            memory: "2Gi"
            cpu: "1000m"
---
apiVersion: v1
kind: Service
metadata:
  name: backend
  namespace: mazo-pantheon
spec:
  ports:
  - port: 8000
  selector:
    app: backend
```

#### frontend.yaml
```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: frontend
  namespace: mazo-pantheon
spec:
  replicas: 1
  selector:
    matchLabels:
      app: frontend
  template:
    metadata:
      labels:
        app: frontend
    spec:
      containers:
      - name: frontend
        image: YOUR_REGISTRY/mazo-frontend:latest
        ports:
        - containerPort: 5173
---
apiVersion: v1
kind: Service
metadata:
  name: frontend
  namespace: mazo-pantheon
spec:
  type: LoadBalancer
  ports:
  - port: 80
    targetPort: 5173
  selector:
    app: frontend
```

### 3. Deploy

```bash
kubectl apply -f namespace.yaml
kubectl apply -f secrets.yaml
kubectl apply -f postgres.yaml
kubectl apply -f backend.yaml
kubectl apply -f frontend.yaml

# Check status
kubectl get pods -n mazo-pantheon
```

---

## Local Development

For developing and testing changes.

### Prerequisites

- Python 3.11+
- Node.js 18+
- Bun (for Mazo)

### Setup

```bash
# Clone
git clone https://github.com/yourusername/mazo-pantheon.git
cd mazo-pantheon

# Python environment
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Install Mazo dependencies
cd mazo && bun install && cd ..

# Frontend dependencies
cd app/frontend && npm install && cd ../..

# Configure
cp .env.example .env
nano .env  # Set MAZO_PATH to your local path
```

### Run

```bash
# Terminal 1 - Backend
source venv/bin/activate
uvicorn app.backend.main:app --reload --port 8000

# Terminal 2 - Frontend
cd app/frontend
npm run dev
```

### Access

- Frontend: http://localhost:5173
- Backend: http://localhost:8000
- API Docs: http://localhost:8000/docs

---

## Environment Variables

### Required

| Variable | Description | Example |
|----------|-------------|---------|
| `FINANCIAL_DATASETS_API_KEY` | Stock data API | `abc123...` |
| `OPENAI_API_KEY` | LLM provider | `sk-...` |
| `ALPACA_API_KEY` | Trading API key | `PK...` |
| `ALPACA_SECRET_KEY` | Trading API secret | `abc...` |
| `ALPACA_BASE_URL` | API endpoint | `https://paper-api.alpaca.markets/v2` |
| `MAZO_PATH` | Path to Mazo | `/app/mazo` (Docker) |
| `POSTGRES_PASSWORD` | Database password | `secure-password` |

### Optional

| Variable | Description | Default |
|----------|-------------|---------|
| `ANTHROPIC_API_KEY` | Claude models | - |
| `GROQ_API_KEY` | Fast inference | - |
| `GOOGLE_API_KEY` | Gemini models | - |
| `TAVILY_API_KEY` | Web search | - |
| `MAZO_TIMEOUT` | Research timeout (sec) | `300` |
| `AUTO_TRADING_ENABLED` | Enable autonomous mode | `false` |
| `TRADING_INTERVAL_MINUTES` | Scan frequency | `30` |

---

## Post-Deployment

### 1. Verify Services

```bash
# Check all containers running
docker ps | grep mazo

# Test API
curl http://localhost:8000/

# Test Alpaca connection
curl http://localhost:8000/alpaca/status
```

### 2. Configure via Web UI

1. Open http://localhost:5173
2. Click ⚙️ Settings
3. Go to **API Keys** tab
4. Enter/verify all keys
5. Click **Sync to .env** to persist

### 3. Enable Autonomous Trading

1. Go to **AI Hedge Fund** tab
2. Set your **Budget Allocation**
3. Choose **Risk Level**
4. Toggle **Autonomous Mode** ON

### 4. Monitor

- Check **Trading Dashboard** for positions
- View **Command Center** for trade history
- Watch logs: `docker logs -f mazo-backend`

---

## Updating

```bash
cd /path/to/mazo-pantheon

# Pull latest code
git pull

# Rebuild images
cd docker
docker-compose -f docker-compose.unraid.yml build --no-cache

# Restart
docker-compose -f docker-compose.unraid.yml up -d
```

---

## Security Considerations

1. **Never commit .env files** - Use `.env.example` as template
2. **Use strong passwords** - Especially `POSTGRES_PASSWORD`
3. **Paper trading first** - Test with `ALPACA_TRADING_MODE=paper`
4. **Firewall rules** - Restrict port access in production
5. **HTTPS** - Use reverse proxy (nginx/traefik) with SSL for internet access

---

## Troubleshooting

### Container won't start
```bash
docker logs mazo-backend
# Check for missing env vars or path issues
```

### Database connection failed
```bash
# Ensure postgres is healthy
docker ps | grep postgres
docker logs mazo-postgres
```

### Frontend shows blank page
```bash
# Check browser console for errors
# Verify backend is accessible
curl http://localhost:8000/
```

### Trade execution fails
```bash
# Verify Alpaca credentials
curl http://localhost:8000/alpaca/status
```
