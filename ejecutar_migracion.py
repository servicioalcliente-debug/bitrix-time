"""
Script para mover masivamente todas las tareas completadas de 'Nuevo' a 'Terminado'
en el proyecto 'Gestión Infraestructura' (ID: 77) de Bitrix24.
Usa la API Batch de Bitrix24 para máxima velocidad y eficiencia.
"""

import sys
import time
import requests
import urllib3

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

WEBHOOK_URL = "https://atcalsas.bitrix24.es/rest/16923/fakqy2ypjnd4tw2w/"
GROUP_ID = 77
STAGE_TERMINADO_ID = 495
STAGES_ORIGEN = [0, 491]  # 0 y 491 corresponden a la columna 'Nuevo'
STATUS_COMPLETADAS = [4, 5]  # 4 = Por revisar / completada, 5 = Completada

def api_call(method, params=None):
    url = f"{WEBHOOK_URL}{method}.json"
    res = requests.post(url, json=params or {}, verify=False)
    res.raise_for_status()
    return res.json()

def obtener_tareas_completadas_en_nuevo():
    print("🔍 Obteniendo lista de tareas en 'Nuevo' con estado 'Completada'...")
    tareas = []
    start = 0

    while True:
        data = api_call("tasks.task.list", {
            "filter": {
                "GROUP_ID": GROUP_ID,
                "STAGE_ID": STAGES_ORIGEN,
                "STATUS": STATUS_COMPLETADAS
            },
            "select": ["ID", "TITLE", "STATUS", "STAGE_ID"],
            "start": start
        })

        lote = data.get("result", {}).get("tasks", [])
        if not lote:
            break

        tareas.extend(lote)
        total = data.get("total", len(tareas))
        print(f"  → Descargadas {len(tareas)} de {total} tareas...")

        if len(tareas) >= total or len(lote) < 50:
            break
        start += 50
        time.sleep(0.2)

    return tareas

def mover_en_lotes(tareas):
    total = len(tareas)
    print(f"\n🚀 Iniciando traslado de {total} tareas a la etapa 'Terminado'...")

    lote_tamano = 50
    movidas = 0
    fallos = 0

    for i in range(0, total, lote_tamano):
        bloque = tareas[i:i + lote_tamano]
        cmd = {}
        for t in bloque:
            tid = t["id"]
            cmd[f"m_{tid}"] = f"task.stages.movetask?id={tid}&stageId={STAGE_TERMINADO_ID}"

        try:
            res = api_call("batch", {"halt": 0, "cmd": cmd})
            respuestas = res.get("result", {}).get("result", {})

            for t in bloque:
                tid = t["id"]
                titulo = t.get("title", "")[:45]
                resultado = respuestas.get(f"m_{tid}")
                if resultado is True:
                    movidas += 1
                else:
                    fallos += 1
                    print(f"  ⚠️ Error en tarea #{tid} ({titulo}): {resultado}")

            porcentaje = (min(i + lote_tamano, total) / total) * 100
            print(f"  Progreso: {min(i + lote_tamano, total)}/{total} ({porcentaje:.1f}%) | Exitosas: {movidas}")

        except Exception as e:
            print(f"  ❌ Error enviando lote: {e}")
            fallos += len(bloque)

        time.sleep(0.5)

    print("\n" + "=" * 50)
    print("  RESULTADO FINAL")
    print("=" * 50)
    print(f"  ✅ Movidas exitosamente : {movidas}")
    print(f"  ❌ Fallos                : {fallos}")
    print(f"  📦 Total procesadas      : {total}")
    print("=" * 50)

if __name__ == "__main__":
    tareas = obtener_tareas_completadas_en_nuevo()
    if tareas:
        mover_en_lotes(tareas)
    else:
        print("✅ No hay tareas pendientes por mover en la etapa 'Nuevo'.")
