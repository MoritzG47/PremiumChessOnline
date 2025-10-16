from fastapi import FastAPI, WebSocket
import uvicorn

app = FastAPI()
clients = []

@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await ws.accept()
    clients.append(ws)
    print("New client connected.")
    try:
        while True:
            data = await ws.receive_text()
            print(f"Received: {data}")
            # Echo back to all clients (except sender)
            for client in clients:
                if client != ws:
                    await client.send_text(f"Opponent: {data}")
    except:
        clients.remove(ws)
        print("Client disconnected.")

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
