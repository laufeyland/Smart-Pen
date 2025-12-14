import asyncio
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request, Form
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from datetime import datetime
import csv, os, shutil

app = FastAPI(title="Shape Recognition & Quality Analysis Server")

# ---------------- Middleware ----------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------- Models ----------------
class MPUData(BaseModel):
    ax: float
    ay: float
    az: float
    gx: float
    gy: float
    gz: float
    temp: float | None = None
    timestamp: float | None = None

class LabelRequest(BaseModel):
    shape: str
    quality: str
    hand: str
    filename: str  # raw file to move

# ---------------- Globals ----------------
recording = False
current_shape = None
current_filename = None
csv_file = None
csv_writer = None
connected_clients: list[WebSocket] = []     # dashboard clients
pen_socket: WebSocket | None = None         # ESP32 pen connection
pen_state = "offline"
last_seen = None

BASE_DIR = "sessions"
RAW_DIR = os.path.join(BASE_DIR, "raw")
LABELED_DIR = os.path.join(BASE_DIR, "labeled")

os.makedirs(RAW_DIR, exist_ok=True)
os.makedirs(LABELED_DIR, exist_ok=True)

# ---------------- Helpers ----------------
async def broadcast(data: dict):
    """Send data to all connected dashboard clients."""
    disconnected = []
    for ws in connected_clients:
        try:
            await ws.send_json(data)
        except:
            disconnected.append(ws)
    for ws in disconnected:
        connected_clients.remove(ws)

def ensure_dir(path):
    os.makedirs(path, exist_ok=True)

# ---------------- Routes ----------------

@app.get("/status")
def status():
    """Return server and session status."""
    return {
        "server": "online",
        "recording": recording,
        "current_shape": current_shape,
        "current_file": current_filename,
        "clients": len(connected_clients),
        "pen_state": pen_state,
    }

@app.post("/start_recording")
async def start_recording(request: Request, shape: str = Form(None)):
    """Start recording session (only 'shape' required)."""
    global recording, current_shape, csv_file, csv_writer, current_filename

    if not shape:
        try:
            data = await request.json()
            shape = data.get("shape")
        except:
            return {"error": "Missing 'shape' parameter"}
    if not shape:
        return {"error": "Shape not provided"}

    current_shape = shape
    ensure_dir(RAW_DIR)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    current_filename = f"{shape}_{timestamp}.csv"
    filepath = os.path.join(RAW_DIR, current_filename)

    csv_file = open(filepath, "w", newline="")
    csv_writer = csv.DictWriter(csv_file, fieldnames=[
        "timestamp", "ax", "ay", "az", "gx", "gy", "gz", "temp"
    ])
    csv_writer.writeheader()
    recording = True

    return {"message": f"Recording started for shape '{shape}'", "filename": current_filename}

async def monitor_pen_offline():
    global pen_state, last_seen
    while True:
        await asyncio.sleep(1)
        if last_seen is not None:
            if datetime.now().timestamp() - last_seen > 3:
                if pen_state != "offline":
                    pen_state = "offline"


@app.post("/data")
async def receive_data(data: MPUData):
    """Receive MPU6050 data, write to CSV, and broadcast."""
    global recording, csv_writer, csv_file
    #Set the Pen status to online when data is received
    global pen_state, last_seen
    pen_state = "online"
    last_seen = datetime.now().timestamp()  # update last seen timestamp
    
    if not recording or csv_writer is None:
        return {"status": "ignored", "reason": "not recording"}

    row = {
        "timestamp": data.timestamp or datetime.now().timestamp(),
        "ax": data.ax,
        "ay": data.ay,
        "az": data.az,
        "gx": data.gx,
        "gy": data.gy,
        "gz": data.gz,
        "temp": data.temp if data.temp is not None else 0.0,
    }

    csv_writer.writerow(row)
    csv_file.flush()

    await broadcast({"type": "mpu_data", "data": row})
    return {"status": "ok"}

@app.post("/stop_recording")
async def stop_recording():
    """Stop recording and close the CSV file."""
    global recording, csv_file, csv_writer, current_shape, current_filename

    if not recording:
        return {"error": "No active recording"}

    recording = False
    if csv_file:
        csv_file.close()

    csv_writer = None
    csv_file = None
    stopped_shape = current_shape
    stopped_filename = current_filename
    current_shape = None
    current_filename = None

    return {
        "message": f"Recording stopped for shape '{stopped_shape}'",
        "filename": stopped_filename,
    }

@app.post("/label_session")
async def label_session(req: LabelRequest):
    """Label a raw session and move it to labeled/<shape>/<quality>/<hand>."""
    shape = req.shape.capitalize()
    quality = req.quality.capitalize()
    hand = req.hand.capitalize()
    src_path = os.path.join(RAW_DIR, req.filename)
    if not os.path.exists(src_path):
        return {"error": f"File not found: {req.filename}"}
    dest_dir = os.path.join(LABELED_DIR, shape, quality, hand)
    ensure_dir(dest_dir)
    dest_path = os.path.join(dest_dir, req.filename)
    shutil.move(src_path, dest_path)
    return {"message": f"Labeled as {quality}", "moved_to": dest_path}

# ---------------- WebSocket: Dashboard ----------------
@app.websocket("/ws/live")
async def ws_live(websocket: WebSocket):
    """WebSocket for dashboard clients."""
    await websocket.accept()
    connected_clients.append(websocket)
    await websocket.send_json({
        "type": "connection",
        "message": "Connected to live feed",
        "pen_state": pen_state,
    })
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        connected_clients.remove(websocket)

@app.on_event("startup")
async def startup_event():
    asyncio.create_task(monitor_pen_offline())
