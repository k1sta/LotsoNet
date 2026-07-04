import asyncio
import sys
from kademlia.network import Server

async def init_node(port):
    server = Server()
    await server.listen(port, interface="127.0.0.1")
    
    connection_success = await server.bootstrap([("127.0.0.1", 8468)])
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
    if len(sys.argv) < 2:
        print("Usage: python node.py <port>")
        sys.exit(1)
        
    port = int(sys.argv[1])
    try:
        asyncio.run(init_node(port))
    except KeyboardInterrupt:
        print(f"\nNode on {port} disconnected.")