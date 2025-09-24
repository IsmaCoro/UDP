let ws = null;
let username = null;
let reconnectAttempts = 0;
const maxReconnectAttempts = 5;

const messages = document.getElementById("messages");
const input = document.getElementById("msg-input");
const btn = document.getElementById("send-btn");
const usersList = document.getElementById("users-list");
const status = document.getElementById("connection-status");

// Función para conectar WebSocket
function connectWebSocket() {
    status.textContent = "Conectando...";
    status.style.color = "orange";
    
    
    ws = new WebSocket("ws://192.168.43.203:8765");
    
    // Eventos WebSocket
    ws.onopen = () => {
        status.textContent = "✅ Conectado";
        status.style.color = "green";
        reconnectAttempts = 0;
        
        // Si ya tenemos nombre de usuario, enviarlo al reconectar
        if (username) {
            ws.send("/name " + username);
        }
    };
    
    ws.onclose = () => {
        status.textContent = "❌ Desconectado";
        status.style.color = "red";
        
        // Intentar reconectar
        if (reconnectAttempts < maxReconnectAttempts) {
            reconnectAttempts++;
            status.textContent = `Reconectando (${reconnectAttempts}/${maxReconnectAttempts})...`;
            setTimeout(connectWebSocket, 3000);
        } else {
            status.textContent = "No se pudo reconectar. Recarga la página.";
        }
    };
    
    ws.onerror = () => {
        status.textContent = "Error de conexión";
        status.style.color = "red";
    };
    
    // Recibir mensajes
    ws.onmessage = (event) => {
        const msg = event.data;
        if (msg.startsWith("USERS:")) {
            const users = msg.slice(6).split(",");
            usersList.innerHTML = users.map(u => `<span>${u}</span>`).join(", ");
            return;
        }
        const div = document.createElement("div");
        div.textContent = msg;
        
        // Aplicar estilos según tipo de mensaje
        if (msg.startsWith("SYSTEM:")) {
            div.className = "system-message";
        } else if (msg.startsWith("[Privado")) {
            div.className = "private-message";
        }
        
        messages.appendChild(div);
        messages.scrollTop = messages.scrollHeight;
    };
}

// Iniciar conexión
connectWebSocket();

// Login
document.getElementById("login-btn").onclick = () => {
    username = document.getElementById("username-input").value.trim();
    if (!username) return alert("Nombre inválido");
    
    if (ws && ws.readyState === WebSocket.OPEN) {
        ws.send("/name " + username);
        document.getElementById("login-container").style.display = "none";
        document.getElementById("chat-container").style.display = "block";
        document.getElementById("current-user").textContent = username;
        
        // Actualizar el nombre de usuario en el cliente UDP
        // Esto se comunica con el cliente Python
        try {
            // Almacenar el nombre de usuario en localStorage para que el cliente UDP pueda acceder a él
            localStorage.setItem('chatUsername', username);
            
            // Crear un evento personalizado para notificar al cliente Python
            const event = new CustomEvent('usernameSet', { detail: username });
            window.dispatchEvent(event);
            
            console.log("Nombre de usuario establecido: " + username);
        } catch (e) {
            console.error("Error al guardar nombre de usuario: " + e);
        }
    } else {
        alert("No hay conexión con el servidor. Intenta más tarde.");
    }
};

// Enviar mensaje
btn.onclick = () => {
    if (input.value && ws && ws.readyState === WebSocket.OPEN) {
        ws.send(input.value);
        input.value = "";
    }
};

input.addEventListener("keyup", e => { if (e.key === "Enter") btn.click(); });