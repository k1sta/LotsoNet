import asyncio
import sys
from kademlia.network import Server

async def iniciar_no(porta_local):
    server = Server()
    await server.listen(porta_local, interface="127.0.0.1")
    
    conectado = await server.bootstrap([("127.0.0.1", 8468)])
    if not conectado:
        print(f"[Erro] Falha ao conectar ao bootstrap na porta {porta_local}")
        server.stop()
        return

    chave = f"status-{porta_local}"
    await server.set(chave, "online")
    
    valor = await server.get(chave)
    print(f"[Nó {porta_local}] Conectado. Teste DHT: '{chave}' -> '{valor}'")

    try:
        await asyncio.Event().wait()
    except asyncio.CancelledError:
        pass
    finally:
        server.stop()

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Uso: python node.py <porta>")
        sys.exit(1)
        
    porta = int(sys.argv[1])
    try:
        asyncio.run(iniciar_no(porta))
    except KeyboardInterrupt:
        print(f"\nNó da porta {porta} encerrado.")