import os
import sys
import time
import json
import traceback
from datetime import datetime, timezone, timedelta
import requests
import urllib3
from flask import Flask, render_template, request, jsonify, send_file
from config import BITRIX_WEBHOOK_URL, BITRIX_DOMAIN, PORT
from export_excel import generar_excel_tiempos

# Asegurar codificación UTF-8 en Windows para evitar errores de print
try:
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
    if hasattr(sys.stderr, 'reconfigure'):
        sys.stderr.reconfigure(encoding='utf-8')
except Exception:
    pass

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

app = Flask(__name__)

CACHE_USERS = {}
CACHE_GROUPS = {}
CACHE_TASKS = {}
USERS_CACHE_FILE = os.path.join(os.path.dirname(__file__), "users_cache.json")

def load_cached_users():
    """Carga los colaboradores guardados en disco para respuesta instantánea (0ms)."""
    global CACHE_USERS
    if os.path.exists(USERS_CACHE_FILE):
        try:
            with open(USERS_CACHE_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, dict) and data:
                    CACHE_USERS.update(data)
                    print(f"[CACHE] Cargados {len(CACHE_USERS)} colaboradores desde archivo local.")
        except Exception as e:
            print(f"[CACHE ERROR] Al leer {USERS_CACHE_FILE}: {e}")

def save_cached_users():
    """Persiste los colaboradores descubiertos en disco para que no se pierdan al reiniciar."""
    global CACHE_USERS
    if CACHE_USERS:
        try:
            with open(USERS_CACHE_FILE, "w", encoding="utf-8") as f:
                json.dump(CACHE_USERS, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"[CACHE ERROR] Al guardar {USERS_CACHE_FILE}: {e}")

# Carga inicial inmediata al arrancar el servidor
load_cached_users()

def call_bitrix(method, params=None):
    """
    Realiza una llamada a la API REST de Bitrix24 de forma segura y rápida.
    """
    url = f"{BITRIX_WEBHOOK_URL}{method}.json"
    try:
        response = requests.post(url, json=params or {}, verify=False, timeout=30)
        try:
            res_json = response.json()
        except Exception:
            res_json = {"error": response.text, "status_code": response.status_code}
            
        if "error" in res_json:
            print(f"⚠️ Bitrix API ({method}) aviso/error: {res_json.get('error')} - {res_json.get('error_description')}")
        return res_json
    except Exception as e:
        print(f"❌ Error de conexión con Bitrix ({method}): {e}")
        return {"error": str(e)}

def parse_date_to_iso(date_str):
    """
    Normaliza cualquier formato de fecha de Bitrix a 'YYYY-MM-DD'.
    """
    if not date_str:
        return ""
    date_str = str(date_str).strip()
    if "T" in date_str:
        return date_str.split("T")[0]
    if " " in date_str:
        date_str = date_str.split(" ")[0]
    if "-" in date_str:
        parts = date_str.split("-")
        if len(parts) == 3 and len(parts[0]) == 4:
            return date_str
    if "." in date_str:
        parts = date_str.split(".")
        if len(parts) == 3:
            return f"{parts[2]}-{parts[1].zfill(2)}-{parts[0].zfill(2)}"
    if "/" in date_str:
        parts = date_str.split("/")
        if len(parts) == 3:
            if len(parts[2]) == 4:
                return f"{parts[2]}-{parts[1].zfill(2)}-{parts[0].zfill(2)}"
            elif len(parts[0]) == 4:
                return f"{parts[0]}-{parts[1].zfill(2)}-{parts[2].zfill(2)}"
    return date_str[:10]

COLOMBIA_TZ = timezone(timedelta(hours=-5))

def check_record_date_match(record, date_from, date_to, criterion="work_date"):
    """
    Determina con exactitud si un registro de tiempo corresponde al período [date_from, date_to].
    - criterion == 'work_date': Utiliza CREATED_DATE (fecha efectiva de la labor indicada por el trabajador).
    - criterion == 'submit_date': Utiliza DATE_START (fecha de guardado/envío al servidor Bitrix, idéntico a PureTaskReport).
    Ajusta por zona horaria de Bitrix (+03:00 Moscú a UTC-5 Colombia) si fue registrado en el límite del mes.
    """
    if criterion == "submit_date":
        raw = record.get("DATE_START") or record.get("CREATED_DATE")
    else:
        raw = record.get("CREATED_DATE") or record.get("DATE_START")

    if not raw or len(str(raw)) < 10:
        return False, None
        
    s_val = str(raw).strip()
    
    # 1. Fecha directa (YYYY-MM-DD)
    direct_date = s_val[:10]
    if date_from <= direct_date <= date_to:
        return True, direct_date
        
    # 2. Ajuste por huso horario (UTC+3 Moscú a Colombia UTC-5)
    try:
        dt = datetime.fromisoformat(s_val)
        col_date = dt.astimezone(COLOMBIA_TZ).strftime("%Y-%m-%d")
        if date_from <= col_date <= date_to:
            return True, col_date
    except Exception:
        pass
        
    return False, None

def extract_users_from_tasks():
    """
    Extrae todos los colaboradores a través de tareas y grupos de trabajo.
    Garantiza que siempre aparezcan todos los trabajadores aunque user.get no tenga permisos.
    """
    global CACHE_USERS
    found_users = {}
    start = 0

    print("🔄 Obteniendo colaboradores desde tareas (tasks.task.list)...")
    for _ in range(4):  # Revisa hasta 200 tareas
        # Bitrix tasks.task.list acepta order por CHANGED_DATE o sin order
        data = call_bitrix("tasks.task.list", {
            "select": ["ID", "TITLE", "RESPONSIBLE_ID", "CREATED_BY", "RESPONSIBLE", "CREATOR", "CHANGED_DATE"],
            "order": {"CHANGED_DATE": "DESC"},
            "start": start
        })

        if "error" in data:
            print(f"⚠️ Aviso en tasks.task.list con orden: {data.get('error')}. Intentando sin orden...")
            data = call_bitrix("tasks.task.list", {
                "select": ["ID", "TITLE", "RESPONSIBLE_ID", "CREATED_BY", "RESPONSIBLE", "CREATOR"],
                "start": start
            })
            if "error" in data:
                print(f"❌ Error definitivo en tasks.task.list: {data.get('error')}")
                break

        tasks_res = data.get("result", {})
        if isinstance(tasks_res, dict):
            tasks = tasks_res.get("tasks", [])
        elif isinstance(tasks_res, list):
            tasks = tasks_res
        else:
            tasks = []

        if not tasks:
            break

        for t in tasks:
            # Responsible (compatible con lowercase y UPPERCASE de Bitrix)
            resp = t.get("responsible") or t.get("RESPONSIBLE") or {}
            if isinstance(resp, dict):
                r_id = str(resp.get("id") or resp.get("ID") or "")
                r_name = resp.get("name") or resp.get("NAME") or ""
                if not r_name:
                    p = [resp.get("NAME", ""), resp.get("LAST_NAME", "")]
                    r_name = " ".join(filter(None, p)).strip()
                if r_id and r_id not in found_users:
                    found_users[r_id] = {
                        "id": r_id,
                        "name": r_name or f"Colaborador #{r_id}",
                        "position": "Colaborador",
                        "photo": resp.get("icon") or resp.get("PERSONAL_PHOTO") or None
                    }
            elif isinstance(resp, (str, int)) and str(resp):
                r_id = str(resp)
                if r_id not in found_users:
                    found_users[r_id] = {
                        "id": r_id,
                        "name": f"Colaborador #{r_id}",
                        "position": "Colaborador",
                        "photo": None
                    }

            # Creator (compatible con lowercase y UPPERCASE de Bitrix)
            creator = t.get("creator") or t.get("CREATOR") or {}
            if isinstance(creator, dict):
                c_id = str(creator.get("id") or creator.get("ID") or "")
                c_name = creator.get("name") or creator.get("NAME") or ""
                if not c_name:
                    p = [creator.get("NAME", ""), creator.get("LAST_NAME", "")]
                    c_name = " ".join(filter(None, p)).strip()
                if c_id and c_id not in found_users:
                    found_users[c_id] = {
                        "id": c_id,
                        "name": c_name or f"Colaborador #{c_id}",
                        "position": "Colaborador",
                        "photo": creator.get("icon") or creator.get("PERSONAL_PHOTO") or None
                    }
            elif isinstance(creator, (str, int)) and str(creator):
                c_id = str(creator)
                if c_id not in found_users:
                    found_users[c_id] = {
                        "id": c_id,
                        "name": f"Colaborador #{c_id}",
                        "position": "Colaborador",
                        "photo": None
                    }

        if "next" in data:
            start = data["next"]
            time.sleep(0.05)
        else:
            break

    # Grupos de trabajo activos (búsqueda ágil y segura)
    try:
        g_res = call_bitrix("sonet_group.get", {})
        groups = g_res.get("result", [])
        if isinstance(groups, list):
            for g in groups[:5]:
                gid = g.get("ID")
                if gid:
                    mem_res = call_bitrix("sonet_group.user.get", {"ID": gid})
                    mems = mem_res.get("result", [])
                    if isinstance(mems, list):
                        for m in mems:
                            mid = str(m.get("USER_ID", "") or m.get("ID", ""))
                            if mid and mid not in found_users:
                                m_name = f"{m.get('USER_NAME', '')} {m.get('USER_LAST_NAME', '')}".strip() or f"Colaborador #{mid}"
                                found_users[mid] = {
                                    "id": mid,
                                    "name": m_name,
                                    "position": "Colaborador",
                                    "photo": None
                                }
    except Exception as e:
        print(f"⚠️ Aviso al consultar grupos: {e}")

    for uid, udata in found_users.items():
        CACHE_USERS[uid] = udata

    # Guardar en archivo local para no tener que volver a consultar en cada reinicio
    save_cached_users()
    print(f"✅ Se cargaron exitosamente {len(CACHE_USERS)} colaboradores.")

def preload_users():
    """
    Carga todos los colaboradores activos en memoria para no hacer llamadas individuales.
    """
    global CACHE_USERS
    start = 0
    while True:
        data = call_bitrix("user.get", {"FILTER": {"ACTIVE": "Y"}, "start": start})
        if "error" in data:
            break
        batch = data.get("result", [])
        if not isinstance(batch, list) or not batch:
            break
        for u in batch:
            name_parts = [u.get("NAME", ""), u.get("LAST_NAME", "")]
            full_name = " ".join(filter(None, name_parts)).strip() or f"Usuario {u.get('ID')}"
            CACHE_USERS[str(u.get("ID"))] = {
                "id": str(u.get("ID")),
                "name": full_name,
                "position": u.get("WORK_POSITION", "Colaborador"),
                "photo": u.get("PERSONAL_PHOTO", None)
            }
        if "next" in data:
            start = data["next"]
            time.sleep(0.05)
        else:
            break

    if CACHE_USERS:
        save_cached_users()

    # Si user.get no devolvió o faltan permisos, extrae de tareas y grupos
    if len(CACHE_USERS) == 0:
        extract_users_from_tasks()

@app.route("/")
def index():
    return render_template("index.html", bitrix_domain=BITRIX_DOMAIN)

@app.route("/api/users", methods=["GET"])
def get_users():
    """
    Devuelve la lista ordenada de empleados activos desde la memoria caché rápida.
    """
    global CACHE_USERS
    if len(CACHE_USERS) == 0:
        preload_users()
    users = sorted(CACHE_USERS.values(), key=lambda x: x["name"])
    return jsonify({"success": True, "users": users, "total": len(users)})

@app.route("/api/times", methods=["POST"])
def get_times():
    """
    Descarga y rectifica tiempos con alta velocidad, soporte para nómina y caché en memoria.
    """
    global CACHE_USERS, CACHE_GROUPS, CACHE_TASKS
    try:
        start_time = time.time()
        body = request.get_json() or {}
        date_from = body.get("date_from")
        date_to = body.get("date_to")

        # Admite múltiples IDs o uno solo
        selected_users = body.get("user_ids")
        if selected_users is None:
            single = body.get("user_id")
            selected_users = [single] if single else []
        elif isinstance(selected_users, (str, int)):
            selected_users = [selected_users]
        
        selected_users = [str(u).strip() for u in selected_users if str(u).strip()]

        criterion = body.get("criterion", "work_date")  # 'work_date' o 'submit_date'

        if not date_from or not date_to:
            return jsonify({"success": False, "error": "Debe especificar 'date_from' y 'date_to'"}), 400

        print(f"\n=======================================================")
        print(f"⚡ [CONSULTA OPTIMIZADA] Rango: {date_from} al {date_to} | Modo: {criterion}")
        print(f"👥 Colaboradores ({len(selected_users)}): {selected_users or 'TODOS'}")
        print(f"=======================================================")

        raw_records = []
        direct_success = False

        # -------------------------------------------------------------
        # 1. INTENTO DIRECTO GLOBAL (task.elapseditem.getlist con paginación por <ID)
        # -------------------------------------------------------------
        # En Bitrix REST API, el filtro siempre debe basarse en CREATED_DATE
        # Si el criterio es 'submit_date' (PureTaskReport), usamos un buffer más amplio (15 días)
        # para capturar registros del mes subidos a destiempo, y en memoria filtramos por DATE_START.
        buffer_days = 15 if criterion == "submit_date" else 1
        dt_start_buffer = (datetime.strptime(date_from, "%Y-%m-%d") - timedelta(days=buffer_days)).strftime("%Y-%m-%d 00:00:00")
        dt_end_target = (datetime.strptime(date_to, "%Y-%m-%d") + timedelta(days=buffer_days)).strftime("%Y-%m-%d 23:59:59")

        base_filter = {
            ">=CREATED_DATE": dt_start_buffer,
            "<=CREATED_DATE": dt_end_target
        }

        # Si se seleccionaron de 1 a 3 colaboradores específicos, consultar por cada uno para máxima velocidad.
        # Si son más o es "Todos", consultar globalmente para evitar que Bitrix falle al recibir listas de USER_ID.
        user_queries = selected_users if (selected_users and len(selected_users) <= 3) else [None]

        for uid in user_queries:
            curr_filter = dict(base_filter)
            if uid:
                curr_filter["USER_ID"] = str(uid)

            # Paginación ultra rápida por <ID (soluciona el bug de Bitrix donde 'next' se estanca)
            for _ in range(50):  # Hasta 2,500 registros por consulta
                payload = {
                    "order": {"ID": "desc"},
                    "filter": curr_filter,
                    "select": ["ID", "TASK_ID", "USER_ID", "SECONDS", "MINUTES", "COMMENT_TEXT", "CREATED_DATE", "DATE_START", "DATE_STOP"]
                }
                res = call_bitrix("task.elapseditem.getlist", payload)

                if "error" in res:
                    break

                items = res.get("result", [])
                if not isinstance(items, list) or not items:
                    direct_success = True
                    break

                raw_records.extend(items)
                direct_success = True

                # Si devuelve menos de 50 registros, se descargó el 100% de esta consulta
                if len(items) < 50:
                    break

                # Paginación por <ID
                last_id = items[-1].get("ID")
                if not last_id:
                    break
                curr_filter["<ID"] = last_id

        print(f"⚡ [RESULTADO DIRECTO] {len(raw_records)} registros descargados en tiempo récord.")

        # -------------------------------------------------------------
        # 2. RASTREO RÁPIDO POR TAREAS (Si la llamada directa no arrojó o falló)
        # -------------------------------------------------------------
        if not direct_success or len(raw_records) == 0:
            print("🔄 Rastreo optimizado por tareas de colaboradores...")
            task_ids_set = set()

            # Fecha límite segura (con 2 días de tolerancia por diferencia de zona horaria UTC)
            try:
                dt_base = datetime.strptime(date_from, "%Y-%m-%d") - timedelta(days=2)
                changed_since = dt_base.strftime("%Y-%m-%d 00:00:00")
            except Exception:
                changed_since = f"{date_from} 00:00:00"

            users_to_check = selected_users if selected_users else [None]

            for uid in users_to_check:
                task_filter = {">=CHANGED_DATE": changed_since}
                if uid:
                    task_filter["MEMBER"] = uid

                start_tasks = 0
                for _ in range(4):  # Máximo 200 tareas modificadas recientemente por colaborador
                    t_res = call_bitrix("tasks.task.list", {
                        "filter": task_filter,
                        "select": ["ID", "TITLE", "GROUP_ID", "CHANGED_DATE"],
                        "order": {"CHANGED_DATE": "DESC"},
                        "start": start_tasks
                    })

                    t_dict = t_res.get("result", {})
                    tasks_batch = t_dict.get("tasks", []) if isinstance(t_dict, dict) else (t_dict if isinstance(t_dict, list) else [])
                    
                    if not tasks_batch:
                        break

                    for t in tasks_batch:
                        tid = str(t.get("id") or t.get("ID") or "")
                        if tid:
                            task_ids_set.add(tid)
                            if tid not in CACHE_TASKS:
                                CACHE_TASKS[tid] = {
                                    "id": tid,
                                    "title": t.get("title") or t.get("TITLE") or f"Tarea #{tid}",
                                    "group_id": str(t.get("groupId") or t.get("GROUP_ID") or "0")
                                }

                    if "next" in t_res:
                        start_tasks = t_res["next"]
                    else:
                        break

            print(f"📋 Total tareas activas identificadas en el período: {len(task_ids_set)}")

            # Descargar tiempos de cada tarea con Batch masivo (50 por llamada)
            all_tids = list(task_ids_set)
            for i in range(0, len(all_tids), 50):
                chunk = all_tids[i:i + 50]
                cmd = {}
                for tid in chunk:
                    cmd[f"t_{tid}"] = f"task.elapseditem.getlist?taskId={tid}"

                batch_res = call_bitrix("batch", {"halt": 0, "cmd": cmd})
                b_res_container = batch_res.get("result", {})
                inner = b_res_container.get("result", {}) if isinstance(b_res_container, dict) else {}
                b_dict = inner if isinstance(inner, dict) else (b_res_container if isinstance(b_res_container, dict) else {})

                for k, res_items in b_dict.items():
                    if isinstance(res_items, dict) and "result" in res_items:
                        res_items = res_items["result"]
                    if isinstance(res_items, list):
                        raw_records.extend(res_items)

        # -------------------------------------------------------------
        # 3. RESOLVER TÍTULOS DE TAREAS Y GRUPOS EN BLOQUE (ULTRA RÁPIDO)
        # -------------------------------------------------------------
        needed_task_ids = [str(r["TASK_ID"]) for r in raw_records if isinstance(r, dict) and r.get("TASK_ID") and str(r.get("TASK_ID")) not in CACHE_TASKS]
        needed_task_ids = list(set(needed_task_ids))

        for i in range(0, len(needed_task_ids), 50):
            chunk = needed_task_ids[i:i + 50]
            t_data = call_bitrix("tasks.task.list", {
                "filter": {"ID": chunk},
                "select": ["ID", "TITLE", "GROUP_ID", "PARENT_ID", "CREATED_BY", "CREATOR", "TIME_ESTIMATE", "TIME_SPENT_IN_LOGS"]
            })
            t_res = t_data.get("result", {})
            tasks_list = t_res.get("tasks", []) if isinstance(t_res, dict) else (t_res if isinstance(t_res, list) else [])
            for t in tasks_list:
                tid = str(t.get("id") or t.get("ID") or "")
                if tid:
                    pid = str(t.get("parentId") or t.get("PARENT_ID") or "")
                    if pid in ["0", "None", "null"]:
                        pid = ""
                    gid = str(t.get("groupId") or t.get("GROUP_ID") or "0")

                    cr = t.get("creator") or t.get("CREATOR") or {}
                    c_name = ""
                    if isinstance(cr, dict):
                        c_name = cr.get("name") or cr.get("NAME") or ""
                    if not c_name:
                        cid = str(t.get("createdBy") or t.get("CREATED_BY") or "")
                        if cid and cid in CACHE_USERS:
                            c_name = CACHE_USERS[cid].get("name", "")
                    if not c_name:
                        c_name = "Desconocido"

                    est_sec = int(t.get("timeEstimate") or t.get("TIME_ESTIMATE") or 0)
                    spent_sec = int(t.get("timeSpentInLogs") or t.get("TIME_SPENT_IN_LOGS") or 0)

                    CACHE_TASKS[tid] = {
                        "id": tid,
                        "title": t.get("title") or t.get("TITLE") or f"Tarea #{tid}",
                        "group_id": gid,
                        "parent_id": pid,
                        "parent_title": "",
                        "creator_name": c_name,
                        "time_estimate": est_sec,
                        "time_spent_in_logs": spent_sec
                    }

        # Resolver nombres de tareas madre / padre en bloque
        needed_parents = [t["parent_id"] for t in CACHE_TASKS.values() if t.get("parent_id") and t.get("parent_id") not in CACHE_TASKS]
        needed_parents = list(set(needed_parents))
        for i in range(0, len(needed_parents), 50):
            chunk = needed_parents[i:i + 50]
            p_data = call_bitrix("tasks.task.list", {
                "filter": {"ID": chunk},
                "select": ["ID", "TITLE"]
            })
            p_res = p_data.get("result", {})
            p_list = p_res.get("tasks", []) if isinstance(p_res, dict) else (p_res if isinstance(p_res, list) else [])
            for pt in p_list:
                ptid = str(pt.get("id") or pt.get("ID") or "")
                if ptid:
                    CACHE_TASKS[ptid] = {
                        "id": ptid,
                        "title": pt.get("title") or pt.get("TITLE") or f"Tarea #{ptid}",
                        "group_id": "0",
                        "parent_id": "",
                        "parent_title": "",
                        "creator_name": "",
                        "time_estimate": 0,
                        "time_spent_in_logs": 0
                    }

        # Asignar el título de la tarea madre
        for tid, t in CACHE_TASKS.items():
            pid = t.get("parent_id")
            if pid and pid in CACHE_TASKS:
                t["parent_title"] = CACHE_TASKS[pid].get("title", "")

        # Resolver Grupos / Proyectos en UNA SOLA llamada si faltan
        needed_group_ids = [t["group_id"] for t in CACHE_TASKS.values() if t.get("group_id") and t.get("group_id") != "0" and t.get("group_id") not in CACHE_GROUPS]
        needed_group_ids = list(set(needed_group_ids))

        if needed_group_ids:
            g_data = call_bitrix("sonet_group.get", {"FILTER": {"ID": needed_group_ids}})
            g_list = g_data.get("result", [])
            if isinstance(g_list, list):
                for g in g_list:
                    gid = str(g.get("ID", ""))
                    if gid:
                        CACHE_GROUPS[gid] = g.get("NAME", f"Proyecto {gid}")

        # -------------------------------------------------------------
        # 4. FILTRADO DINÁMICO, DEDUPLICACIÓN Y CÁLCULOS
        # -------------------------------------------------------------
        matched_records = []
        task_user_map = {}
        resumen_usuarios = {}
        total_minutos_general = 0
        total_segundos_general = 0
        seen_record_ids = set()

        for r in raw_records:
            if not isinstance(r, dict):
                continue

            r_id = str(r.get("ID", ""))
            if r_id and r_id in seen_record_ids:
                continue
            if r_id:
                seen_record_ids.add(r_id)

            u_id = str(r.get("USER_ID", "0"))
            t_id = str(r.get("TASK_ID", "0"))

            # FILTRO DE USUARIOS SELECCIONADOS (Nómina)
            if selected_users and u_id not in selected_users:
                continue

            # FILTRO DE FECHA SEGÚN CRITERIO (Nómina Real vs PureTaskReport)
            matched, eff_date = check_record_date_match(r, date_from, date_to, criterion)
            if not matched:
                continue

            mins = 0
            sec = 0
            try:
                mins = int(r.get("MINUTES") or 0)
                sec = int(r.get("SECONDS") or 0)
                if mins == 0 and sec > 0:
                    mins = round(sec / 60)
                if sec == 0 and mins > 0:
                    sec = mins * 60
            except Exception:
                mins = 0
                sec = 0

            total_minutos_general += mins
            total_segundos_general += sec

            # Resolver Nombre del colaborador desde caché
            u_info = CACHE_USERS.get(u_id, {
                "id": u_id,
                "name": f"Colaborador #{u_id}",
                "position": "Colaborador",
                "photo": None
            })

            t_info = CACHE_TASKS.get(t_id, {"title": f"Tarea #{t_id}", "group_id": "0"})
            group_name = CACHE_GROUPS.get(t_info.get("group_id"), "General")
            comment = r.get("COMMENT_TEXT") or r.get("TEXT") or ""

            # Acumulado por Persona
            if u_id not in resumen_usuarios:
                resumen_usuarios[u_id] = {
                    "user_id": u_id,
                    "name": u_info.get("name"),
                    "position": u_info.get("position"),
                    "photo": u_info.get("photo"),
                    "total_minutes": 0,
                    "total_seconds": 0,
                    "total_records": 0
                }
            resumen_usuarios[u_id]["total_minutes"] += mins
            resumen_usuarios[u_id]["total_seconds"] += sec
            resumen_usuarios[u_id]["total_records"] += 1

            # Acumulado por Persona en CADA Tarea
            tu_key = f"{u_id}_{t_id}"
            if tu_key not in task_user_map:
                pid = t_info.get("parent_id", "")
                p_title = t_info.get("parent_title", "")
                if pid and pid not in ["0", "None", "null"]:
                    parent_fmt = f"{p_title} ({pid})" if p_title else f"Tarea #{pid}"
                else:
                    parent_fmt = "Tarea Principal"

                gid = str(t_info.get("group_id") or "0")
                if gid in ["None", "null"]:
                    gid = "0"

                est_sec = t_info.get("time_estimate", 0)
                spent_sec = t_info.get("time_spent_in_logs", 0)

                task_user_map[tu_key] = {
                    "user_id": u_id,
                    "user_name": u_info.get("name"),
                    "user_position": u_info.get("position"),
                    "task_id": t_id,
                    "task_title": t_info.get("title"),
                    "project_id": gid,
                    "group_id": gid,
                    "group_name": group_name,
                    "parent_id": pid,
                    "parent_title": p_title,
                    "parent_formatted": parent_fmt,
                    "creator_name": t_info.get("creator_name", "Desconocido"),
                    "time_estimate_sec": est_sec,
                    "time_estimate_hours": round(est_sec / 3600, 2),
                    "time_spent_sec": spent_sec,
                    "time_spent_hours": round(spent_sec / 3600, 2),
                    "total_minutes": 0,
                    "total_seconds": 0,
                    "records_count": 0
                }
            task_user_map[tu_key]["total_minutes"] += mins
            task_user_map[tu_key]["total_seconds"] += sec
            task_user_map[tu_key]["records_count"] += 1

            # Formatear fecha y hora para la tabla
            c_raw = str(r.get("CREATED_DATE", "")).replace("T", " ")
            time_part = (c_raw.split(" ")[1] if " " in c_raw else "00:00:00")[:8]
            display_datetime = f"{eff_date} {time_part}"

            # Registro detallado
            matched_records.append({
                "ID": r.get("ID", 0),
                "CREATED_DATE": display_datetime,
                "DATE": eff_date,
                "USER_ID": u_id,
                "USER_NAME": u_info.get("name"),
                "USER_POSITION": u_info.get("position"),
                "TASK_ID": t_id,
                "TASK_TITLE": t_info.get("title"),
                "GROUP_ID": t_info.get("group_id"),
                "GROUP_NAME": group_name,
                "SECONDS": sec,
                "MINUTES": mins,
                "HOURS": round(mins / 60, 2),
                "HOURS_FORMATTED": f"{mins // 60:02d}h {mins % 60:02d}m",
                "HOURS_DECIMAL": round(mins / 60, 2),
                "COMMENT": comment,
                "COMMENT_TEXT": comment
            })

        # Resumen por tarea (ordenado por minutos)
        task_user_list = sorted(task_user_map.values(), key=lambda x: x["total_minutes"], reverse=True)
        for tu in task_user_list:
            tm = tu["total_minutes"]
            tu["hours_formatted"] = f"{tm // 60:02d}h {tm % 60:02d}m"
            tu["hours_decimal"] = round(tm / 60, 2)

        # Resumen por persona (ordenado por minutos)
        resumen_list = sorted(resumen_usuarios.values(), key=lambda x: x["total_minutes"], reverse=True)
        for u in resumen_list:
            tm = u["total_minutes"]
            u["hours_formatted"] = f"{tm // 60:02d}h {tm % 60:02d}m"
            u["hours_decimal"] = round(tm / 60, 2)
            u["percentage"] = round((tm / total_minutos_general * 100), 1) if total_minutos_general > 0 else 0

        total_h = total_minutos_general // 60
        total_m = total_minutos_general % 60
        all_known_users = sorted(list(CACHE_USERS.values()), key=lambda x: x["name"])

        elapsed_sec = round(time.time() - start_time, 2)
        print(f"⏱️ Tiempo total de respuesta: {elapsed_sec}s | Registros: {len(matched_records)} | Horas: {total_h}h {total_m}m")

        return jsonify({
            "success": True,
            "kpis": {
                "total_seconds": total_segundos_general,
                "total_minutes": total_minutos_general,
                "total_hours_formatted": f"{total_h:02d}h {total_m:02d}m",
                "total_hours_decimal": round(total_minutos_general / 60, 2),
                "total_records": len(matched_records),
                "active_workers_count": len(resumen_list),
                "tasks_count": len({r["TASK_ID"] for r in matched_records if r.get("TASK_ID")})
            },
            "users_summary": resumen_list,
            "task_user_summary": task_user_list,
            "known_users": all_known_users,
            "records": matched_records
        })

    except Exception as e:
        print("❌ Excepción en /api/times:")
        traceback.print_exc()
        return jsonify({"success": False, "error": f"Error: {str(e)}"}), 500

@app.route("/api/export", methods=["POST"])
def export_excel():
    """
    Descarga directa de archivo Excel profesional con los tiempos filtrados.
    """
    try:
        body = request.get_json() or {}
        records = body.get("records", [])
        users_summary = body.get("users_summary", [])
        task_user_summary = body.get("task_user_summary", [])
        date_from = body.get("date_from", "")
        date_to = body.get("date_to", "")

        excel_file = generar_excel_tiempos(records, users_summary, date_from, date_to, task_user_summary)

        filename = f"Reporte_Nomina_Bitrix24_{date_from}_{date_to}.xlsx"
        return send_file(
            excel_file,
            mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            as_attachment=True,
            download_name=filename
        )
    except Exception as e:
        print("❌ Error en exportación a Excel:")
        traceback.print_exc()
        return jsonify({"success": False, "error": str(e)}), 500

if __name__ == "__main__":
    print(f"\n🚀 Dashboard de Control de Tiempos Bitrix24 iniciando...")
    print(f"👉 Abre tu navegador en: http://localhost:{PORT}")
    app.run(host="0.0.0.0", port=PORT, debug=True)
