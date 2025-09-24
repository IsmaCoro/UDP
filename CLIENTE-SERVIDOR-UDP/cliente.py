import socket
import threading
import webbrowser
import os
import time

# Cambia localhost por la IP de la máquina donde se ejecuta el servidor
# Por ejemplo: ("192.168.1.5", 10000)
UDP_SERVER = ("192.168.43.203", 10000)

# Establecer un nombre de usuario predeterminado para la consola
username = "CMD"

sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.settimeout(1.0)  # Timeout para recepción

def open_browser():
    """Abrir la web del chat automáticamente"""
    html_file = os.path.join('web', 'index.html')
    if os.path.exists(html_file):
        webbrowser.open(f'file:///{os.path.abspath(html_file)}')
        print(f"✅ Navegador abierto con {html_file}")
    else:
        print("⚠️ No se encontró index.html. Abre manualmente el archivo.")

def send_user_registration():
    """Envía registro de usuario"""
    global username
    try:
        sock.sendto(f"USER:{username}".encode("utf-8"), UDP_SERVER)
        return True
    except Exception as e:
        print(f"Error de conexión: {e}")
        return False

def send_heartbeat():
    """Envía señales periódicas para mantener la conexión activa"""
    global username
    while True:
        try:
            sock.sendto(f"USER:{username}".encode("utf-8"), UDP_SERVER)
            time.sleep(60)
        except Exception as e:
            print(f"Error en heartbeat: {e}")
            time.sleep(5)  # Esperar antes de reintentar

def listen_udp():
    users_list = []
    reconnect_attempts = 0
    max_reconnect_attempts = 5
    
    while True:
        try:
            data, addr = sock.recvfrom(4096)
            message = data.decode("utf-8")
            
            # Reiniciar contador de reconexión al recibir mensajes
            reconnect_attempts = 0
            
            # Procesar lista de usuarios
            if message.startswith("USERS:"):
                users = message[6:].split(",")
                if users != users_list:
                    users_list = users
                    print(f"\r👥 Usuarios conectados: {', '.join(users)}\n> ", end="", flush=True)
            else:
                print(f"\r{message}\n> ", end="", flush=True)
                
        except socket.timeout:
            # Timeout normal, continuar
            continue
        except ConnectionResetError:
            print("\r⚠️ Conexión reiniciada por el servidor. Reintentando...")
            reconnect_attempts += 1
        except Exception as e:
            print(f"\r⚠️ Error UDP: {e}")
            reconnect_attempts += 1
            
        # Intentar reconectar si hay errores
        if reconnect_attempts > 0:
            if reconnect_attempts <= max_reconnect_attempts:
                print(f"\rIntentando reconectar ({reconnect_attempts}/{max_reconnect_attempts})...")
                time.sleep(2)  # Esperar antes de reintentar
                if send_user_registration():
                    print("\r✅ Reconectado al servidor")
                    reconnect_attempts = 0
            else:
                print("\r❌ No se pudo reconectar después de varios intentos. Saliendo...")
                break

def main():
    print("Iniciando cliente de chat...")
    print(f"Conectado como: {username} (predeterminado)")
    print("Abriendo interfaz web...")
    
    # Registrar el usuario predeterminado
    if send_user_registration():
        print(f"✅ Registrado en el servidor como '{username}'")
    else:
        print("❌ No se pudo conectar al servidor")
        return
    
    # Abrir web
    threading.Thread(target=open_browser, daemon=True).start()

    # Iniciar escucha UDP
    threading.Thread(target=listen_udp, daemon=True).start()
    
    # Iniciar heartbeat
    threading.Thread(target=send_heartbeat, daemon=True).start()

    # Ciclo de envío de mensajes
    try:
        while True:
            msg = input("> ").strip()
            if not msg:
                continue
            if msg.lower() == "/quit":
                print("Saliendo...")
                break
                
            try:
                sock.sendto(msg.encode("utf-8"), UDP_SERVER)
            except Exception as e:
                print(f"Error al enviar mensaje: {e}")
    finally:
        sock.close()

if __name__ == "__main__":
    main()
