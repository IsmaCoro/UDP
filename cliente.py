import socket
import threading
import webbrowser
import os
import time

#IP DEL DISPOSITIVO QUE SE UTILIZA COMO SERVIDOR
#EN ESTE CASO LAPTOP DE ISMAEL
UDP_SERVER = ("192.168.43.203", 10000)

#NOMBRE DE USUARIO PREDETERMINADO PARA LA CONSOLA
username = "CMD"

sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.settimeout(1.0)

#ABRE EL LA WEB
def open_browser():
    html_file = os.path.join('web', 'index.html')
    if os.path.exists(html_file):
        webbrowser.open(f'file:///{os.path.abspath(html_file)}')
        print(f"✅ Navegador abierto con {html_file}")
    else:
        print("⚠️ No se encontró index.html. Abre manualmente el archivo.")

#ENVIA EL REGISTRO DEL USUARIO
def send_user_registration():
    global username
    try:
        sock.sendto(f"USER:{username}".encode("utf-8"), UDP_SERVER)
        return True
    except Exception as e:
        print(f"Error de conexión: {e}")
        return False

#IENVIA EL HEARTBEAT PARA MANTENER Y VER EL ESTADO DE LA CONEXIÓN
def send_heartbeat():
    global username
    while True:
        try:
            sock.sendto(f"USER:{username}".encode("utf-8"), UDP_SERVER)
            time.sleep(60)
        except Exception as e:
            print(f"Error en heartbeat: {e}")
            time.sleep(5)

def listen_udp():
    users_list = []
    reconnect_attempts = 0
    max_reconnect_attempts = 5
    
    while True:
        try:
            data, addr = sock.recvfrom(4096)
            message = data.decode("utf-8")
            reconnect_attempts = 0
            
            #LISTA DE USUARIOS
            if message.startswith("USERS:"):
                users = message[6:].split(",")
                if users != users_list:
                    users_list = users
                    print(f"\r👥 Usuarios conectados: {', '.join(users)}\n> ", end="", flush=True)
            else:
                print(f"\r{message}\n> ", end="", flush=True)
                
        except socket.timeout:
            continue
        except ConnectionResetError:
            print("\r⚠️ Conexión reiniciada por el servidor. Reintentando...")
            reconnect_attempts += 1
        except Exception as e:
            print(f"\r⚠️ Error UDP: {e}")
            reconnect_attempts += 1
            
        #RECONEXIÓN EN CASO DE ERROR.
        if reconnect_attempts > 0:
            if reconnect_attempts <= max_reconnect_attempts:
                print(f"\rIntentando reconectar ({reconnect_attempts}/{max_reconnect_attempts})...")
                time.sleep(2)
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
    
    #REGISTRO DE USUARIOS
    if send_user_registration():
        print(f"✅ Registrado en el servidor como '{username}'")
    else:
        print("❌ No se pudo conectar al servidor")
        return
    
    #ABRE WEB
    threading.Thread(target=open_browser, daemon=True).start()

    #INICIA EL HILO DE UDP
    threading.Thread(target=listen_udp, daemon=True).start()
    
    #INICIA EL HILI DE HEARTBREAT PARA CORROBORAR EL ESTADO
    threading.Thread(target=send_heartbeat, daemon=True).start()

    #CICLO DE MENSAJES
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
