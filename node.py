import asyncio
import os
import sys
from kademlia.network import Server

LISTEN_INTERFACE = os.environ.get("LOTSONET_INTERFACE", "0.0.0.0")
BOOTSTRAP_HOST = os.environ.get("BOOTSTRAP_HOST", "127.0.0.1")
BOOTSTRAP_PORT = int(os.environ.get("BOOTSTRAP_PORT", 8468))

async def init_node(port):
    server = Server()
    await server.listen(port, interface=LISTEN_INTERFACE)

    connection_success = await server.bootstrap([(BOOTSTRAP_HOST, BOOTSTRAP_PORT)])
    if not connection_success:
        print(f"[Error] Couldn't connect on port {port}")
        server.stop()
        return

    key = f"status-{port}"
    await server.set(key, "online")
    
    val = await server.get(key)
    print(f"[Node {port}] Connected. Testing DHT: '{key}' -> '{val}'")

    try:
        await asyncio.Event().wait()
    except asyncio.CancelledError:
        pass
    finally:
        server.stop()

if __name__ == "__main__":
    if len(sys.argv) >= 2:
        port = int(sys.argv[1])
    else:
        port = int(os.environ.get("LOTSONET_PORT", 8469))
    try:
        asyncio.run(init_node(port))
    except KeyboardInterrupt:
        print(f"\nNode on {port} disconnected.")