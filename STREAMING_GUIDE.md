# 🎬 Nebula Streaming Guide

## Quick Start: Streaming Videos

### Method 1: Using `nebula play` Command (Recommended)

```bash
# List your uploaded videos
nebula list

# Play a video by ID (auto-detects VLC/mpv)
nebula play 67

# Specify a player
nebula play 67 --player vlc
nebula play 67 --player mpv
```

**What happens:**
1. CLI finds your video file ID
2. Constructs stream URL: `http://YOUR_SERVER:8000/api/files/67/stream`
3. Launches VLC/mpv with that URL
4. Video streams directly - no download needed!

### Method 2: Direct URL (Browser/Any Player)

```bash
# Get the stream URL
echo "http://YOUR_SERVER_IP:8000/api/files/67/stream"

# Open in browser or paste into VLC:
# VLC → Media → Open Network Stream → Paste URL
```

### Method 3: Test with curl

```bash
# Test byte-range support (seeking)
curl -I -H "Range: bytes=0-1000" http://YOUR_SERVER:8000/api/files/67/stream

# Should return: HTTP/1.1 206 Partial Content
```

---

## How Streaming Works

### Byte-Range Streaming (HTTP 206)

```
┌─────────────────────────────────────────────────┐
│  Your Video File (194MB)                        │
│  [========================================]     │
│  0                                           194MB│
└─────────────────────────────────────────────────┘

When you seek to middle:
VLC: "Give me bytes 97,000,000 to 97,100,000"
Server: Returns ONLY that 100KB chunk
VLC: Plays instantly from middle!
```

### Request Flow

```
1. VLC starts: GET /api/files/67/stream
   ↓
2. Server: Returns Accept-Ranges: bytes header
   ↓
3. VLC seeks: GET /api/files/67/stream
              Range: bytes=97000000-97100000
   ↓
4. Server: HTTP 206 Partial Content
           Content-Range: bytes 97000000-97100000/194285009
           Content-Length: 100000
   ↓
5. MinIO: Reads only requested bytes
   ↓
6. VLC: Plays from middle instantly
```

---

## Troubleshooting Streaming

### Video Won't Play

```bash
# 1. Check if file is a video
nebula list | grep -i "mp4\|mkv\|avi"

# 2. Test direct URL
curl -I http://YOUR_SERVER:8000/api/files/67/stream

# 3. Check server logs
docker logs nebula-api | tail -20

# 4. Verify VLC/mpv is installed
which vlc
which mpv
```

### Seeking Doesn't Work

```bash
# Test byte-range support
curl -v -H "Range: bytes=1000-2000" \
  http://YOUR_SERVER:8000/api/files/67/stream

# Should return: HTTP/1.1 206 Partial Content
# If it returns 200, byte-range isn't working
```

### Slow Buffering

- **Check network speed**: `nebula status` shows server health
- **File too large?**: Consider transcoding to smaller quality
- **Server overloaded?**: Check `nebula status` for CPU/memory

---

## Advanced: Multiple Quality Streams

Once transcoding is implemented:

```bash
# Upload original video
nebula upload movie.mkv

# Automatically transcodes to multiple qualities
# Original: movie.mkv (4K, 5GB)
# Generated: movie_1080p.mp4 (2GB)
#          : movie_720p.mp4 (800MB)
#          : movie_480p.mp4 (300MB)

# Stream specific quality
nebula play 68 --quality 720   # Stream 720p version
nebula play 68 --quality 480   # Stream 480p (faster, less bandwidth)
```

---

## Example Workflow

```bash
# 1. Upload a video
nebula upload "/mnt/c/Users/abhin/Downloads/movie.mp4" \
  --description "My movie"

# Output: ✅ Upload successful! File ID: 69

# 2. List to confirm
nebula list | head -5

# 3. Play it
nebula play 69

# VLC opens and streams the video!
# You can seek, pause, everything works like a local file
```






