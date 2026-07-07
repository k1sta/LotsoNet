import asyncio
import json
import os
import random
import re
import sys
import uuid
from contextlib import suppress
from pathlib import Path

from kademlia.crawling import NodeSpiderCrawl
from kademlia.network import Server
from kademlia.node import Node as KademliaNode

import discovery
from envelope import load_or_create_keypair, node_id_bytes_for_key
from exec_node import exec_code, serialize_value

LISTEN_INTERFACE = os.environ.get("LOTSONET_INTERFACE", "0.0.0.0")
BOOTSTRAP_HOST = os.environ.get("BOOTSTRAP_HOST")
BOOTSTRAP_PORT = int(os.environ.get("BOOTSTRAP_PORT", 8468))
NODE_KEY_FILE = os.environ.get("LOTSONET_KEY_FILE", ".lotsonet_key")

# host
port  = int(os.environ.get("LOTSONET_PORT", 8468))


def format_dht_value(value):
    if isinstance(value, bytes):
        try:
            return value.decode("utf-8")
        except UnicodeDecodeError:
            return repr(value)
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            return value
        return json.dumps(parsed, indent=2, ensure_ascii=False)
    try:
        return json.dumps(value, indent=2, ensure_ascii=False)
    except (TypeError, ValueError):
        return str(value)


def value_to_bytes(value):
    if isinstance(value, bytes):
        return value
    if isinstance(value, bytearray):
        return bytes(value)
    if isinstance(value, str):
        return value.encode("utf-8")
    try:
        return json.dumps(value, ensure_ascii=False).encode("utf-8")
    except (TypeError, ValueError):
        return str(value).encode("utf-8")


def _storage_items(server):
    storage = getattr(server, "storage", None)
    if storage is None:
        protocol = getattr(server, "protocol", None)
        storage = getattr(protocol, "storage", None)
    if storage is None:
        return []

    if hasattr(storage, "items"):
        return list(storage.items())

    data = getattr(storage, "data", None)
    if isinstance(data, dict):
        items = []
        for key, stored in data.items():
            if isinstance(stored, tuple) and len(stored) == 2:
                items.append((key, stored[1]))
            else:
                items.append((key, stored))
        return items

    items = []
    try:
        keys = list(storage)
    except TypeError:
        return []
    for key in keys:
        try:
            items.append((key, storage[key]))
        except (KeyError, TypeError):
            continue
    return items


def _display_key(key):
    return key.hex() if isinstance(key, bytes) else str(key)


def local_storage_matches(server, pattern):
    regex = re.compile(pattern)
    matches = []
    for key, value in _storage_items(server):
        display_key = _display_key(key)
        if regex.search(display_key):
            matches.append((display_key, value))
    return matches


async def get_dht_entries(server, entry):
    value = await server.get(entry)
    if value is not None:
        return [(entry, value)], True
    return local_storage_matches(server, entry), False


async def show_dht_entry(server, entry):
    return await get_dht_entries(server, entry)


async def dump_dht_entry(server, entry, target):
    value = await server.get(entry)
    if value is None:
        return None
    data = value_to_bytes(value)
    Path(target).write_bytes(data)
    return len(data)


def known_node_ids(server: Server) -> set:
    ids = {server.node.id.hex()}
    for bucket in server.protocol.router.buckets:
        for node in bucket.get_nodes():
            ids.add(node.id.hex())
    return ids


async def refresh_membership(server: Server, rounds: int = 4):
    protocol = server.protocol
    lookups = []
    for _ in range(rounds):
        target = KademliaNode(os.urandom(20))
        nearest = protocol.router.find_neighbors(target, server.alpha)
        if not nearest:
            continue
        spider = NodeSpiderCrawl(protocol, target, nearest, server.ksize, server.alpha)
        lookups.append(spider.find())
    if lookups:
        await asyncio.gather(*lookups)


async def listen_for_tasks(server: Server, port: int, processed_tasks: set, node_id: str):
    while True:
        try:
            payload_str = await server.get("lotsonet:current-task")
            if not payload_str:
                await asyncio.sleep(1)
                continue

            try:
                payload = json.loads(payload_str)
            except (TypeError, json.JSONDecodeError):
                await asyncio.sleep(1)
                continue

            task_id = payload.get("id")
            if not task_id or task_id in processed_tasks:
                await asyncio.sleep(1)
                continue

            processed_tasks.add(task_id)
            filename = payload.get("filename", "<unknown>")
            code = payload.get("code", "")
            print(f"[Node {port}] Recebido comando distribuído: {filename}")

            result_key = f"lotsonet:result:{task_id}:{node_id}"
            try:
                result = await exec_code(code)
                await server.set(result_key, serialize_value(result))
                print(f"[Node {port}] Resultado salvo em {result_key}: {result!r}")
            except Exception as exc:
                await server.set(result_key, serialize_value({"error": str(exc)}))
                print(f"[Node {port}] Erro ao executar comando distribuído: {exc}")
        except Exception as exc:
            print(f"[Node {port}] Falha ao ouvir por comandos: {exc}")
        await asyncio.sleep(1)


async def init_node(port: int):
    private_key = load_or_create_keypair(Path(NODE_KEY_FILE))
    node_id_bytes = node_id_bytes_for_key(private_key)
    server = Server(node_id=node_id_bytes)
    await server.listen(port, interface=LISTEN_INTERFACE)

    discovery_transport, peers = await discovery.discover_peers(port)

    if BOOTSTRAP_HOST:
        peers.append((BOOTSTRAP_HOST, BOOTSTRAP_PORT))
    peers = list(dict.fromkeys(peers))

    if peers:
        connection_success = await server.bootstrap(peers)
        if not connection_success:
            print(f"[Node {port}] Warning: found {len(peers)} peer(s) but couldn't bootstrap against any; continuing standalone.")
        else:
            print(f"[Node {port}] Bootstrapped against {len(peers)} peer(s).")
    else:
        print(f"[Node {port}] No peers discovered; starting a new LotsoNet network as the first node.")

    node_id = node_id_bytes.hex()
    processed_tasks: set = set()

    listener_task = asyncio.create_task(listen_for_tasks(server, port, processed_tasks, node_id))
    print(f"[Node {port}] Ready. Use help to see commands.")

    try:
        while True:
            args = []
            command = []
            try:
                usr_input = await asyncio.to_thread(input, f"[Node {port}] Arquivo> ")
                usr_input = usr_input.strip().split()
                if usr_input is None or len(usr_input) == 0:
                    continue
                elif len(usr_input) == 1:
                    command = usr_input[0]
                else:
                    command = usr_input[0]
                    args    = usr_input[1:]
            except EOFError:
                break

            if   command == "help":
                print(f"[Node {port}]: help: list of commands.")
                print(f"[Node {port}]: quit: stop.")
                print(f"[Node {port}]: run <script>: runs the python script on every machine on every node.")
                print(f"[Node {port}]: collect <task_id>: gathers every known node's result for a task.")
                print(f"[Node {port}]: status: shows this node's id, port, and known peer count.")
                print(f"[Node {port}]: show <entry>: shows the content of a entry on the DHT, entry can be a regex.")
                print(f"[Node {port}]: dump <entry> <target>: dumps the content of the entry into a target binary file.")
            elif command == "quit":
                break
            elif command == "run":
                if len(args) != 1:
                    print(f"[Node {port}]: [FAILLED] Try \"run <script>\"")
                    continue
                filename = args[0]
                if not filename:
                    continue
                path = Path(filename)
                if path.suffix.lower() != ".py":
                    print(f"[Node {port}] Invalid file. Only python files are accepted.")
                    continue

                try:
                    script = path.read_text(encoding="utf-8")
                except FileNotFoundError:
                    print(f"[Node {port}] Arquivo não encontrado: {filename}")
                    continue
                except OSError as exc:
                    print(f"[Node {port}] Não foi possível ler o arquivo: {exc}")
                    continue

                task_id = str(uuid.uuid4())
                processed_tasks.add(task_id)
                task_payload = {"id": task_id, "filename": filename, "code": script}

                try:
                    await server.set("lotsonet:current-task", json.dumps(task_payload))
                    await asyncio.sleep(1.5)
                    result = await exec_code(script)
                    await server.set(f"lotsonet:result:{task_id}:{node_id}", serialize_value(result))
                    print(f"[Node {port}] Comando distribuído para a rede ({task_id}). Resultado local: {result!r}")
                except Exception as exc:
                    print(f"[Node {port}] Erro ao executar o comando: {exc}")
            elif command == "collect":
                if len(args) != 1:
                    print(f"[Node {port}]: [FAILLED] Try \"collect <task_id>\"")
                    continue
                task_id = args[0]
                await refresh_membership(server)
                member_ids = known_node_ids(server)
                results = {}
                for member_id in member_ids:
                    value = await server.get(f"lotsonet:result:{task_id}:{member_id}")
                    if value is not None:
                        results[member_id] = value
                if not results:
                    print(f"[Node {port}] No results found for task {task_id!r} among {len(member_ids)} known node(s).")
                    continue
                print(f"[Node {port}] Collected {len(results)}/{len(member_ids)} result(s) for task {task_id}:")
                for member_id, value in results.items():
                    print(f"  {member_id}: {format_dht_value(value)}")
                await server.set(f"lotsonet:aggregate:{task_id}", json.dumps(results))
            elif command == "status":
                if len(args) != 0:
                    print(f"[Node {port}]: [FAILLED] Try \"status\"")
                    continue
                peer_ids = known_node_ids(server) - {node_id}
                print(f"[Node {port}] node_id: {node_id}")
                print(f"[Node {port}] listening on port: {port}")
                print(f"[Node {port}] known peers: {len(peer_ids)}")
                print(f"[Node {port}] ksize: {server.ksize}, alpha: {server.alpha}")
            elif command == "show":
                if len(args) != 1:
                    print(f"[Node {port}]: [FAILLED] Try \"show <entry>\"")
                    continue
                try:
                    entries, exact = await show_dht_entry(server, args[0])
                except re.error as exc:
                    print(f"[Node {port}] Invalid regex: {exc}")
                    continue
                except Exception as exc:
                    print(f"[Node {port}] Could not read DHT entry: {exc}")
                    continue
                if not entries:
                    print(f"[Node {port}] No DHT entry found for {args[0]!r}.")
                    continue
                if not exact:
                    print(f"[Node {port}] Exact key not found; showing local regex matches.")
                for key, value in entries:
                    print(f"[Node {port}] {key}:")
                    print(format_dht_value(value))
            elif command == "dump":
                if len(args) != 2:
                    print(f"[Node {port}]: [FAILLED] Try \"dump <entry> <target>\"")
                    continue
                try:
                    byte_count = await dump_dht_entry(server, args[0], args[1])
                except OSError as exc:
                    print(f"[Node {port}] Could not write dump target: {exc}")
                    continue
                except Exception as exc:
                    print(f"[Node {port}] Could not dump DHT entry: {exc}")
                    continue
                if byte_count is None:
                    print(f"[Node {port}] No DHT entry found for {args[0]!r}.")
                    continue
                print(f"[Node {port}] Dumped {byte_count} bytes to {args[1]}.")
            else:
                print(f"[Node {port}]: [FAILLED] Try \"help\"")
                continue
    except asyncio.CancelledError:
        pass
    finally:
        listener_task.cancel()
        with suppress(asyncio.CancelledError):
            await listener_task
        discovery_transport.close()
        server.stop()


if __name__ == "__main__":
    try:
        asyncio.run(init_node(port))
    except KeyboardInterrupt:
        print(f"\nNode on {port} disconnected.")
