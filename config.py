import os

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# URL del Webhook de Bitrix24
BITRIX_WEBHOOK_URL = os.environ.get(
    "BITRIX_WEBHOOK_URL", 
    "https://atcalsas.bitrix24.es/rest/16923/fakqy2ypjnd4tw2w/"
)

# Dominio base de Bitrix para enlaces directos
BITRIX_DOMAIN = os.environ.get("BITRIX_DOMAIN", "https://atcalsas.bitrix24.es")

# Puerto del servidor local
PORT = int(os.environ.get("PORT", 5000))
