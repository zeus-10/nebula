# Network Protocol & Workload Distribution

## Network Protocol

### What We're Using: **HTTP/1.1 over TCP**

**Stack:**
```
Application Layer:  HTTP/1.1 (REST API)
Transport Layer:    TCP (reliable, ordered)
Network Layer:     IP (routing)
Link Layer:        Ethernet/WiFi/Tailscale
```

**Why HTTP?**
- ✅ Standard REST API (FastAPI)
- ✅ Easy to implement
- ✅ Works over Tailscale VPN
- ✅ Supports streaming
- ✅ Can upgrade to HTTP/2 or HTTP/3 later

**TCP Characteristics:**
- ✅ Reliable (guaranteed delivery)
- ✅ Ordered (packets arrive in order)
- ✅ Connection-oriented (handshake, then data)
- ✅ Flow control (prevents overwhelming receiver)
- ✅ Error detection/correction

---

## Who Does the Heavy Lifting?

### The Reality: **Both Have Roles, But Different Work**

### Client Side (New Laptop) Responsibilities:

**Must Do (Unavoidable):**
1. **Read file from disk** → Client's job (file is on client)
2. **Send data over network** → Client's job (data originates here)
3. **Network transmission** → Client's job (bytes must travel)

**Can Be Light:**
- ✅ Just read chunks and send (minimal processing)
- ✅ No buffering entire file
- ✅ No complex computation
- ✅ Simple streaming loop

**Client Workload:**
```
Read 10MB chunk from disk → Send to server → Repeat
Memory: ~10-50MB (one chunk at a time)
CPU: Minimal (just I/O)
Network: Sending data (unavoidable)
```

### Server Side (Old Laptop) Responsibilities:

**Does the Heavy Lifting:**
1. **Receives data** → Server's job (listening)
2. **Validates/processes** → Server's job (can be heavy)
3. **Stores to MinIO** → Server's job (S3 operations)
4. **Saves metadata to DB** → Server's job (database writes)
5. **Transcoding (later)** → Server's job (CPU-intensive)

**Server Workload:**
```
Receive chunk → Validate → Stream to MinIO → Update DB → Repeat
Memory: ~10-50MB (one chunk at a time)
CPU: Can be heavy (validation, transcoding)
Storage: Writing to MinIO (I/O intensive)
```

---

## Data Flow Breakdown

### Upload Flow:

```
┌─────────────────────────────────────────────────────────┐
│ CLIENT (New Laptop) - Light Work                        │
├─────────────────────────────────────────────────────────┤
│ 1. Read 10MB chunk from disk (I/O)                     │
│ 2. Send chunk over HTTP/TCP (network)                  │
│ 3. Repeat for next chunk                                │
│                                                          │
│ Memory: ~10-50MB                                        │
│ CPU: Minimal                                            │
│ Network: Uploading (unavoidable)                       │
└─────────────────────────────────────────────────────────┘
                    ↓ HTTP/TCP over Tailscale
┌─────────────────────────────────────────────────────────┐
│ SERVER (Old Laptop) - Heavy Lifting                     │
├─────────────────────────────────────────────────────────┤
│ 1. Receive chunk (network I/O)                          │
│ 2. Validate chunk (CPU - checksums, size, etc.)        │
│ 3. Stream to MinIO (storage I/O)                       │
│ 4. Update database (DB I/O)                           │
│ 5. Track progress (Redis)                              │
│ 6. [Later] Queue transcoding job (CPU-intensive)      │
│                                                          │
│ Memory: ~10-50MB                                        │
│ CPU: Can be heavy (validation, processing)             │
│ Storage: Writing to MinIO (I/O intensive)               │
└─────────────────────────────────────────────────────────┘
```

---

## Key Insight: **Client Sends, Server Processes**

### What Client MUST Do:
- **Read file** (file is on client's disk)
- **Send data** (data must travel over network)
- **Network transmission** (bytes must be sent)

**This is unavoidable** - the file is on the client, so the client must send it.

### What Server DOES (Heavy Lifting):
- **Receives and buffers** (handles network)
- **Validates** (checksums, file type, size limits)
- **Processes** (metadata extraction, thumbnails)
- **Stores** (MinIO operations, database writes)
- **Transcodes** (CPU-intensive video processing)

**This is where the heavy work happens** - server does all the processing.

---

## Network Protocol Details

### HTTP/1.1 Upload (Current Plan)

**Request:**
```http
POST /api/upload HTTP/1.1
Host: 100.x.y.z:8000
Content-Type: multipart/form-data
Content-Length: <chunk_size>

[Binary file data streamed in chunks]
```

**Characteristics:**
- ✅ Single TCP connection
- ✅ Streaming (chunks sent as available)
- ✅ Standard HTTP (works everywhere)
- ⚠️ One connection (can be slow for very large files)

### HTTP/2 Upload (Future Option)

**Benefits:**
- ✅ Multiplexing (multiple streams on one connection)
- ✅ Better compression
- ✅ Server push (theoretical, not used for uploads)
- ✅ More efficient for large transfers

**Trade-off:**
- More complex implementation
- Requires HTTP/2 support in FastAPI/httpx

### HTTP/3 (QUIC) Upload (Future Option)

**Benefits:**
- ✅ Built on UDP (faster connection setup)
- ✅ Better for unreliable networks
- ✅ Multiplexing
- ✅ Built-in encryption

**Trade-off:**
- Very new (limited support)
- More complex

---

## Workload Distribution Examples

### Example 1: 1GB Video Upload

**Client (New Laptop):**
```
Work: Read 1GB file in 10MB chunks, send over network
Time: ~5-10 minutes (depends on network speed)
CPU: 5% (just I/O)
Memory: 50MB (one chunk)
Network: Uploading at ~2-20 Mbps
```

**Server (Old Laptop):**
```
Work: Receive chunks, validate, store to MinIO, save to DB
Time: Same as client (receiving in parallel)
CPU: 20-30% (validation, MinIO operations)
Memory: 50MB (one chunk)
Storage: Writing to MinIO at disk speed
```

**Heavy Lifting:** Server (validation, storage, database)

---

### Example 2: 10GB Video Upload with Transcoding

**Client (New Laptop):**
```
Work: Read 10GB file, send over network
Time: ~50-100 minutes
CPU: 5% (just I/O)
Memory: 50MB
Network: Uploading
```

**Server (Old Laptop):**
```
Work: Receive, validate, store, THEN transcode
Time: Upload (50-100 min) + Transcode (30-60 min)
CPU: 80-100% during transcoding (FFmpeg)
Memory: 500MB-1GB (during transcoding)
Storage: Reading from MinIO, writing transcoded version
```

**Heavy Lifting:** Server (especially transcoding - very CPU-intensive)

---

## Why Server Does Heavy Lifting

### Advantages:

1. **Client Stays Light**
   - Client laptop can do other work
   - No CPU-intensive processing on client
   - Client just reads and sends (simple)

2. **Server Has Resources**
   - Server is dedicated (old laptop in corner)
   - Can use all CPU/RAM for processing
   - Can run multiple workers (Celery)

3. **Centralized Processing**
   - All files processed in one place
   - Consistent processing environment
   - Easier to monitor and debug

4. **Scalability**
   - Can add more workers on server
   - Can distribute transcoding across workers
   - Client doesn't need to scale

---

## Network Protocol Choice: HTTP/1.1 over TCP

### Why This Works:

**TCP Provides:**
- ✅ Reliability (no lost packets)
- ✅ Ordering (chunks arrive in order)
- ✅ Flow control (server controls speed)
- ✅ Error correction (retransmits lost packets)

**HTTP Provides:**
- ✅ Standard API (REST)
- ✅ Streaming support
- ✅ Easy to implement
- ✅ Works over Tailscale

**HTTP/1.1 Limitations:**
- ⚠️ One request per connection (for upload)
- ⚠️ Head-of-line blocking (not an issue for single upload)

**For Our Use Case:**
- ✅ HTTP/1.1 is perfect
- ✅ Simple to implement
- ✅ Works reliably
- ✅ Can upgrade later if needed

---

## Data Transmission Reality

### The Unavoidable Truth:

**Data MUST travel from client to server:**
```
Client Disk → Client Memory → Network → Server Memory → Server Disk
```

**Client's Role:**
- Read from disk (fast - local SSD)
- Send over network (speed depends on connection)
- **This is unavoidable** - file is on client

**Server's Role:**
- Receive from network
- Process (heavy work happens here)
- Store (MinIO, database)

---

## Optimizations

### 1. Compression (Optional)

**Client:**
- Compress before sending (CPU work)
- Smaller payload (faster transfer)

**Trade-off:**
- Client does more work (compression)
- Server does less work (decompression)
- May not help for already-compressed files (videos)

**Recommendation:** Skip for now (videos are already compressed)

---

### 2. Chunked Transfer Encoding

**How it works:**
```
Client sends: Chunk 1 → Chunk 2 → Chunk 3 → ...
Server receives: Chunk 1 → Chunk 2 → Chunk 3 → ...
```

**Benefits:**
- ✅ No need to know file size upfront
- ✅ Can start processing while receiving
- ✅ Better memory usage

**HTTP/1.1 supports this natively** ✅

---

### 3. Parallel Chunks (Advanced)

**Idea:** Send multiple chunks in parallel

**Reality:**
- HTTP/1.1: One connection = sequential chunks
- HTTP/2: Multiple streams = parallel chunks
- **For MVP:** Sequential is fine

**Trade-off:**
- More complex
- May not help (network is usually the bottleneck)

---

## Summary

### Network Protocol:
- **HTTP/1.1 over TCP** ✅
- Standard, reliable, works over Tailscale
- Supports streaming natively

### Workload Distribution:

**Client (Light):**
- Reads file from disk
- Sends data over network
- **Unavoidable** - file is on client

**Server (Heavy Lifting):**
- Receives and validates
- Processes (metadata, thumbnails)
- Stores (MinIO, database)
- Transcodes (CPU-intensive)

### Key Insight:

**Client must send data** (file is on client's disk), but **server does all the heavy processing**. This is the optimal distribution:

- ✅ Client stays light (just I/O)
- ✅ Server does heavy work (processing, storage)
- ✅ Network is just transport (TCP handles reliability)

**For your use case:** This is perfect! Client is thin, server does the work. 🚀

---

## Implementation

**Client Code (Light):**
```python
# Just read and send - minimal work
with open(file_path, 'rb') as f:
    for chunk in read_chunks(f, chunk_size=10*1024*1024):
        send_chunk(chunk)  # Simple HTTP POST
```

**Server Code (Heavy):**
```python
# Receive, validate, process, store - heavy work
async def upload(file: UploadFile):
    async for chunk in file.stream():
        validate_chunk(chunk)      # CPU work
        await store_to_minio(chunk)  # I/O work
        update_progress()          # DB work
    extract_metadata()            # CPU work
    create_thumbnail()            # CPU work
    save_to_database()            # DB work
```

**Result:** Client is thin, server does the heavy lifting! ✅


