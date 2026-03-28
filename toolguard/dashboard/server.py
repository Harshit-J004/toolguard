import json
import os
import time
import asyncio
from pathlib import Path
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from sse_starlette.sse import EventSourceResponse
import toolguard

# Constants
TRACES_DIR = Path(".toolguard/mcp_traces")
STATIC_DIR = Path(__file__).parent / "static"

app = FastAPI(title="ToolGuard Live Dashboard")

# Ensure required directories exist
TRACES_DIR.mkdir(parents=True, exist_ok=True)
STATIC_DIR.mkdir(parents=True, exist_ok=True)

# Mount static files (HTML, CSS, JS)
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

@app.get("/")
async def root():
    """Serve the main Live Dashboard HTML."""
    index_path = STATIC_DIR / "index.html"
    html = index_path.read_text(encoding="utf-8")
    html = html.replace("{{VERSION}}", toolguard.__version__)
    return HTMLResponse(content=html)

def get_all_traces():
    """Read and parse all trace files, sorted by time (newest first)."""
    traces = []
    if not TRACES_DIR.exists():
        return traces
        
    for file in sorted(TRACES_DIR.glob("*.json"), key=os.path.getmtime, reverse=True):
        try:
            with open(file, "r") as f:
                data = json.load(f)
                if isinstance(data, dict):
                    traces.append(data)
                elif isinstance(data, list):
                    traces.extend(data)
        except Exception:
            pass
    return traces

@app.get("/api/traces")
async def api_traces():
    """Return the last 100 historical traces for initial load."""
    return {"traces": get_all_traces()[:100]}

async def trace_event_generator():
    """Watch for new trace files and emit Server-Sent Events."""
    seen_files = set(TRACES_DIR.glob("*.json"))
    
    while True:
        await asyncio.sleep(0.5)
        current_files = set(TRACES_DIR.glob("*.json"))
        new_files = current_files - seen_files
        
        for file in sorted(new_files, key=os.path.getmtime):
            # Wait briefly to ensure file is fully written
            await asyncio.sleep(0.1)
            try:
                with open(file, "r") as f:
                    data = json.load(f)
                    yield {
                        "event": "new_trace",
                        "data": json.dumps(data)
                    }
            except Exception:
                pass
        seen_files = current_files

@app.get("/api/stream")
async def api_stream():
    """SSE endpoint for live trace streaming."""
    return EventSourceResponse(trace_event_generator())

# ── Obsidian Security State ───────────────────────
SECURITY_LOCKED = False

@app.post("/api/toggle_security")
async def toggle_security():
    """Toggle the global proxy security mesh state (Simulated)."""
    global SECURITY_LOCKED
    SECURITY_LOCKED = not SECURITY_LOCKED
    status = "LOCKED" if SECURITY_LOCKED else "SECURE"
    return {"status": status, "timestamp": time.time()}
