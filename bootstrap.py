import asyncio
from kademlia.network import Server

async def bootstrap():
    server = Server()
    await server.listen(8468, interface="127.0.0.1")
    try:
        await asyncio.Event().wait()
    except asyncio.CancelledError:
        pass
    finally:
        server.stop()

if __name__ == "__main__":
    try:
        asyncio.run(bootstrap())
    except KeyboardInterrupt:
        print("\nNode disconnected.")