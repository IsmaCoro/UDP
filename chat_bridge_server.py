import asyncio
import websockets
import socket
import struct
import threading
import sys

# --- Configuración Multicast ---
MCAST_GRP = '224.1.1.1'
MCAST_PORT = 5007

# --- Configuración WebSocket ---
WS_HOST = '0.0.0.0'
WS_PORT = 8080

# --- Almacenamiento de Clientes ---
# Mantiene un registro de todos los navegadores conectados
CONNECTED_CLIENTS = set()

# --- Parte 1: Lógica del WebSocket ---

async def broadcast_to_websockets(message):
    """Envía un mensaje a TODOS los clientes WebSocket conectados."""
    if CONNECTED_CLIENTS:
        # Crea una tarea para enviar el mensaje a cada cliente
        await asyncio.gather(*[client.send(message) for client in CONNECTED_CLIENTS])

async def websocket_handler(websocket):
    """Maneja la conexión de un solo cliente WebSocket."""
    global CONNECTED_CLIENTS
    
    # Registrar al nuevo cliente
    CONNECTED_CLIENTS.add(websocket)
    print(f"Nuevo cliente web conectado. Total: {len(CONNECTED_CLIENTS)}")
    
    try:
        # --- Bucle de escucha del WebSocket ---
        # Escucha mensajes VENIDOS DESDE el navegador
        async for message in websocket:
            print(f"[Web -> Multicast]: {message}")
            
            # Reenviar el mensaje al grupo multicast
            # (El socket de envío se crea aquí para ser simple, 
            # pero podría optimizarse)
            send_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            ttl = struct.pack('b', 1) # TTL = 1 (solo red local)
            send_sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, ttl)
            try:
                send_sock.sendto(message.encode('utf-8'), (MCAST_GRP, MCAST_PORT))
            except socket.error as e:
                print(f"Error al enviar a multicast: {e}")
            finally:
                send_sock.close()

    except websockets.exceptions.ConnectionClosed:
        print("Cliente web desconectado.")
    finally:
        # Eliminar al cliente al desconectarse
        CONNECTED_CLIENTS.remove(websocket)
        print(f"Cliente web desconectado. Restantes: {len(CONNECTED_CLIENTS)}")


# --- Parte 2: Lógica del Multicast (en un Hilo separado) ---

def multicast_listener():
    """Escucha mensajes de Multicast y los envía a los WebSockets."""
    
    # Obtener el loop de asyncio del hilo principal
    # Esto es crucial para la comunicación entre hilos
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    # Configurar el socket de recepción de Multicast
    recv_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    recv_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    recv_sock.bind(('', MCAST_PORT))
    
    group = socket.inet_aton(MCAST_GRP)
    mreq = struct.pack('4sL', group, socket.INADDR_ANY)
    recv_sock.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq)
    
    print("Escuchando mensajes multicast...")

    # --- Bucle de escucha de Multicast ---
    while True:
        try:
            # Espera (bloquea) hasta recibir un mensaje multicast
            data, addr = recv_sock.recvfrom(1024)
            message = data.decode('utf-8')
            print(f"[Multicast -> Web]: {message}")
            
            # --- El "Puente" ---
            # Ahora, envía este mensaje a todos los clientes WebSocket.
            # Usamos 'run_coroutine_threadsafe' porque estamos en un hilo
            # separado y necesitamos hablar con el loop de asyncio de forma segura.
            asyncio.run_coroutine_threadsafe(
                broadcast_to_websockets(message),
                main_loop  # main_loop se define en __main__
            )
            
        except socket.error as e:
            print(f"Error de socket multicast: {e}")
        except UnicodeDecodeError:
            print("Error: Paquete multicast malformado recibido.")


# --- Parte 3: Iniciar todo ---

async def main_async():
    """Inicia el servidor de WebSockets."""
    print(f"Iniciando servidor WebSocket en ws://{WS_HOST}:{WS_PORT}")
    start_server = websockets.serve(websocket_handler, WS_HOST, WS_PORT)
    await start_server

if __name__ == "__main__":
    try:
        # Obtenemos el loop de asyncio principal
        main_loop = asyncio.get_event_loop()
        asyncio.set_event_loop(main_loop)
        
        # 1. Iniciar el servidor WebSocket en el loop principal
        main_loop.run_until_complete(main_async())
        
        # 2. Iniciar el listener de Multicast en un hilo separado
        listener_thread = threading.Thread(target=multicast_listener, daemon=True)
        listener_thread.start()
        
        # 3. Correr el loop de asyncio para siempre
        main_loop.run_forever()
        
    except KeyboardInterrupt:
        print("\nCerrando servidor...")
    except OSError as e:
        if e.errno == 10048: # Error "Address already in use"
             print(f"ERROR: El puerto {WS_PORT} ya está en uso.")
             print("Asegúrate de no tener otro servidor de chat corriendo.")
        else:
             print(f"Error del sistema: {e}")
    finally:
        sys.exit(0)