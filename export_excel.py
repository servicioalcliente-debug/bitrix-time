import io
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter

def generar_excel_tiempos(records, resumen_usuarios, date_from, date_to, task_user_summary=None):
    """
    Genera un archivo Excel en memoria (BytesIO) con:
    1. Hoja de Resumen por Empleado.
    2. Hoja de Resumen por Colaborador y Tarea.
    3. Hoja de Detalle Completo de Registros de Tiempo.
    """
    wb = Workbook()
    
    # ───────────────────────────────────────────────
    # ESTILOS
    # ───────────────────────────────────────────────
    header_fill = PatternFill(start_color="1F4E79", end_color="1F4E79", fill_type="solid")
    header_font = Font(name="Segoe UI", size=11, bold=True, color="FFFFFF")
    
    sub_fill = PatternFill(start_color="D9E1F2", end_color="D9E1F2", fill_type="solid")
    data_font = Font(name="Segoe UI", size=10)
    total_font = Font(name="Segoe UI", size=11, bold=True, color="1F4E79")
    
    thin_border = Border(
        left=Side(style='thin', color='D9D9D9'),
        right=Side(style='thin', color='D9D9D9'),
        top=Side(style='thin', color='D9D9D9'),
        bottom=Side(style='thin', color='D9D9D9')
    )
    
    center_align = Alignment(horizontal="center", vertical="center")
    left_align = Alignment(horizontal="left", vertical="center")
    right_align = Alignment(horizontal="right", vertical="center")
    
    # ───────────────────────────────────────────────
    # HOJA 1: RESUMEN POR EMPLEADO
    # ───────────────────────────────────────────────
    ws_resumen = wb.active
    ws_resumen.title = "Resumen por Colaborador"
    ws_resumen.views.sheetView[0].showGridLines = True
    
    ws_resumen.merge_cells("A1:E1")
    ws_resumen["A1"] = "REPORTE DE TIEMPOS DE TRABAJO - BITRIX24"
    ws_resumen["A1"].font = Font(name="Segoe UI", size=15, bold=True, color="1F4E79")
    ws_resumen["A1"].alignment = left_align
    
    ws_resumen["A2"] = f"Período consultado: {date_from} al {date_to}"
    ws_resumen["A2"].font = Font(name="Segoe UI", size=10, italic=True)
    
    headers_resumen = ["Colaborador", "Cargo", "Cantidad Registros", "Total Horas (HH:MM)", "Horas (Decimal)"]
    for col_idx, header in enumerate(headers_resumen, 1):
        cell = ws_resumen.cell(row=4, column=col_idx, value=header)
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = center_align
    
    row_num = 5
    gran_total_segundos = 0
    gran_total_registros = 0
    
    for u in resumen_usuarios:
        total_sec = u.get("total_seconds", 0)
        gran_total_segundos += total_sec
        gran_total_registros += u.get("total_records", 0)
        
        hours = total_sec // 3600
        mins = (total_sec % 3600) // 60
        dec_hours = round(total_sec / 3600, 2)
        
        ws_resumen.cell(row=row_num, column=1, value=u.get("name", "")).alignment = left_align
        ws_resumen.cell(row=row_num, column=2, value=u.get("position", "")).alignment = left_align
        ws_resumen.cell(row=row_num, column=3, value=u.get("total_records", 0)).alignment = center_align
        ws_resumen.cell(row=row_num, column=4, value=f"{hours:02d}h {mins:02d}m").alignment = center_align
        ws_resumen.cell(row=row_num, column=5, value=dec_hours).alignment = right_align
        
        for c in range(1, 6):
            cell = ws_resumen.cell(row=row_num, column=c)
            cell.font = data_font
            cell.border = thin_border
            if row_num % 2 == 0:
                cell.fill = PatternFill(start_color="F9FAFB", end_color="F9FAFB", fill_type="solid")
        
        row_num += 1
        
    # Fila de Totales
    ws_resumen.cell(row=row_num, column=1, value="TOTAL GENERAL").font = total_font
    ws_resumen.cell(row=row_num, column=1).alignment = left_align
    ws_resumen.cell(row=row_num, column=3, value=gran_total_registros).font = total_font
    ws_resumen.cell(row=row_num, column=3).alignment = center_align
    
    tot_h = gran_total_segundos // 3600
    tot_m = (gran_total_segundos % 3600) // 60
    ws_resumen.cell(row=row_num, column=4, value=f"{tot_h:02d}h {tot_m:02d}m").font = total_font
    ws_resumen.cell(row=row_num, column=4).alignment = center_align
    ws_resumen.cell(row=row_num, column=5, value=round(gran_total_segundos / 3600, 2)).font = total_font
    ws_resumen.cell(row=row_num, column=5).alignment = right_align
    
    for c in range(1, 6):
        cell = ws_resumen.cell(row=row_num, column=c)
        cell.fill = sub_fill
        cell.border = thin_border
        
    for col in ws_resumen.columns:
        max_len = max(len(str(cell.value or '')) for cell in col)
        col_letter = get_column_letter(col[0].column)
        ws_resumen.column_dimensions[col_letter].width = max(max_len + 4, 15)

    # ───────────────────────────────────────────────
    # HOJA 2: POR COLABORADOR Y TAREA
    # ───────────────────────────────────────────────
    if task_user_summary:
        ws_task_user = wb.create_sheet(title="Por Colaborador y Tarea")
        ws_task_user.views.sheetView[0].showGridLines = True

        headers_tu = [
            "Colaborador",
            "Cargo",
            "ID Proyecto",
            "Proyecto / Grupo",
            "ID Tarea Madre",
            "Tarea Madre",
            "ID Tarea",
            "Título de la Tarea",
            "Creador de la Tarea",
            "Tiempo Estimado (Hrs)",
            "Tiempo Acumulado Tarea (Hrs)",
            "Cantidad Registros",
            "Tiempo Trabajado (HH:MM)",
            "Horas Trabajadas (Decimal)"
        ]

        for col_idx, header in enumerate(headers_tu, 1):
            cell = ws_task_user.cell(row=1, column=col_idx, value=header)
            cell.fill = header_fill
            cell.font = header_font
            cell.alignment = center_align

        total_reg_tu = 0
        total_sec_tu = 0

        # Ordenar por Colaborador (A-Z) y luego por mayor tiempo trabajado
        sorted_task_user = sorted(
            task_user_summary,
            key=lambda x: (
                str(x.get("user_name", "")).strip().lower(),
                -int(x.get("total_seconds", 0))
            )
        )

        for idx, tu in enumerate(sorted_task_user, 2):
            sec = tu.get("total_seconds", 0)
            total_sec_tu += sec
            reg_cnt = tu.get("records_count", 1)
            total_reg_tu += reg_cnt

            h = sec // 3600
            m = (sec % 3600) // 60
            dec_h = round(sec / 3600, 2)

            proj_id = str(tu.get("project_id") or tu.get("group_id") or "0")
            pid = str(tu.get("parent_id") or "")
            if pid and pid not in ["0", "None", "null"]:
                parent_id_val = int(pid) if pid.isdigit() else pid
                parent_title_val = tu.get("parent_title") or f"Tarea #{pid}"
            else:
                parent_id_val = ""
                parent_title_val = "Tarea Principal"

            creator = tu.get("creator_name") or "Desconocido"
            est_h = float(tu.get("time_estimate_hours") or 0.0)
            spent_h = float(tu.get("time_spent_hours") or 0.0)

            ws_task_user.cell(row=idx, column=1, value=tu.get("user_name", "")).alignment = left_align
            ws_task_user.cell(row=idx, column=2, value=tu.get("user_position", "")).alignment = left_align
            ws_task_user.cell(row=idx, column=3, value=int(proj_id) if proj_id.isdigit() else proj_id).alignment = center_align
            ws_task_user.cell(row=idx, column=4, value=tu.get("group_name", "")).alignment = left_align
            ws_task_user.cell(row=idx, column=5, value=parent_id_val).alignment = center_align
            ws_task_user.cell(row=idx, column=6, value=parent_title_val).alignment = left_align
            ws_task_user.cell(row=idx, column=7, value=int(tu.get("task_id", 0))).alignment = center_align
            ws_task_user.cell(row=idx, column=8, value=tu.get("task_title", "")).alignment = left_align
            ws_task_user.cell(row=idx, column=9, value=creator).alignment = left_align
            ws_task_user.cell(row=idx, column=10, value=est_h).alignment = right_align
            ws_task_user.cell(row=idx, column=11, value=spent_h).alignment = right_align
            ws_task_user.cell(row=idx, column=12, value=reg_cnt).alignment = center_align
            ws_task_user.cell(row=idx, column=13, value=f"{h:02d}h {m:02d}m").alignment = center_align
            ws_task_user.cell(row=idx, column=14, value=dec_h).alignment = right_align

            for c in range(1, 15):
                cell = ws_task_user.cell(row=idx, column=c)
                cell.font = data_font
                cell.border = thin_border
                if idx % 2 == 0:
                    cell.fill = PatternFill(start_color="FAFAFA", end_color="FAFAFA", fill_type="solid")

        # Fila de Totales
        row_tot = len(task_user_summary) + 2
        ws_task_user.cell(row=row_tot, column=1, value="TOTAL GENERAL").font = total_font
        ws_task_user.cell(row=row_tot, column=1).alignment = left_align
        ws_task_user.cell(row=row_tot, column=12, value=total_reg_tu).font = total_font
        ws_task_user.cell(row=row_tot, column=12).alignment = center_align
        
        tot_h_tu = total_sec_tu // 3600
        tot_m_tu = (total_sec_tu % 3600) // 60
        ws_task_user.cell(row=row_tot, column=13, value=f"{tot_h_tu:02d}h {tot_m_tu:02d}m").font = total_font
        ws_task_user.cell(row=row_tot, column=13).alignment = center_align
        ws_task_user.cell(row=row_tot, column=14, value=round(total_sec_tu / 3600, 2)).font = total_font
        ws_task_user.cell(row=row_tot, column=14).alignment = right_align

        for c in range(1, 15):
            cell = ws_task_user.cell(row=row_tot, column=c)
            cell.fill = sub_fill
            cell.border = thin_border

        for col in ws_task_user.columns:
            col_letter = get_column_letter(col[0].column)
            if col_letter in ['F', 'H']:
                ws_task_user.column_dimensions[col_letter].width = 38
            else:
                max_len = max(len(str(cell.value or '')) for cell in col)
                ws_task_user.column_dimensions[col_letter].width = max(max_len + 3, 13)

    # ───────────────────────────────────────────────
    # HOJA 3: DETALLE COMPLETO DE REGISTROS DE TIEMPO
    # ───────────────────────────────────────────────
    ws_detalle = wb.create_sheet(title="Detalle Cronológico")
    ws_detalle.views.sheetView[0].showGridLines = True
    
    headers_detalle = [
        "ID Registro", 
        "Fecha / Hora", 
        "Colaborador que Registró", 
        "ID Tarea", 
        "Título de Tarea", 
        "Proyecto / Grupo", 
        "Tiempo (HH:MM)", 
        "Horas Decimales", 
        "Comentario / Actividad"
    ]
    
    for col_idx, header in enumerate(headers_detalle, 1):
        cell = ws_detalle.cell(row=1, column=col_idx, value=header)
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = center_align
        
    for idx, r in enumerate(records, 2):
        sec = int(r.get("SECONDS") or 0)
        h = sec // 3600
        m = (sec % 3600) // 60
        dec_h = round(sec / 3600, 2)
        
        ws_detalle.cell(row=idx, column=1, value=int(r.get("ID", 0))).alignment = center_align
        ws_detalle.cell(row=idx, column=2, value=str(r.get("CREATED_DATE", ""))).alignment = center_align
        ws_detalle.cell(row=idx, column=3, value=r.get("USER_NAME", f"Usuario {r.get('USER_ID')}")).alignment = left_align
        ws_detalle.cell(row=idx, column=4, value=int(r.get("TASK_ID", 0))).alignment = center_align
        ws_detalle.cell(row=idx, column=5, value=r.get("TASK_TITLE", "")).alignment = left_align
        ws_detalle.cell(row=idx, column=6, value=r.get("GROUP_NAME", "")).alignment = left_align
        ws_detalle.cell(row=idx, column=7, value=f"{h:02d}h {m:02d}m").alignment = center_align
        ws_detalle.cell(row=idx, column=8, value=dec_h).alignment = right_align
        ws_detalle.cell(row=idx, column=9, value=r.get("COMMENT_TEXT", "")).alignment = left_align
        
        for c in range(1, 10):
            cell = ws_detalle.cell(row=idx, column=c)
            cell.font = data_font
            cell.border = thin_border
            if idx % 2 == 0:
                cell.fill = PatternFill(start_color="FAFAFA", end_color="FAFAFA", fill_type="solid")
                
    for col in ws_detalle.columns:
        col_letter = get_column_letter(col[0].column)
        if col_letter in ['E', 'I']:
            ws_detalle.column_dimensions[col_letter].width = 38
        else:
            max_len = max(len(str(cell.value or '')) for cell in col)
            ws_detalle.column_dimensions[col_letter].width = max(max_len + 3, 14)
            
    output = io.BytesIO()
    wb.save(output)
    output.seek(0)
    return output
