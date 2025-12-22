# Large File Upload Architecture

## Problem Statement

- **CLI runs in venv** on new laptop (limited memory)
- **Large files** (videos, 4K content) can be 10GB+
- **Network** over Tailscale (may have interruptions)
- **Server** has limited RAM (8GB total)

**Challenge:** Upload large files without:
- Loading entire file into memory (client or server)
- Crashing on network interruptions
- Timing out on slow connections

---

## Architecture Options

### Option 1: Simple Streaming (Good for <1GB files)

**Flow:**
```
CLI (venv) → Stream file chunks → FastAPI → Stream to MinIO
```

**Pros:**
- Simple implementation
- Low memory usage
- Works for most files

**Cons:**
- No resume capability
- Fails completely on network error
- Single connection timeout risk

**Implementation:**
- Client: `requests` with file streaming
- Server: FastAPI `UploadFile` with streaming
- MinIO: Direct put_object with streaming

---

### Option 2: Chunked Upload (Recommended for >1GB files)

**Flow:**
```
CLI → Split file into chunks (e.g., 10MB each)
     → Upload each chunk with retry logic
     → Server stores chunks temporarily
     → Server reassembles in MinIO
```

**Pros:**
- Resume capability (track uploaded chunks)
- Better error handling
- Progress tracking per chunk
- Can retry failed chunks only

**Cons:**
- More complex implementation
- Need chunk tracking (Redis/DB)
- Temporary storage for chunks

**Implementation:**
- Client: Upload chunks sequentially with retry
- Server: Store chunks, track progress, reassemble
- MinIO: Use multipart upload API

---

### Option 3: MinIO Multipart Upload (Best for very large files)

**Flow:**
```
CLI → Request upload session from server
     → Server creates MinIO multipart upload
     → CLI uploads chunks directly to MinIO (via server proxy)
     → Server completes multipart upload
```

**Pros:**
- Native MinIO support
- Most efficient for large files
- Server doesn't buffer data
- Can resume from any chunk

**Cons:**
- Most complex
- Requires session management
- Need to handle partial uploads

---

## Recommended Approach: Hybrid

**Use different strategies based on file size:**

| File Size | Strategy | Why |
|-----------|----------|-----|
| < 100MB | Simple streaming | Fast, simple, no overhead |
| 100MB - 1GB | Chunked upload | Better error handling |
| > 1GB | MinIO multipart | Most efficient, resume support |

---

## Implementation Plan

### Phase 1: Simple Streaming (MVP)

**Client Side (CLI):**
```python
# client/cli/src/commands/upload.py
import os
from pathlib import Path
from rich.progress import Progress, BarColumn, FileSizeColumn
import httpx  # Better than requests for streaming

def upload_file(file_path: str, server_url: str):
    file_size = os.path.getsize(file_path)
    
    with open(file_path, 'rb') as f:
        with httpx.stream(
            'POST',
            f"{server_url}/api/upload",
            files={'file': f},
            data={'filename': Path(file_path).name}
        ) as response:
            # Stream file, show progress
            for chunk in response.iter_bytes():
                # Update progress bar
                pass
```

**Server Side:**
```python
# app/api/upload.py
from fastapi import APIRouter, UploadFile, File
from app.services.file_service import upload_to_s3

@router.post("/upload")
async def upload_file(file: UploadFile = File(...)):
    # Stream directly to MinIO without buffering
    await upload_to_s3(file)
    return {"status": "uploaded", "filename": file.filename}
```

**Memory Usage:**
- Client: ~10-50MB buffer (chunk size)
- Server: ~10-50MB buffer (streaming)
- **Total: ~100MB max** (regardless of file size)

---

### Phase 2: Chunked Upload (Large Files)

**Client Side:**
```python
def upload_large_file(file_path: str, chunk_size: int = 10 * 1024 * 1024):
    file_size = os.path.getsize(file_path)
    total_chunks = (file_size + chunk_size - 1) // chunk_size
    
    # Request upload session
    session = create_upload_session(file_path)
    
    # Upload chunks with retry
    for chunk_num in range(total_chunks):
        chunk_data = read_chunk(file_path, chunk_num, chunk_size)
        upload_chunk(session.id, chunk_num, chunk_data, retry=3)
    
    # Complete upload
    complete_upload(session.id)
```

**Server Side:**
- Store chunks temporarily (or stream directly to MinIO)
- Track progress in Redis
- Reassemble when complete
- Clean up on failure

---

## Technical Details

### Client Requirements

**Current CLI dependencies:**
- `requests` - Basic HTTP (not ideal for streaming)
- `rich` - Progress bars ✅

**Need to add:**
- `httpx` - Better streaming support, async
- `tqdm` or use `rich.progress` - Progress tracking

**Update `pyproject.toml`:**
```toml
dependencies = [
    "typer[all]",
    "httpx",  # Better for streaming
    "requests",  # Keep for simple requests
    "python-dotenv",
    "rich"
]
```

### Server Requirements

**FastAPI streaming:**
- `UploadFile` supports streaming natively
- Use `async for chunk in file.stream()` to read chunks
- Stream directly to MinIO without buffering

**MinIO Client:**
- `minio.put_object()` accepts file-like objects
- Can stream directly from FastAPI UploadFile
- Supports multipart for large files

### Memory Considerations

**Simple Streaming:**
- Client buffer: 10-50MB (configurable)
- Server buffer: 10-50MB (FastAPI default)
- **Total: ~100MB** regardless of file size ✅

**Chunked Upload:**
- Client: One chunk in memory at a time
- Server: One chunk in memory at a time
- **Total: ~20-100MB** (chunk size)

**MinIO Multipart:**
- Client: One chunk in memory
- Server: Minimal (just metadata)
- MinIO: Handles internally
- **Total: ~10-50MB**

---

## Error Handling

### Network Interruptions

**Simple Streaming:**
- ❌ Must restart entire upload
- ✅ Simple to implement

**Chunked Upload:**
- ✅ Resume from last successful chunk
- ✅ Retry failed chunks only
- ✅ Progress persists

**MinIO Multipart:**
- ✅ Resume from any chunk
- ✅ Server tracks uploaded parts
- ✅ Most robust

### Timeout Handling

**Client:**
- Set reasonable timeout (e.g., 5 minutes per chunk)
- Retry with exponential backoff
- Show clear error messages

**Server:**
- FastAPI timeout: 5-10 minutes default
- MinIO timeout: Configurable
- Clean up on timeout

---

## Progress Tracking

### Client Side
```python
from rich.progress import Progress, BarColumn, FileSizeColumn, TimeRemainingColumn

with Progress(
    BarColumn(),
    "[progress.percentage]{task.percentage:>3.0f}%",
    FileSizeColumn(),
    TimeRemainingColumn()
) as progress:
    task = progress.add_task("Uploading...", total=file_size)
    # Update progress as chunks upload
```

### Server Side
- For chunked: Store progress in Redis
- Return progress via WebSocket or polling endpoint
- `/api/upload/{upload_id}/progress`

---

## Recommended Implementation Order

### Step 1: Simple Streaming (MVP)
1. Implement basic streaming upload
2. Test with small files (<100MB)
3. Add progress bar
4. **Memory efficient, works for most files**

### Step 2: Add Chunked Upload
1. Detect large files (>100MB)
2. Automatically use chunked upload
3. Add resume capability
4. **Better for large files**

### Step 3: MinIO Multipart (Optional)
1. For very large files (>1GB)
2. Use MinIO native multipart
3. **Most efficient, but complex**

---

## Example: 10GB Video Upload

### Simple Streaming
- Memory: ~100MB
- Time: Depends on network
- Risk: High (one failure = restart)
- **Good for: Reliable network, smaller files**

### Chunked Upload
- Memory: ~50MB
- Time: Same, but can resume
- Risk: Low (resume from last chunk)
- **Good for: Unreliable network, large files**

### MinIO Multipart
- Memory: ~20MB
- Time: Same, most efficient
- Risk: Very low
- **Good for: Very large files, production**

---

## Decision Matrix

| File Size | Network | Recommended |
|-----------|---------|-------------|
| < 100MB | Any | Simple streaming |
| 100MB - 1GB | Reliable | Simple streaming |
| 100MB - 1GB | Unreliable | Chunked upload |
| > 1GB | Any | MinIO multipart |

---

## Next Steps

1. **Start with simple streaming** (MVP)
   - Works for most files
   - Low memory usage
   - Easy to implement

2. **Add chunked upload later** (if needed)
   - When users report issues with large files
   - Or if network is unreliable

3. **Consider MinIO multipart** (advanced)
   - Only if very large files are common
   - Or if resume is critical

---

## Summary

**For MVP (Phase 2):**
- ✅ Use **simple streaming** with `httpx` on client
- ✅ Stream directly to MinIO on server
- ✅ Memory usage: ~100MB max (regardless of file size)
- ✅ Works in venv (no memory issues)
- ✅ Progress tracking with `rich`

**For Production:**
- Add chunked upload for files >100MB
- Add resume capability
- Consider MinIO multipart for very large files

**Key Insight:** Streaming prevents memory issues. Even a 10GB file only uses ~100MB of RAM during upload! 🚀

