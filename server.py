from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
import asyncio

app = FastAPI()

# Add CORS middleware to handle requests from different origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class ConnectionManager:
    def __init__(self):
        self.active_connections: list[WebSocket] = []
        self.openside = [None, None]  

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

        side = 0
        if self.openside[0] is None:
            self.openside[0] = websocket
            side = 0
        elif self.openside[1] is None:
            self.openside[1] = websocket
            side = 1
            await self.broadcast("start", sender=None)
            print("Game started!")
        else:
            # More than two clients, assign as spectator (-1)
            side = -1
        await self.send_message(f"init:{side}", sender=None, recipient=websocket)
        print(f"New client connected. Total clients: {len(self.active_connections)}")

    def disconnect(self, websocket: WebSocket):
        """Synchronous disconnect - remove from lists"""
        if self.openside[0] == websocket:
            self.openside[0] = None
        elif self.openside[1] == websocket:
            self.openside[1] = None
        
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
        print(f"Client disconnected. Total clients: {len(self.active_connections)}")

    async def handle_disconnect(self, websocket: WebSocket):
        """Async method to handle disconnection with broadcast"""
        self.disconnect(websocket)
        if self.openside[0] is None or self.openside[1] is None:
            print("A player disconnected, stopping the game.")
            await self.broadcast("stop", sender=None)

    async def broadcast(self, message: str, sender: WebSocket = None):
        disconnected_clients = []
        for connection in self.active_connections:
            if connection != sender:  # Don't send back to sender
                try:
                    await connection.send_text(message)
                except Exception as e:
                    print(f"Failed to send to client: {e}")
                    disconnected_clients.append(connection)
        
        # Remove disconnected clients
        for client in disconnected_clients:
            self.disconnect(client)

    async def send_message(self, message: str, sender: WebSocket = None, recipient: WebSocket = None):
        if recipient:
            try:
                await recipient.send_text(message)
            except Exception as e:
                print(f"Failed to send to client: {e}")
                self.disconnect(recipient)
        else:
            await self.broadcast(message, sender)

manager = ConnectionManager()

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            print(f"Received: {data}")
            # Broadcast to all other clients
            await manager.broadcast(f"Opponent: {data}", sender=websocket)
    except WebSocketDisconnect:
        print("WebSocketDisconnect exception caught - client disconnected normally")
        await manager.handle_disconnect(websocket)
    except Exception as e:
        print(f"Unexpected error: {e}")
        await manager.handle_disconnect(websocket)

@app.get("/")
async def root():
    return {"message": "WebSocket server is running"}

@app.get("/status")
async def status():
    return {
        "active_connections": len(manager.active_connections),
        "openside_0": manager.openside[0] is not None,
        "openside_1": manager.openside[1] is not None
    }

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")