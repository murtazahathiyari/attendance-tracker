"""Stub endpoint that just receives a frame and confirms it.

Used in Step 4 to verify the browser webcam pipeline works end-to-end
before we plug in face recognition. Will be replaced by the real
check-in pipeline in Step 8.
"""
import io
from datetime import datetime

from fastapi import APIRouter, HTTPException, UploadFile
from PIL import Image


router = APIRouter(prefix="/api/camera-test", tags=["dev"])


@router.post("/echo")
async def echo_frame(frame: UploadFile):
    if not frame.content_type or not frame.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="Expected an image upload.")

    raw = await frame.read()
    try:
        img = Image.open(io.BytesIO(raw))
        img.verify()
        width, height = img.size
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Not a valid image: {e}")

    return {
        "received_bytes": len(raw),
        "width": width,
        "height": height,
        "server_time": datetime.utcnow().isoformat() + "Z",
    }
