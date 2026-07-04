import asyncio
import json
import os
import random
import socket
import uuid

from netutil import get_broadcast_address, get_local_ip, pick_primary_interface

DISCOVERY_MAGIC = "LOTSONET-DISCOVERY-V1"
NETWORK_ID = os.environ.get("LOTSONET_NETWORK_ID", "lotsonet")
DISCOVERY_PORT = int(os.environ.get("LOTSONET_DISCOVERY_PORT", 8469))
DISCOVERY_TIMEOUT = float(os.environ.get("LOTSONET_DISCOVERY_TIMEOUT", 2.0))
DISCOVERY_ROUNDS = int(os.environ.get("LOTSONET_DISCOVERY_ROUNDS", 2))

INSTANCE_ID = uuid.uuid4().hex


class DiscoveryProtocol(asyncio.DatagramProtocol):
    def __init__(self, kademlia_port, on_peer_found):
        self.kademlia_port = kademlia_port
        self.on_peer_found = on_peer_found
        self.transport = None

    def connection_made(self, transport):
        self.transport = transport

    def datagram_received(self, data, addr):
        try:
            msg = json.loads(data.decode("utf-8"))
            if msg.get("magic") != DISCOVERY_MAGIC or msg.get("network") != NETWORK_ID:
                return
            if msg.get("from_id") == INSTANCE_ID:
                return
        except (json.JSONDecodeError, UnicodeDecodeError, AttributeError):
            return

        if msg.get("type") == "DISCOVER":
            reply = json.dumps({
                "magic": DISCOVERY_MAGIC,
                "network": NETWORK_ID,
                "type": "ANNOUNCE",
                "from_id": INSTANCE_ID,
                "kademlia_port": self.kademlia_port,
            }).encode("utf-8")
            self.transport.sendto(reply, addr)
        elif msg.get("type") == "ANNOUNCE":
            port = msg.get("kademlia_port")
            if port:
                self.on_peer_found((addr[0], port))

    def error_received(self, exc):
        print(f"[Discovery] Socket error: {exc}")


async def discover_peers(kademlia_port, rounds=DISCOVERY_ROUNDS, timeout=DISCOVERY_TIMEOUT):
    found = set()

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    sock.bind(("0.0.0.0", DISCOVERY_PORT))

    loop = asyncio.get_event_loop()
    transport, _ = await loop.create_datagram_endpoint(
        lambda: DiscoveryProtocol(kademlia_port, found.add), sock=sock
    )

    iface = pick_primary_interface(os.environ.get("LOTSONET_IFACE_NAME"))
    local_ip = get_local_ip(iface)
    broadcast_addr = get_broadcast_address(local_ip, iface) if local_ip and iface else "255.255.255.255"

    request = json.dumps({
        "magic": DISCOVERY_MAGIC,
        "network": NETWORK_ID,
        "type": "DISCOVER",
        "from_id": INSTANCE_ID,
        "kademlia_port": kademlia_port,
    }).encode("utf-8")

    for _ in range(max(1, rounds)):
        try:
            transport.sendto(request, (broadcast_addr, DISCOVERY_PORT))
        except OSError as exc:
            print(f"[Discovery] Failed to broadcast on {broadcast_addr}: {exc}")
            break
        await asyncio.sleep(timeout + random.uniform(0, 0.3))
        if found:
            break

    return transport, list(found)
