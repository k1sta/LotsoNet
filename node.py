import asyncio
import json
import os
import sys
import uuid
from contextlib import suppress
from pathlib import Path

from kademlia.network import Server

import discovery
from netutil import get_local_ip

LISTEN_INTERFACE = os.environ.get("LOTSONET_INTERFACE", "0.0.0.0")
BOOTSTRAP_HOST = os.environ.get("BOOTSTRAP_HOST")
BOOTSTRAP_PORT = int(os.environ.get("BOOTSTRAP_PORT", 8468))

# host  
port  = int(os.environ.get("LOTSONET_PORT", 8468))

async def exec_code(script: str):
    namespace = {"__name__": "__main__"}
    exec(compile(script, "<lotsonet_script>", "exec"), namespace, namespace)

    main_fn = namespace.get("main")
    if callable(main_fn):
        return main_fn()
    return None


def serialize_value(value):
    if isinstance(value, (int, float, bool, str, bytes)):
        return value
    try:
        return json.dumps(value)
    except (TypeError, ValueError):
        return str(value)


def get_node_address(port: int) -> str:
    host = get_local_ip(os.environ.get("LOTSONET_IFACE_NAME"))
    return f"{host}:{port}"


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

            try:
                result = await exec_code(code)
                await server.set(f"{node_id}-response", serialize_value(result))
                print(f"[Node {port}] Resultado salvo em {node_id}-response: {result!r}")
            except Exception as exc:
                await server.set(f"{node_id}-response", serialize_value({"error": str(exc)}))
                print(f"[Node {port}] Erro ao executar comando distribuído: {exc}")
        except Exception as exc:
            print(f"[Node {port}] Falha ao ouvir por comandos: {exc}")
        await asyncio.sleep(1)


async def init_node(port: int):
    server = Server()
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

    node_id = get_node_address(port)
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
                print(f"[Node {port}]: show <entry>: shows the content of a entry on the DHT, entry can be a regex.")
                print(f"[Node {port}]: dump <entry> <target>: dumps the content of the entry into a target binary file.")
            elif command == "run":
                if len(args) != 1:
                    print(f"[Node {port}]: [FAILLED] Try \"run <script>\"")
                    break    
                filename = args[0]
                if not filename:
                    break
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
                    response_value = result if isinstance(result, (int, float, bool, str, bytes)) else str(result)
                    await server.set(f"{node_id}-response", response_value)
                    print(f"[Node {port}] Comando distribuído para a rede. Resultado local: {result!r}")
                except Exception as exc:
                    print(f"[Node {port}] Erro ao executar o comando: {exc}")
                # continue
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