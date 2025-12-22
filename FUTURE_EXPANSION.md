# Nebula: Future Expansion Roadmap

This document outlines planned features and enhancements for Nebula beyond the core functionality (health check, upload, download, stream).

---

## Phase 2: Core Enhancements

### 1. Authentication & User Management
**Priority:** High  
**Status:** Planned

- JWT-based authentication system
- User registration and login endpoints
- Refresh token rotation
- Multi-user support with permissions
- API key management for programmatic access
- Password hashing and security best practices

**Why:** Essential security feature, demonstrates authentication knowledge

---

### 2. File Organization & Metadata
**Priority:** High  
**Status:** Planned

- Folder/directory structure support
- Tags and categories for files
- File search (by name, type, date, tags)
- Metadata extraction (video duration, resolution, codec)
- Thumbnail generation for videos and images
- File preview capabilities

**Why:** Improves user experience, demonstrates data modeling and search implementation

---

### 3. Sharing & Access Control
**Priority:** Medium  
**Status:** Planned

- Share links with expiration dates
- Password-protected shares
- Public/private file visibility settings
- Download limits and bandwidth controls
- Access logs for shared files
- Revoke sharing capabilities

**Why:** Real-world use case, demonstrates security and access control implementation

---

### 4. Transcoding & Optimization
**Priority:** High  
**Status:** Partially Planned (Phase 4)

- Background video transcoding pipeline
- Multiple quality profiles (1080p, 720p, 480p)
- Automatic transcoding on upload
- Transcode queue management
- Progress tracking for transcoding jobs
- Hardware acceleration (Intel QuickSync) support

**Why:** Core feature, demonstrates async processing and media handling skills

---

### 5. Search & Discovery
**Priority:** Medium  
**Status:** Planned

- Full-text search (file names, metadata, tags)
- Advanced filters (date range, file type, size)
- Recent uploads view
- Most accessed/popular files
- Search history

**Why:** Improves usability, demonstrates search implementation skills

---

### 6. Playlists & Collections
**Priority:** Low  
**Status:** Planned

- Create and manage playlists
- Playlist sharing
- Auto-playlists (recent, favorites, by tag)
- Collections (group related files)
- Playlist export/import

**Why:** Media server feature, demonstrates data relationships and organization

---

### 7. Analytics & Monitoring
**Priority:** Medium  
**Status:** Planned

- Usage statistics (storage, bandwidth)
- Upload/download history
- System health dashboard
- Performance metrics
- Resource utilization tracking
- Activity logs

**Why:** Production monitoring, demonstrates data visualization and analytics skills

---

### 8. Backup & Sync
**Priority:** Medium  
**Status:** Planned

- Automatic backups to external storage
- Sync between devices
- Version history for files
- Restore deleted files
- Backup scheduling and management

**Why:** Data management, demonstrates reliability and backup strategies

---

### 9. Advanced Streaming Features
**Priority:** Low  
**Status:** Planned

- Adaptive bitrate streaming (HLS/DASH)
- Subtitle support (.srt, .vtt)
- Multiple audio tracks
- Playback speed control
- Resume watching functionality
- Playback position tracking

**Why:** Advanced media features, demonstrates streaming protocol knowledge

---

### 10. Batch Operations
**Priority:** Low  
**Status:** Planned

- Bulk upload
- Bulk delete
- Bulk download (ZIP archives)
- Batch tagging
- Batch sharing

**Why:** Practical feature, demonstrates file handling and batch processing

---

### 11. Notifications
**Priority:** Low  
**Status:** Planned

- Upload completion notifications
- Transcoding job completion
- System alerts
- Email/webhook notifications
- Notification preferences

**Why:** User experience improvement, demonstrates async messaging

---

## Phase 3: DevOps Platform (Later Version)

### Personal PaaS / EC2+S3+Drive Vision
**Priority:** Future  
**Status:** Conceptual

Transform Nebula into a complete personal cloud platform that provides total control of the old laptop from the new laptop, utilizing all resources.

#### Core Concept
- **Old laptop** = Permanent personal EC2 (always-on, in corner, on power)
- **Nebula** = Personal Heroku/GitHub Actions + ECS-lite
- **Command:** `nebula push deploy` → Full CI/CD pipeline

#### Features

**Compute (EC2-like)**
- `nebula ps` - List running apps/containers on old laptop
- `nebula deploy my-app` - Build & deploy new project
- `nebula logs my-app` - Stream logs from any app
- `nebula exec my-app -- bash` - Get shell inside running container
- `nebula jobs submit ...` - Run batch jobs (ML, FFmpeg) on old laptop's CPU/GPU
- `nebula restart my-app` - Restart a service
- `nebula update nebula` - Update Nebula platform itself

**Storage (S3/Drive-like)**
- `nebula upload file.mp4` - Upload files
- `nebula download file.mp4` - Download files
- `nebula ls /movies` - Browse files/folders
- Web UI for browsing, previewing, organizing files

**System Control**
- `nebula stats` - RAM/CPU/disk/battery/temperature of old laptop
- `nebula deploy` - Push code → build → run → accessible on public URL
- Multi-project support (each project gets its own subdomain)
- Git-based deployments (push to deploy)
- Docker image-based deployments
- Reverse proxy routing (nginx/Caddy/Traefik)

**Networking & Access**
- Tailscale VPN (private access)
- Public HTTPS via reverse proxy + domain
- Let's Encrypt TLS certificates (free)
- Dynamic DNS support

#### Technical Requirements
- **Nebula CLI** - Command-line tool on new laptop
- **Nebula Orchestrator** - Service on old laptop managing projects
- **Reverse Proxy** - Routes `app1.yourdomain.com`, `app2.yourdomain.com`, etc.
- **GitOps Pipeline** - Automated deployments via git hooks
- **Container Registry** - Store Docker images (optional)

#### Cost Analysis
- **Domain name:** ~₹700-₹1,000/year (only paid service needed)
- **DNS:** Free (DuckDNS, Cloudflare DDNS)
- **TLS/HTTPS:** Free (Let's Encrypt)
- **CI/CD:** Free (run locally or GitHub Actions free tier)
- **VPN:** Free (Tailscale free tier for personal use)

#### Use Case
```
Developer workflow:
1. Create new project on new laptop
2. Run: `nebula push deploy`
3. Code is pushed to old laptop
4. Automatically built and deployed
5. Accessible at: https://myapp.yourdomain.com
6. Never touch old laptop - it's fully automated
```

---

## Project Classification

### What Nebula Is
- **Self-hosted PaaS** (Platform as a Service)
- **Personal cloud platform** (EC2 + S3 + Drive equivalent)
- **Homelab "cloud"** / **developer platform**
- **Self-hosted Heroku/Render/Fly.io** on repurposed hardware

### Resume Description Options
- "A self-hosted PaaS and storage platform turning an old laptop into a personal EC2 + S3 equivalent"
- "A personal cloud platform providing push-to-deploy apps, object storage, and media streaming on repurposed hardware"
- "A developer-focused homelab platform offering Git-based deployments, container orchestration, and private S3-compatible storage"

---

## Implementation Priority

### Immediate (After Core Features)
1. Authentication & User Management
2. File Organization & Metadata
3. Sharing & Access Control
4. Transcoding Pipeline

### Medium Term
5. Search & Discovery
6. Analytics & Monitoring
7. Backup & Sync

### Long Term
8. Advanced Streaming Features
9. Playlists & Collections
10. Batch Operations
11. Notifications

### Future Vision
12. DevOps Platform / Personal PaaS (Phase 3)

---

## Notes

- **No UI features or mobile app** for now - focus on backend/API
- **DevOps platform** is the big vision but comes later
- All features should maintain the core philosophy: **self-hosted, private, resource-efficient**

