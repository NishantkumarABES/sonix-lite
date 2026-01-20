# Sonix-Lite Transcription Service

A lightweight FastAPI-based transcription service that mimics Sonix API behavior using local speech recognition.

## Features

✅ **Sonix-style API** - Submit media via URL, poll status, fetch transcripts  
✅ **Asynchronous Processing** - Non-blocking downloads and transcription  
✅ **Local Storage** - No database required, file-based job tracking  
✅ **Multi-format Support** - Handles MP4, MOV, AVI, WAV, MP3  
✅ **Error Handling** - Graceful failure states with detailed error messages  
✅ **Render-Ready** - Configured for one-click deployment  

---

## Quick Start

### Local Development

```bash
# Install dependencies
pip install -r requirements.txt

# Install ffmpeg (required for moviepy)
# macOS:
brew install ffmpeg

# Ubuntu/Debian:
sudo apt-get install ffmpeg

# Start the server
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

Server will be available at `http://localhost:8000`

### Docker

```bash
docker build -t sonix-lite .
docker run -p 8000:8000 sonix-lite
```

---

## API Usage

### 1. Submit Media for Transcription

```bash
curl -X POST http://localhost:8000/media \
  -H "Content-Type: application/json" \
  -d '{
    "file_url": "https://example.com/video.mp4",
    "language": "en",
    "name": "My Video"
  }'
```

**Response:**
```json
{
  "id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "status": "processing",
  "name": "My Video",
  "created_at": "2026-01-20T10:30:00Z",
  "completed_at": null
}
```

### 2. Check Status

```bash
curl http://localhost:8000/media/a1b2c3d4-e5f6-7890-abcd-ef1234567890
```

**Response (Processing):**
```json
{
  "id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "status": "processing",
  "name": "My Video",
  "created_at": "2026-01-20T10:30:00Z",
  "completed_at": null
}
```

**Response (Completed):**
```json
{
  "id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "status": "completed",
  "name": "My Video",
  "created_at": "2026-01-20T10:30:00Z",
  "completed_at": "2026-01-20T10:32:45Z"
}
```

### 3. Fetch Transcript

**Plain Text:**
```bash
curl http://localhost:8000/media/a1b2c3d4-e5f6-7890-abcd-ef1234567890/transcript
```

**JSON Format:**
```bash
curl http://localhost:8000/media/a1b2c3d4-e5f6-7890-abcd-ef1234567890/transcript.json
```

**Response:**
```json
{
  "id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "status": "completed",
  "transcript": "This is the transcribed text from the video...",
  "created_at": "2026-01-20T10:30:00Z",
  "completed_at": "2026-01-20T10:32:45Z"
}
```

### 4. Delete Media

```bash
curl -X DELETE http://localhost:8000/media/a1b2c3d4-e5f6-7890-abcd-ef1234567890
```

---

## Python Client Example

```python
import requests
import time

# Submit media
response = requests.post('http://localhost:8000/media', json={
    'file_url': 'https://example.com/video.mp4',
    'language': 'en',
    'name': 'Test Video'
})

media_id = response.json()['id']
print(f"Job submitted: {media_id}")

# Poll status
while True:
    status_response = requests.get(f'http://localhost:8000/media/{media_id}')
    status = status_response.json()['status']
    print(f"Status: {status}")
    
    if status == 'completed':
        # Fetch transcript
        transcript = requests.get(
            f'http://localhost:8000/media/{media_id}/transcript'
        ).text
        print(f"Transcript: {transcript}")
        break
    elif status == 'failed':
        print(f"Error: {status_response.json().get('error')}")
        break
    
    time.sleep(5)
```

---

## Deployment to Render

### Method 1: Using render.yaml (Recommended)

1. Push code to GitHub
2. Connect repository to Render
3. Render will auto-detect `render.yaml` and deploy

### Method 2: Manual Setup

1. Create new **Web Service** on Render
2. Connect your repository
3. Configure:
   - **Build Command:** `pip install -r requirements.txt && apt-get update && apt-get install -y ffmpeg`
   - **Start Command:** `uvicorn main:app --host 0.0.0.0 --port $PORT`
   - **Environment:** Python 3.11

### Important Notes for Render

- **Storage is ephemeral** - Files are lost on restart
- For production, consider mounting persistent disk or using cloud storage
- Free tier has limited CPU - transcription may be slow

---

## Architecture

### File Structure

```
sonix-lite/
├── main.py              # FastAPI application
├── video_to_text.py     # Transcription engine
├── requirements.txt     # Python dependencies
├── render.yaml          # Render deployment config
├── Dockerfile           # Optional Docker config
├── storage/             # Job storage (created at runtime)
│   └── <media_id>/
│       ├── status.json
│       ├── input_media.mp4
│       └── transcript.txt
└── assets/
    └── chunks/          # Temporary audio chunks
```

### Processing Flow

1. **Submit** → Download media → Create job → Return immediately
2. **Background** → Extract audio → Split into chunks → Transcribe → Save
3. **Poll** → Read `status.json` → Return current state
4. **Fetch** → Return transcript when completed

---

## Error Handling

| Status Code | Meaning |
|------------|---------|
| 200 | Success |
| 400 | Invalid request (bad URL, etc.) |
| 404 | Media ID not found |
| 409 | Transcript requested but still processing |
| 500 | Transcription failed |

**Failed Job Response:**
```json
{
  "id": "...",
  "status": "failed",
  "error": "Google API error: ...",
  "completed_at": "2026-01-20T10:35:00Z"
}
```

---

## Configuration

### Environment Variables (Optional)

```bash
export PORT=8000                    # Server port
export MAX_WORKERS=4                # Thread pool size
export CHUNK_DURATION_MS=30000      # Audio chunk size
```

### Modify Chunk Duration

Edit `main.py` to pass custom chunk duration:

```python
transcript = await loop.run_in_executor(
    executor,
    video_to_text,
    media_path,
    60000  # 60 seconds per chunk
)
```

---

## Testing

### Health Check

```bash
curl http://localhost:8000/
```

**Response:**
```json
{
  "service": "sonix-lite",
  "status": "running",
  "version": "1.0.0"
}
```

### Test with Sample Media

```bash
# Submit a test video
curl -X POST http://localhost:8000/media \
  -H "Content-Type: application/json" \
  -d '{
    "file_url": "https://www.w3schools.com/html/mov_bbb.mp4",
    "language": "en",
    "name": "Big Buck Bunny"
  }'
```

---

## Limitations

⚠️ **No Authentication** - Anyone can submit jobs  
⚠️ **No Rate Limiting** - Could be overwhelmed by requests  
⚠️ **No Persistent Storage on Render** - Jobs lost on restart  
⚠️ **Google Speech Recognition Limits** - Free tier has quotas  
⚠️ **Single Instance** - No horizontal scaling  

---

## Troubleshooting

### "FFmpeg not found"
```bash
# Install ffmpeg
sudo apt-get install ffmpeg  # Linux
brew install ffmpeg          # macOS
```

### "Module not found"
```bash
pip install -r requirements.txt
```

### "Storage permission denied"
```bash
mkdir -p storage assets/chunks
chmod 755 storage assets/chunks
```

### Slow transcription
- Reduce `chunk_duration_ms` to smaller chunks
- Increase `max_workers` in ThreadPoolExecutor
- Use shorter videos for testing

---

## API Documentation

Once running, visit:
- **Swagger UI:** http://localhost:8000/docs
- **ReDoc:** http://localhost:8000/redoc

---

## License

MIT License - Free to use and modify

---

## Support

For issues or questions, check:
- FastAPI docs: https://fastapi.tiangolo.com
- Render docs: https://render.com/docs
- MoviePy docs: https://zulko.github.io/moviepy/