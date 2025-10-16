import asyncio
import websockets

async def play(name):
    uri = "ws://localhost:8000/ws"
    async with websockets.connect(uri) as ws:
        print(f"{name} connected.")
        async def receiver():
            while True:
                msg = await ws.recv()
                print(f"\n{name} received: {msg}")

        asyncio.create_task(receiver())

        while True:
            text = input(f"{name} move> ")
            await ws.send(f"{name}: {text}")

asyncio.run(play(input("Enter your name: ")))
