import os

# Configuración de Gunicorn para despliegue en Render
port = os.environ.get("PORT", "10000")
bind = f"0.0.0.0:{port}"
timeout = 180
workers = 2
threads = 4
