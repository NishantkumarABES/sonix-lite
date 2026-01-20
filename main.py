from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.responses import PlainTextResponse, JSONResponse
from pydantic import BaseModel, HttpUrl, Field
from typing import Optional, Literal
import uuid
import os
import json
import asyncio
import aiohttp
import aiofiles
from datetime import datetime
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
import traceback

from video_to_text import video_to_text

app = FastAPI(
    title="Sonix-Lite Transcription Service",
    description="Lightweight local transcription API mimicking Sonix behavior",
    version="1.0.0"
)

# Configuration
STORAGE_DIR = Path("storage")
STORAGE_DIR.mkdir(exist_ok=True)

# Thread pool for CPU-bound transcription work
executor = ThreadPoolExecutor(max_workers=4)


# ============================================================================
# REQUEST/RESPONSE MODELS
# ============================================================================

class MediaSubmissionRequest(BaseModel):
    file_url: HttpUrl
    language: str = Field(default="en", description="Language code (e.g., 'en')")
    name: Optional[str] = Field(default=None, description="Optional human-readable name")


class MediaResponse(BaseModel):
    id: str
    status: Literal["processing", "completed", "failed"]
    name: Optional[str] = None
    created_at: str
    completed_at: Optional[str] = None
    error: Optional[str] = None


# ============================================================================
# STORAGE UTILITIES
# ============================================================================

def get_media_dir(media_id: str) -> Path:
    """Get the storage directory for a media item"""
    return STORAGE_DIR / media_id


def get_status_file(media_id: str) -> Path:
    """Get the status.json file path"""
    return get_media_dir(media_id) / "status.json"


def get_transcript_file(media_id: str) -> Path:
    """Get the transcript.txt file path"""
    return get_media_dir(media_id) / "transcript.txt"


def get_media_file(media_id: str) -> Path:
    """Get the input media file path"""
    media_dir = get_media_dir(media_id)
    # Find the first media file in the directory
    for ext in ['.mp4', '.mov', '.avi', '.mkv', '.wav', '.mp3']:
        media_file = media_dir / f"input_media{ext}"
        if media_file.exists():
            return media_file
    return media_dir / "input_media.mp4"


def read_status(media_id: str) -> dict:
    """Read status from status.json"""
    status_file = get_status_file(media_id)
    if not status_file.exists():
        raise HTTPException(status_code=404, detail=f"Media ID {media_id} not found")
    
    with open(status_file, 'r') as f:
        return json.load(f)


def write_status(media_id: str, status_data: dict):
    """Write status to status.json"""
    status_file = get_status_file(media_id)
    with open(status_file, 'w') as f:
        json.dump(status_data, f, indent=2)


# ============================================================================
# ASYNC FILE DOWNLOAD
# ============================================================================

async def download_media(url: str, destination: Path) -> str:
    """Download media file from URL to destination"""
    async with aiohttp.ClientSession() as session:
        async with session.get(str(url)) as response:
            if response.status != 200:
                raise Exception(f"Failed to download: HTTP {response.status}")
            
            # Determine file extension from URL or Content-Type
            content_type = response.headers.get('Content-Type', '')
            url_path = str(url).split('?')[0]  # Remove query params
            
            if url_path.endswith(('.mp4', '.mov', '.avi', '.mkv', '.wav', '.mp3')):
                ext = Path(url_path).suffix
            elif 'video/mp4' in content_type:
                ext = '.mp4'
            elif 'video/' in content_type:
                ext = '.mp4'
            elif 'audio/' in content_type:
                ext = '.wav'
            else:
                ext = '.mp4'
            
            # Update destination with correct extension
            final_destination = destination.parent / f"input_media{ext}"
            
            async with aiofiles.open(final_destination, 'wb') as f:
                async for chunk in response.content.iter_chunked(8192):
                    await f.write(chunk)
            
            return str(final_destination)


# ============================================================================
# BACKGROUND TRANSCRIPTION TASK
# ============================================================================

async def process_transcription(media_id: str, media_path: str):
    """Background task to process transcription"""
    try:
        # Update status to processing
        status_data = read_status(media_id)
        status_data["status"] = "processing"
        write_status(media_id, status_data)
        
        # Run CPU-bound transcription in thread pool
        loop = asyncio.get_event_loop()
        transcript = await loop.run_in_executor(
            executor,
            video_to_text,
            media_path
        )
        
        # Save transcript
        transcript_file = get_transcript_file(media_id)
        async with aiofiles.open(transcript_file, 'w') as f:
            await f.write(transcript)
        
        # Update status to completed
        status_data = read_status(media_id)
        status_data["status"] = "completed"
        status_data["completed_at"] = datetime.utcnow().isoformat() + "Z"
        write_status(media_id, status_data)
        
    except Exception as e:
        # Update status to failed
        error_msg = f"{str(e)}\n{traceback.format_exc()}"
        status_data = read_status(media_id)
        status_data["status"] = "failed"
        status_data["error"] = error_msg
        status_data["completed_at"] = datetime.utcnow().isoformat() + "Z"
        write_status(media_id, status_data)


# ============================================================================
# API ENDPOINTS
# ============================================================================

@app.get("/")
async def root():
    """Health check endpoint"""
    return {
        "service": "sonix-lite",
        "status": "running",
        "version": "1.0.0"
    }


@app.post("/media", response_model=MediaResponse)
async def submit_media(request: MediaSubmissionRequest, background_tasks: BackgroundTasks):
    """
    Submit a media file for transcription
    
    - Downloads media from provided URL
    - Starts transcription in background
    - Returns immediately with job ID
    """
    # Generate unique media ID
    media_id = str(uuid.uuid4())
    
    # Create storage directory
    media_dir = get_media_dir(media_id)
    media_dir.mkdir(parents=True, exist_ok=True)
    
    # Initialize status
    created_at = datetime.utcnow().isoformat() + "Z"
    status_data = {
        "id": media_id,
        "status": "processing",
        "name": request.name,
        "created_at": created_at,
        "completed_at": None,
        "error": None
    }
    write_status(media_id, status_data)
    
    try:
        # Download media file
        media_path = await download_media(
            str(request.file_url),
            get_media_file(media_id)
        )
        
        # Start transcription in background
        background_tasks.add_task(process_transcription, media_id, media_path)
        
        return MediaResponse(**status_data)
        
    except Exception as e:
        # If download fails, mark as failed immediately
        status_data["status"] = "failed"
        status_data["error"] = f"Download failed: {str(e)}"
        status_data["completed_at"] = datetime.utcnow().isoformat() + "Z"
        write_status(media_id, status_data)
        
        raise HTTPException(
            status_code=400,
            detail=f"Failed to download media: {str(e)}"
        )


@app.get("/media/{media_id}", response_model=MediaResponse)
async def get_media_status(media_id: str):
    """
    Get transcription status for a media item
    
    - Returns current status (processing/completed/failed)
    - Includes timestamps and error info if applicable
    """
    status_data = read_status(media_id)
    return MediaResponse(**status_data)


@app.get("/media/{media_id}/transcript", response_class=PlainTextResponse)
async def get_transcript_text(media_id: str):
    """
    Get plain text transcript
    
    - Returns transcript if completed
    - Returns 409 if still processing
    """
    status_data = read_status(media_id)
    
    if status_data["status"] == "processing":
        raise HTTPException(
            status_code=409,
            detail="Transcription still in progress"
        )
    
    if status_data["status"] == "failed":
        raise HTTPException(
            status_code=500,
            detail=f"Transcription failed: {status_data.get('error', 'Unknown error')}"
        )
    
    transcript_file = get_transcript_file(media_id)
    if not transcript_file.exists():
        raise HTTPException(
            status_code=404,
            detail="Transcript file not found"
        )
    
    async with aiofiles.open(transcript_file, 'r') as f:
        content = await f.read()
    
    return content


@app.get("/media/{media_id}/transcript.json")
async def get_transcript_json(media_id: str):
    """
    Get structured JSON transcript
    
    - Returns transcript in JSON format with metadata
    """
    status_data = read_status(media_id)
    
    if status_data["status"] == "processing":
        raise HTTPException(
            status_code=409,
            detail="Transcription still in progress"
        )
    
    if status_data["status"] == "failed":
        raise HTTPException(
            status_code=500,
            detail=f"Transcription failed: {status_data.get('error', 'Unknown error')}"
        )
    
    transcript_file = get_transcript_file(media_id)
    if not transcript_file.exists():
        raise HTTPException(
            status_code=404,
            detail="Transcript file not found"
        )
    
    async with aiofiles.open(transcript_file, 'r') as f:
        content = await f.read()
    
    return {
        "id": media_id,
        "status": status_data["status"],
        "transcript": content,
        "created_at": status_data["created_at"],
        "completed_at": status_data["completed_at"]
    }


@app.delete("/media/{media_id}")
async def delete_media(media_id: str):
    """
    Delete a media item and all associated files
    """
    media_dir = get_media_dir(media_id)
    
    if not media_dir.exists():
        raise HTTPException(status_code=404, detail=f"Media ID {media_id} not found")
    
    # Remove all files in the directory
    import shutil
    shutil.rmtree(media_dir)
    
    return {"message": f"Media {media_id} deleted successfully"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)