import asyncio
import os
from kademlia.network import Server

LISTEN_PORT = int(os.environ.get("LOTSONET_PORT", 8468))
LISTEN_INTERFACE = os.environ.get("LOTSONET_INTERFACE", "0.0.0.0")

async def bootstrap():
    server = Server()
    await server.listen(LISTEN_PORT, interface=LISTEN_INTERFACE)
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