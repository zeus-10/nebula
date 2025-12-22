# Nebula: Distributed Private Cloud & Streaming Engine
**Status:** In Development | **Version:** 1.0.0-alpha

---

## 1. Executive Summary
Nebula is a self-hosted, distributed cloud platform engineered to run on bare-metal hardware. It decouples storage, compute, and state into isolated microservices, transforming a standard laptop into a high-performance private cloud.

**Core Value Proposition:**
* **Data Sovereignty:** A private S3-compatible object storage layer (MinIO).
* **Adaptive Streaming:** A Netflix-style media pipeline capable of 4K ingestion and byte-range streaming.
* **Zero-Trust Access:** A secure mesh network (Tailscale) eliminating public port exposure.
* **Infrastructure as Code:** Fully containerized deployment with a custom GitOps pipeline.

---

## 2. System Architecture

### A. High-Level Design (Microservices)
The system is composed of **5 Isolated Services** running within a Docker network.



| Service | Role | Tech Stack |
| :--- | :--- | :--- |
| **Gateway** | The "Receptionist" | **FastAPI (Python)** |
| **Storage** | The "Warehouse" | **MinIO (S3 Compatible)** |
| **State** | The "Memory" | **PostgreSQL** |
| **Queue** | The "Inbox" | **Redis** |
| **Worker** | The "Muscle" | **Celery + FFmpeg** |

### B. Network & Security
* **Tunneling:** Uses **Tailscale** (WireGuard) to expose the API to specific client devices without opening router ports.
* **Communication:**
    * **Internal:** Services talk via Docker DNS (e.g., `http://db:5432`).
    * **External:** Client talks via Tailscale IP (e.g., `http://100.x.y.z:8000`).

---

## 3. Detailed Technology Stack

**Backend (Server Node)**
* **OS:** Linux Mint (Headless configuration)
* **Runtime:** Docker Engine & Docker Compose
* **Language:** Python 3.10+ (Type-hinted)
* **Framework:** FastAPI (Selected for native Async I/O)
* **Database:** PostgreSQL 15 (Relational Integrity)
* **Object Store:** MinIO (AWS S3 API compatibility)
* **Task Queue:** Celery 5 + Redis 7
* **Media Processing:** FFmpeg (Hardware accelerated via Intel QuickSync)

**Frontend (Client Node)**
* **Language:** Python 3.10+
* **CLI Framework:** Typer (Command parsing)
* **UI Library:** Rich (Progress bars, tables, logs)
* **Network Lib:** Requests / Httpx

**DevOps (CI/CD)**
* **Strategy:** Push-to-Deploy
* **Mechanism:** Git Bare Repository + `post-receive` Hooks

---

## 4. Directory Structure

### A. Server Side (Old Laptop)
The server maintains two distinct directories: one for receiving code (Git) and one for running it (Live).

```text
/home/nebula_user/
├── nebula.git/                  # [Bare Repo] The Git Remote
│   └── hooks/
│       └── post-receive         # Script: Checkouts code -> Rebuilds Docker
│
├── nebula-live/                 # [Runtime] The Active Application
│   ├── docker-compose.yml       # Infrastructure Definition
│   ├── .env                     # Secrets (Not in Git)
│   ├── backend/                 # Source Code
│   │   ├── Dockerfile
│   │   ├── app/                 # Python Package
│   │   │   ├── main.py
│   │   │   ├── api/
│   │   │   ├── services/
│   │   │   └── worker.py
│   └── data/                    # [Persistence Layer]
│       ├── minio_storage/       # <--- Raw Files live here (SSD)
│       ├── postgres_data/       # <--- DB Tables live here
│       └── redis_data/          # <--- Queue persistence