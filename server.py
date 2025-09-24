import socket
import threading
import asyncio
import websockets
from queue import Queue
import time

# ------------------- UDP -------------------
UDP_HOST = "0.0.0.0"
UDP_PORT = 10000
udp_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
udp_sock.bind((UDP_HOST, UDP_PORT))

clients_udp = {}
clients_last_active = {}  # Registro de última actividad
clients_udp_lock = threading.Lock()

# ---------------- WebSocket ----------------
WS_PORT = 8765
ws_clients = set()
ws_clients_lock = threading.Lock()

# Diccionario para asociar websockets con nombres de usuario
ws_usernames = {}
ws_usernames_lock = threading.Lock()

message_queue = Queue()

# ---------------- Funciones ----------------
def get_username_by_addr(addr):
    with clients_udp_lock:
        for username, client_addr in clients_udp.items():
            if client_addr == addr:
                return username
    return None

async def broadcast_ws(message):
    disconnected = set()
    with ws_clients_lock:
        for ws in ws_clients:
            try:
                await ws.send(message)
            except:
                disconnected.add(ws)
        for ws in disconnected:
            ws_clients.remove(ws)

def broadcast_udp(message):
    data = message.encode("utf-8")
    disconnected_users = []
    
    with clients_udp_lock:
        for username, addr in clients_udp.items():
            try:
                udp_sock.sendto(data, addr)
            except Exception as e:
                print(f"Error enviando a {username}: {e}")
                disconnected_users.append(username)
    
    # Eliminar usuarios desconectados
    if disconnected_users:
        remove_disconnected_users(disconnected_users)

async def process_message(message):
    """Envia mensaje a UDP y WebSocket"""
    broadcast_udp(message)
    await broadcast_ws(message)

def remove_disconnected_users(usernames):
    """Elimina usuarios desconectados y notifica"""
    with clients_udp_lock:
        for username in usernames:
            if username in clients_udp:
                del clients_udp[username]
                if username in clients_last_active:
                    del clients_last_active[username]
                asyncio.create_task(process_message(f"SYSTEM: {username} se ha desconectado"))

def check_inactive_clients(loop):
    """Verifica clientes inactivos periódicamente"""
    while True:
        time.sleep(30)  # Verificar cada 30 segundos
        current_time = time.time()
        inactive_users = []
        
        with clients_udp_lock:
            for username, last_active in list(clients_last_active.items()):
                # Si no hay actividad en 2 minutos, considerar desconectado
                if current_time - last_active > 120:  
                    inactive_users.append(username)
        
        if inactive_users:
            remove_disconnected_users(inactive_users)
            
            # Actualizar lista de usuarios
            with clients_udp_lock, ws_usernames_lock:
                user_list = "USERS:" + ",".join(list(clients_udp.keys()) + list(ws_usernames.values()))
                asyncio.run_coroutine_threadsafe(broadcast_ws(user_list), loop)

# ---------------- UDP Listener ----------------
def udp_listener(loop):
    while True:
        try:
            data, addr = udp_sock.recvfrom(4096)
            msg = data.decode("utf-8")
            if not msg or len(msg) > 1000:
                continue

            # Actualizar tiempo de actividad
            username = get_username_by_addr(addr)
            if username:
                with clients_udp_lock:
                    clients_last_active[username] = time.time()

            if msg.startswith("USER:"):
                username = msg.split(":",1)[1].strip()
                if username and ':' not in username and len(username) <= 20:
                    with clients_udp_lock:
                        clients_udp[username] = addr
                        clients_last_active[username] = time.time()
                    asyncio.run_coroutine_threadsafe(process_message(f"SYSTEM: {username} se ha conectado"), loop)
                    
                    # Enviar lista de usuarios conectados
                    user_list = "USERS:" + ",".join(clients_udp.keys())
                    udp_sock.sendto(user_list.encode("utf-8"), addr)

            elif msg.startswith("@"):
                parts = msg.split(" ", 1)
                target_user = parts[0][1:]
                text = parts[1] if len(parts)>1 else ""
                if target_user and text:
                    with clients_udp_lock:
                        if target_user in clients_udp:
                            sender = get_username_by_addr(addr) or "Anónimo"
                            private_msg = f"[Privado de {sender}] {text}"
                            udp_sock.sendto(private_msg.encode("utf-8"), clients_udp[target_user])
                            # Confirmar al remitente
                            confirm_msg = f"[Privado para {target_user}] {text}"
                            udp_sock.sendto(confirm_msg.encode("utf-8"), addr)
            elif msg.lower() == "/users":
                # Comando para solicitar lista de usuarios
                with clients_udp_lock:
                    user_list = "USERS:" + ",".join(clients_udp.keys())
                    udp_sock.sendto(user_list.encode("utf-8"), addr)
            else:
                username = get_username_by_addr(addr)
                if username:
                    asyncio.run_coroutine_threadsafe(process_message(f"{username}: {msg}"), loop)

        except Exception as e:
            print(f"Error UDP: {e}")

# ---------------- WebSocket Handler ----------------
async def ws_handler(websocket):
    with ws_clients_lock:
        ws_clients.add(websocket)
    try:
        await websocket.send("SYSTEM: Conectado al chat WebSocket")
        
        # Enviar lista inicial de usuarios (UDP + Web)
        with clients_udp_lock, ws_usernames_lock:
            user_list = "USERS:" + ",".join(list(clients_udp.keys()) + list(ws_usernames.values()))
            await websocket.send(user_list)
            
        async for msg in websocket:
            if msg and len(msg) <= 1000:
                if msg.startswith("/name "):
                    # Manejo de registro de nombre desde web
                    web_username = msg[6:].strip()
                    if web_username and ':' not in web_username and len(web_username) <= 20:
                        with ws_usernames_lock:
                            ws_usernames[websocket] = web_username  # 🔹 Guardar username del cliente web

                        await process_message(f"SYSTEM: {web_username} se ha conectado desde web")

                        # Actualizar lista de usuarios (UDP + Web)
                        with clients_udp_lock, ws_usernames_lock:
                            user_list = "USERS:" + ",".join(list(clients_udp.keys()) + list(ws_usernames.values()))
                            await broadcast_ws(user_list)
                else:
                    # 🔹 Usar el nombre guardado o "Web" si no está definido
                    sender = ws_usernames.get(websocket, "Web")
                    await process_message(f"[{sender}]: {msg}")
    finally:
        with ws_clients_lock:
            ws_clients.discard(websocket)
        with ws_usernames_lock:
            if websocket in ws_usernames:
                username = ws_usernames.pop(websocket)
                asyncio.create_task(process_message(f"SYSTEM: {username} se ha desconectado"))

        # 🔹 Al desconectarse, actualizar la lista de usuarios para los demás
        with clients_udp_lock, ws_usernames_lock:
            user_list = "USERS:" + ",".join(list(clients_udp.keys()) + list(ws_usernames.values()))
            asyncio.create_task(broadcast_ws(user_list))


# ---------------- Main ----------------
async def main():
    # Iniciar UDP en hilo
    loop = asyncio.get_running_loop()
    threading.Thread(target=udp_listener, args=(loop,), daemon=True).start()
    
    # Iniciar verificador de clientes inactivos
    threading.Thread(target=check_inactive_clients, args=(loop,), daemon=True).start()
    
    print(f"✅ UDP escuchando en {UDP_HOST}:{UDP_PORT}")

    # Iniciar WebSocket
    server = await websockets.serve(ws_handler, "0.0.0.0", WS_PORT)
    print(f"✅ WebSocket escuchando en ws://0.0.0.0:{WS_PORT}")

    await server.wait_closed()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n🛑 Servidor detenido")
