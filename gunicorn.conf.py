# Configuración de Gunicorn para despliegue en Render
timeout = 180
workers = 2
threads = 4
bind = "0.0.0.0:10000"
