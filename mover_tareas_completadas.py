"""
Script para mover tareas "Completadas" de la etapa "Nuevo"
a la etapa "Terminado" en el proyecto Gestión Infraestructura - Bitrix24

Autor: Antigravity Assistant
Fecha: 2026-10-19
"""

import requests
import time

# ─────────────────────────────────────────────
# CONFIGURACIÓN
# ─────────────────────────────────────────────
WEBHOOK_URL = "https://atcalsas.bitrix24.es/rest/16923/fakqy2ypjnd4tw2w/"

# Nombre del grupo/proyecto a buscar
NOMBRE_GRUPO = "Gestión Infraestructura"

# Statuses de "Completada" en Bitrix24
# 4 = Supuestamente completada | 5 = Completada
STATUSES_COMPLETADA = [4, 5]


# ─────────────────────────────────────────────
# FUNCIONES
# ─────────────────────────────────────────────

def api_call(method, params=None):
    """Llama a la API de Bitrix24"""
    url = f"{WEBHOOK_URL}{method}.json"
    response = requests.post(url, json=params or {})
    response.raise_for_status()
    return response.json()


def get_group_id(nombre):
    """Busca el ID del grupo por nombre"""
    print(f"🔍 Buscando grupo: '{nombre}'...")
    result = api_call("sonet_group.get", {"FILTER": {"NAME": nombre}})
    grupos = result.get("result", [])
    if not grupos:
        print(f"❌ No se encontró el grupo '{nombre}'")
        return None
    grupo = grupos[0]
    print(f"✅ Grupo encontrado: {grupo['NAME']} (ID: {grupo['ID']})")
    return int(grupo["ID"])


def get_stages(group_id):
    """Obtiene las etapas del proyecto"""
    print(f"📋 Obteniendo etapas del grupo {group_id}...")
    result = api_call("task.stages.get", {"entityId": group_id, "isAdmin": True})
    stages = result.get("result", {})
    # El resultado puede ser un dict con ID como key
    if isinstance(stages, dict):
        stages = list(stages.values())
    return stages


def find_stage_id(stages, nombre):
    """Encuentra el ID de una etapa por nombre (parcial, case-insensitive)"""
    nombre_lower = nombre.lower()
    for stage in stages:
        if nombre_lower in stage.get("TITLE", "").lower():
            print(f"  ✅ Etapa '{stage['TITLE']}' encontrada (ID: {stage['ID']})")
            return int(stage["ID"])
    return None


def get_tasks_in_stage(group_id, stage_id, statuses):
    """Obtiene todas las tareas en una etapa con ciertos estados"""
    print(f"\n📦 Buscando tareas en etapa ID={stage_id} con status {statuses}...")
    all_tasks = []
    start = 0

    while True:
        result = api_call("tasks.task.list", {
            "filter": {
                "GROUP_ID": group_id,
                "STAGE_ID": stage_id,
                "STATUS": statuses,
            },
            "select": ["ID", "TITLE", "STATUS", "STAGE_ID"],
            "start": start,
        })
        tasks = result.get("result", {}).get("tasks", [])
        all_tasks.extend(tasks)

        total = result.get("total", 0)
        print(f"  Obtenidas {len(all_tasks)} de {total} tareas...")

        if len(all_tasks) >= total or not tasks:
            break
        start += 50
        time.sleep(0.3)  # Evitar rate limiting

    return all_tasks


def move_task_to_stage(task_id, stage_id):
    """Mueve una tarea a otra etapa"""
    result = api_call("task.stages.movetask", {
        "id": task_id,
        "stageId": stage_id,
    })
    return result.get("result", False)


# ─────────────────────────────────────────────
# EJECUCIÓN PRINCIPAL
# ─────────────────────────────────────────────

def main():
    print("=" * 60)
    print("  BITRIX24 - Mover tareas Completadas → Terminado")
    print("=" * 60)

    # 1. Obtener ID del grupo
    group_id = get_group_id(NOMBRE_GRUPO)
    if not group_id:
        return

    # 2. Obtener etapas
    stages = get_stages(group_id)
    print(f"\n📋 Etapas encontradas:")
    for s in stages:
        print(f"  - [{s['ID']}] {s.get('TITLE', 'Sin nombre')}")

    # 3. Encontrar IDs de etapas
    print("\n🔎 Buscando etapas 'Nuevo' y 'Terminado'...")
    stage_nuevo_id = find_stage_id(stages, "nuevo")
    stage_terminado_id = find_stage_id(stages, "terminado")

    if not stage_nuevo_id or not stage_terminado_id:
        print("❌ No se encontraron las etapas. Verifica los nombres.")
        print(f"   'Nuevo' ID: {stage_nuevo_id}")
        print(f"   'Terminado' ID: {stage_terminado_id}")
        return

    # 4. Obtener tareas a mover
    tasks = get_tasks_in_stage(group_id, stage_nuevo_id, STATUSES_COMPLETADA)
    print(f"\n✅ Total de tareas a mover: {len(tasks)}")

    if not tasks:
        print("ℹ️  No hay tareas para mover.")
        return

    # 5. Confirmar antes de ejecutar
    print(f"\n⚠️  Se moverán {len(tasks)} tareas de 'Nuevo' → 'Terminado'")
    confirmacion = input("¿Continuar? (s/n): ").strip().lower()
    if confirmacion != "s":
        print("❌ Operación cancelada.")
        return

    # 6. Mover tareas
    print(f"\n🚀 Moviendo tareas...")
    exitosas = 0
    fallidas = 0

    for i, task in enumerate(tasks, 1):
        task_id = task["id"]
        title = task.get("title", "Sin título")[:50]
        try:
            success = move_task_to_stage(task_id, stage_terminado_id)
            if success:
                exitosas += 1
                print(f"  [{i}/{len(tasks)}] ✅ Tarea {task_id}: {title}")
            else:
                fallidas += 1
                print(f"  [{i}/{len(tasks)}] ⚠️  Tarea {task_id}: {title} - Sin respuesta")
        except Exception as e:
            fallidas += 1
            print(f"  [{i}/{len(tasks)}] ❌ Tarea {task_id}: {title} - Error: {e}")

        time.sleep(0.2)  # Evitar rate limiting de la API

    # 7. Resumen
    print("\n" + "=" * 60)
    print(f"  RESUMEN FINAL")
    print("=" * 60)
    print(f"  ✅ Exitosas : {exitosas}")
    print(f"  ❌ Fallidas : {fallidas}")
    print(f"  📦 Total   : {len(tasks)}")
    print("=" * 60)


if __name__ == "__main__":
    main()
