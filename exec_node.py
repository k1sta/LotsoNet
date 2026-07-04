import asyncio
import json
import socket
import sys
import uuid
from contextlib import suppress
from pathlib import Path

from kademlia.network import Server


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
    try:
        host = socket.gethostbyname(socket.gethostname())
        if host.startswith("127."):
            return f"127.0.0.1:{port}"
        return f"{host}:{port}"
    except OSError:
        return f"127.0.0.1:{port}"


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
    node_id = get_node_address(port)
    processed_tasks: set = set()

    listener_task = asyncio.create_task(listen_for_tasks(server, port, processed_tasks, node_id))
    print(f"[Node {port}] Pronto. Digite o nome de um arquivo .txt ou .py para distribuir pela rede (ou 'quit' para sair).")

    try:
        while True:
            try:
                filename = await asyncio.to_thread(input, f"[Node {port}] Arquivo> ")
            except EOFError:
                break

            filename = filename.strip()
            if not filename or filename.lower() in {"quit", "exit"}:
                break

            path = Path(filename)
            if path.suffix.lower() not in {".txt", ".py"}:
                print(f"[Node {port}] Arquivo inválido. Use um .txt ou .py.")
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
    except asyncio.CancelledError:
        pass
    finally:
        listener_task.cancel()
        with suppress(asyncio.CancelledError):
            await listener_task
        server.stop()


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python exec_node.py <port>")
        sys.exit(1)

    port = int(sys.argv[1])
    try:
        asyncio.run(init_node(port))
    except KeyboardInterrupt:
        print(f"\nNode on {port} disconnected.")