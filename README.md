# Dashboard de Control y Seguimiento de Tiempos - Bitrix24

Aplicación web profesional para la gestión, seguimiento y descarga completa de los tiempos de trabajo de colaboradores registrados en tareas de **Bitrix24**.

---

## 🚀 Características Principales

1. **Descarga Total de Tiempos (Sin límites de paginación)**:
   * Consume el endpoint REST `task.elapseditem.getlist`.
   * Itera automáticamente a través de todos los bloques de 50 registros (`next`), respetando el *rate limit* de Bitrix24 para asegurar que **ningún tiempo se quede sin descargar**.

2. **Cruce Automático de Información**:
   * **Colaboradores (`user.get`)**: Nombre completo, cargo, departamento y foto.
   * **Tareas (`tasks.task.list`)**: Título de la tarea e ID con enlace directo para abrirla en Bitrix24.
   * **Proyectos/Grupos (`sonet_group.get`)**: Identifica el proyecto o grupo de trabajo al que pertenece cada tarea.

3. **Panel Lateral de Trabajadores**:
   * Muestra todos los colaboradores activos.
   * Muestra el acumulado de horas trabajadas en el período seleccionado.
   * Permite filtrar la tabla y los gráficos por un colaborador específico con un solo clic.

4. **Filtro de Fechas Flexible**:
   * Selectores de fecha `Desde` y `Hasta`.
   * Botones de períodos rápidos: *Hoy*, *Esta semana*, *Semana anterior*, *Este mes* y *Mes anterior*.

5. **Gráficos y Métricas (KPIs)**:
   * Total de horas registradas (formato `HH:MM` y decimal).
   * Total de colaboradores con actividad en el rango.
   * Gráfico de barras comparativo por colaborador.
   * Gráfico donut de distribución de horas por Proyecto/Grupo.

6. **Exportación a Excel Profesional (`.xlsx`)**:
   * Genera un libro de Excel con 2 hojas:
     1. **Resumen por Colaborador**: Totales consolidados con fórmulas de suma y formato visual.
     2. **Detalle de Tiempos**: Registro a registro con Fecha, Empleado, Tarea, Proyecto, Horas, Segundos y Comentario.

---

## 🛠️ Cómo Iniciar la Aplicación

### Opción 1: Con 1 Clic (Recomendada)
Haz doble clic sobre el archivo:
```text
iniciar_dashboard.bat
```
Esto iniciará el servidor local y abrirá automáticamente tu navegador en `http://localhost:5000`.

### Opción 2: Desde la Terminal
```bash
python app.py
```
Luego abre tu navegador en [http://localhost:5000](http://localhost:5000).

---

## ⚙️ Configuración

Si deseas cambiar el webhook o el puerto, puedes editar el archivo [config.py](file:///d:/OneDrive/Documentos/empresa/7%20Innovacion%20y%20Desarrollo/Bitrix/config.py):
* `BITRIX_WEBHOOK_URL`: URL del Webhook entrante con permisos de `tasks`, `user` y `sonet_group`.
* `PORT`: Puerto local (por defecto `5000`).
