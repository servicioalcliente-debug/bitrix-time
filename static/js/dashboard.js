// Estado de la aplicación
let appState = {
    users: [],                  // Todos los usuarios obtenidos de Bitrix24
    records: [],                // Registros individuales de tiempo
    taskUserSummary: [],        // Resumen rectificado por Persona y por Tarea
    usersSummary: [],           // Resumen global por persona
    kpis: {},                   // KPIs consolidados
    selectedUserIds: [],        // Lista de IDs seleccionados para Nómina (vacío = Todos)
    charts: {
        usersBar: null,
        projectsDoughnut: null
    }
};

// Función para remover tildes y caracteres especiales para búsqueda flexible
function removeAccents(str) {
    return (str || "")
        .normalize("NFD")
        .replace(/[\u0300-\u036f]/g, "")
        .toLowerCase()
        .trim();
}

// Inicialización
document.addEventListener("DOMContentLoaded", () => {
    initDatePresets();
    setupEventListeners();
    fetchUsers();
});

// Configurar presets de fechas
function initDatePresets() {
    applyPreset("month"); // Por defecto: Este mes

    document.querySelectorAll(".preset-btn").forEach(btn => {
        btn.addEventListener("click", (e) => {
            document.querySelectorAll(".preset-btn").forEach(b => b.classList.remove("active"));
            e.currentTarget.classList.add("active");
            applyPreset(e.currentTarget.dataset.preset);
        });
    });
}

function formatDate(date) {
    const d = new Date(date);
    const month = '' + (d.getMonth() + 1);
    const day = '' + d.getDate();
    const year = d.getFullYear();
    return [year, month.padStart(2, '0'), day.padStart(2, '0')].join('-');
}

function applyPreset(preset) {
    const today = new Date();
    let fromDate = new Date();
    let toDate = new Date();

    if (preset === "today") {
        fromDate = today;
        toDate = today;
    } else if (preset === "week") {
        const day = today.getDay() || 7; // Lunes = 1
        fromDate.setDate(today.getDate() - day + 1);
        toDate = today;
    } else if (preset === "lastweek") {
        const day = today.getDay() || 7;
        fromDate.setDate(today.getDate() - day - 6);
        toDate = new Date(fromDate);
        toDate.setDate(fromDate.getDate() + 6);
    } else if (preset === "month") {
        fromDate = new Date(today.getFullYear(), today.getMonth(), 1);
        toDate = today;
    } else if (preset === "lastmonth") {
        fromDate = new Date(today.getFullYear(), today.getMonth() - 1, 1);
        toDate = new Date(today.getFullYear(), today.getMonth(), 0);
    }

    document.getElementById("dateFrom").value = formatDate(fromDate);
    document.getElementById("dateTo").value = formatDate(toDate);
}

// Configurar eventos
function setupEventListeners() {
    document.getElementById("btnConsultar").addEventListener("click", fetchTimeRecords);
    document.getElementById("btnExportar").addEventListener("click", exportToExcel);

    // Cambio de Criterio de Fecha (Nómina Real vs PureTaskReport)
    document.querySelectorAll('input[name="dateCriterion"]').forEach(radio => {
        radio.addEventListener("change", () => {
            const dateFrom = document.getElementById("dateFrom").value;
            const dateTo = document.getElementById("dateTo").value;
            if (dateFrom && dateTo && appState.records.length > 0) {
                fetchTimeRecords();
            }
        });
    });

    // BUSCADOR EN VIVO DE COLABORADORES (CON NORMALIZACIÓN DE ACENTOS)
    const userSearchInput = document.getElementById("userSearchInput");
    
    // Evita que Bootstrap intercepte teclas como espacio o flechas dentro del input
    userSearchInput.addEventListener("keydown", (e) => {
        e.stopPropagation();
    });

    userSearchInput.addEventListener("input", (e) => {
        const q = removeAccents(e.target.value);
        let visibleCount = 0;

        document.querySelectorAll(".user-checkbox-item").forEach(item => {
            const nameNorm = removeAccents(item.dataset.userName || "");
            const posNorm = removeAccents(item.dataset.userPos || "");

            const isMatch = !q || nameNorm.includes(q) || posNorm.includes(q);
            
            if (isMatch) {
                item.classList.remove("d-none");
                visibleCount++;
            } else {
                item.classList.add("d-none");
            }
        });

        // Mensaje de sin resultados si no coincide ninguno
        let noResultsMsg = document.getElementById("noUserResults");
        if (visibleCount === 0 && q) {
            if (!noResultsMsg) {
                noResultsMsg = document.createElement("div");
                noResultsMsg.id = "noUserResults";
                noResultsMsg.className = "text-center py-2 text-muted small";
                noResultsMsg.textContent = "No se encontraron colaboradores";
                document.getElementById("userCheckboxContainer").appendChild(noResultsMsg);
            }
            noResultsMsg.style.display = "block";
        } else if (noResultsMsg) {
            noResultsMsg.style.display = "none";
        }
    });

    // Botones de acción rápida en el desplegable (Seleccionar Todos / Ninguno)
    document.getElementById("btnSelectAll").addEventListener("click", () => {
        appState.selectedUserIds = [];
        document.querySelectorAll(".user-cb").forEach(cb => {
            const item = cb.closest(".user-checkbox-item");
            if (!item || !item.classList.contains("d-none")) {
                if (!appState.selectedUserIds.includes(cb.value)) {
                    appState.selectedUserIds.push(cb.value);
                }
            }
        });
        renderUserCheckboxes(appState.users);
        updateDropdownLabel();
        filterAllTables();
    });

    document.getElementById("btnClearAll").addEventListener("click", () => {
        appState.selectedUserIds = [];
        renderUserCheckboxes(appState.users);
        updateDropdownLabel();
        filterAllTables();
    });

    // Búsqueda en vivo en las tablas
    document.getElementById("searchTable").addEventListener("input", filterAllTables);
}

// Cargar lista inicial de trabajadores
async function fetchUsers() {
    const container = document.getElementById("userCheckboxContainer");
    if (!container) return;

    // Indicador visual de carga
    container.innerHTML = `
        <div class="text-center py-3 text-muted small">
            <span class="spinner-border spinner-border-sm me-2 text-primary" role="status"></span>
            Cargando colaboradores de Bitrix24...
        </div>
    `;

    try {
        const res = await fetch("/api/users");
        if (!res.ok) {
            throw new Error(`HTTP ${res.status}`);
        }
        const data = await res.json();
        
        if (data.success && data.users && data.users.length > 0) {
            appState.users = data.users;
            renderUserCheckboxes(data.users);
        } else {
            container.innerHTML = `
                <div class="text-center py-3 text-muted small">
                    <i class="fa-solid fa-triangle-exclamation text-warning me-1"></i> No se encontraron colaboradores.<br>
                    <button type="button" class="btn btn-sm btn-outline-primary mt-2" onclick="fetchUsers()">
                        <i class="fa-solid fa-rotate-right me-1"></i> Reintentar carga
                    </button>
                </div>
            `;
        }
    } catch (err) {
        console.warn("Aviso al obtener usuarios iniciales:", err);
        container.innerHTML = `
            <div class="text-center py-3 text-danger small">
                <i class="fa-solid fa-circle-exclamation text-danger me-1"></i> Error al conectar con el servidor.<br>
                <button type="button" class="btn btn-sm btn-outline-danger mt-2" onclick="fetchUsers()">
                    <i class="fa-solid fa-rotate-right me-1"></i> Reintentar
                </button>
            </div>
        `;
    }
}

// Renderizar checkboxes dentro del desplegable
function renderUserCheckboxes(usersList) {
    const container = document.getElementById("userCheckboxContainer");
    if (!container) return;
    if (!usersList || usersList.length === 0) {
        container.innerHTML = `<div class="text-center py-3 text-muted small">No se encontraron colaboradores.</div>`;
        return;
    }

    let html = '';
    usersList.forEach(u => {
        const isChecked = appState.selectedUserIds.includes(u.id);
        const checkedAttr = isChecked ? 'checked' : '';
        const activeClass = isChecked ? 'bg-primary-subtle border-start border-3 border-primary' : '';
        const cargo = u.position ? `<small class="text-muted d-block text-truncate" style="font-size: 0.72rem;">${u.position}</small>` : '';
        const checkIcon = isChecked ? '<i class="fa-solid fa-circle-check text-primary ms-auto ps-1" style="font-size: 0.9rem;"></i>' : '';

        html += `
            <div class="user-checkbox-item d-flex align-items-center py-1 px-2 rounded mb-1 hover-bg ${activeClass}" 
                 data-user-id="${u.id}" data-user-name="${u.name}" data-user-pos="${u.position || ''}" 
                 style="cursor: pointer; transition: background-color 0.15s ease;"
                 onclick="toggleUserSelection('${u.id}')">
                <input class="form-check-input user-cb mt-0 me-2" type="checkbox" value="${u.id}" id="cb_user_${u.id}" ${checkedAttr} onclick="event.stopPropagation(); onUserCheckboxChange(this)">
                <label class="flex-grow-1 text-truncate mb-0 cursor-pointer" for="cb_user_${u.id}" onclick="event.stopPropagation(); toggleUserSelection('${u.id}')">
                    <span class="fw-semibold text-dark d-block text-truncate" style="font-size: 0.83rem;">${u.name}</span>
                    ${cargo}
                </label>
                ${checkIcon}
            </div>
        `;
    });

    container.innerHTML = html;
    updateDropdownLabel();
}

// Alternar selección de un usuario al hacer clic en su fila
window.toggleUserSelection = function(userId) {
    const cb = document.getElementById(`cb_user_${userId}`);
    if (appState.selectedUserIds.includes(userId)) {
        appState.selectedUserIds = appState.selectedUserIds.filter(id => id !== userId);
        if (cb) cb.checked = false;
    } else {
        appState.selectedUserIds.push(userId);
        if (cb) cb.checked = true;
    }
    // Re-renderizar visualmente las filas para actualizar resaltados
    renderUserCheckboxes(appState.users);
    updateDropdownLabel();
    filterAllTables();
};

// Evento al marcar / desmarcar un checkbox directamente
window.onUserCheckboxChange = function(checkbox) {
    const userId = checkbox.value;
    if (checkbox.checked) {
        if (!appState.selectedUserIds.includes(userId)) {
            appState.selectedUserIds.push(userId);
        }
    } else {
        appState.selectedUserIds = appState.selectedUserIds.filter(id => id !== userId);
    }
    renderUserCheckboxes(appState.users);
    updateDropdownLabel();
    filterAllTables();
};

// Eliminar un colaborador individual desde el cuadrito / badge
window.removeSelectedUser = function(userId) {
    appState.selectedUserIds = appState.selectedUserIds.filter(id => id !== userId);
    const cb = document.getElementById(`cb_user_${userId}`);
    if (cb) cb.checked = false;
    renderUserCheckboxes(appState.users);
    updateDropdownLabel();
    filterAllTables();
};

// Limpiar todos los seleccionados
window.clearSelectedUsers = function() {
    appState.selectedUserIds = [];
    document.querySelectorAll(".user-cb").forEach(cb => { cb.checked = false; });
    renderUserCheckboxes(appState.users);
    updateDropdownLabel();
    filterAllTables();
};

// Renderizar pastillas visuales de colaboradores seleccionados
function renderSelectedUsersBadges() {
    const card = document.getElementById("selectedUsersCard");
    const pillsContainer = document.getElementById("selectedUsersPills");
    const badgeCount = document.getElementById("badgeCount");
    const dropdownPreview = document.getElementById("dropdownSelectedPreview");
    const dropdownNames = document.getElementById("dropdownSelectedNames");
    const dropdownCount = document.getElementById("dropdownSelectedCount");

    const count = appState.selectedUserIds.length;
    const total = appState.users.length;

    // Si no hay ninguno o están todos seleccionados, ocultar el cuadrito
    if (count === 0 || (total > 0 && count === total)) {
        if (card) card.style.display = "none";
        if (dropdownPreview) dropdownPreview.style.display = "none";
        return;
    }

    // Obtener objetos de usuarios seleccionados
    const selectedUsers = appState.selectedUserIds.map(id => {
        const u = appState.users.find(user => user.id === id);
        return u || { id: id, name: `Colaborador #${id}` };
    });

    // Mostrar el cuadrito visible
    if (card) card.style.display = "block";
    if (badgeCount) badgeCount.textContent = count;

    if (pillsContainer) {
        let pillsHtml = '';
        selectedUsers.forEach(u => {
            pillsHtml += `
                <span class="badge bg-white text-dark border border-primary-subtle shadow-xs d-inline-flex align-items-center py-1 px-2" style="font-size: 0.82rem; font-weight: 500;">
                    <i class="fa-solid fa-circle-user text-primary me-1"></i>
                    <span class="text-truncate" style="max-width: 220px;" title="${u.name}">${u.name}</span>
                    <button type="button" class="btn-close ms-2" style="font-size: 0.55rem;" aria-label="Quitar" onclick="removeSelectedUser('${u.id}')" title="Quitar ${u.name}"></button>
                </span>
            `;
        });
        pillsContainer.innerHTML = pillsHtml;
    }

    // Actualizar vista previa en el desplegable
    if (dropdownPreview) {
        dropdownPreview.style.display = "block";
        if (dropdownCount) dropdownCount.textContent = count;
        if (dropdownNames) {
            dropdownNames.textContent = selectedUsers.map(u => u.name).join(", ");
            dropdownNames.title = selectedUsers.map(u => u.name).join(", ");
        }
    }
}

// Actualizar etiqueta del botón desplegable
function updateDropdownLabel() {
    const btnText = document.getElementById("userDropdownBtnText");
    const userDropdownBtn = document.getElementById("userDropdownBtn");
    const count = appState.selectedUserIds.length;
    const total = appState.users.length;

    if (count === 0 || (total > 0 && count === total)) {
        btnText.innerHTML = `<i class="fa-solid fa-users me-1 text-primary"></i> Todos los Trabajadores`;
        if (userDropdownBtn) userDropdownBtn.title = "Todos los trabajadores de la empresa";
    } else if (count === 1) {
        const u = appState.users.find(user => user.id === appState.selectedUserIds[0]);
        const name = u ? u.name : `Colaborador #${appState.selectedUserIds[0]}`;
        btnText.innerHTML = `<i class="fa-solid fa-user-check me-1 text-success"></i> ${name}`;
        if (userDropdownBtn) userDropdownBtn.title = `Seleccionado: ${name}`;
    } else if (count === 2) {
        const u1 = appState.users.find(user => user.id === appState.selectedUserIds[0]);
        const u2 = appState.users.find(user => user.id === appState.selectedUserIds[1]);
        const n1 = u1 ? u1.name.split(" ")[0] : `#${appState.selectedUserIds[0]}`;
        const n2 = u2 ? u2.name.split(" ")[0] : `#${appState.selectedUserIds[1]}`;
        btnText.innerHTML = `<i class="fa-solid fa-user-check me-1 text-success"></i> ${n1} y ${n2} (2)`;
        if (userDropdownBtn) userDropdownBtn.title = `Seleccionados: ${u1?.name || n1}, ${u2?.name || n2}`;
    } else {
        btnText.innerHTML = `<i class="fa-solid fa-users-viewfinder me-1 text-success"></i> <strong>${count}</strong> colaboradores seleccionados`;
        const names = appState.selectedUserIds.map(id => {
            const u = appState.users.find(user => user.id === id);
            return u ? u.name : `#${id}`;
        }).join(", ");
        if (userDropdownBtn) userDropdownBtn.title = `Seleccionados (${count}): ${names}`;
    }

    const statusText = document.getElementById("filterStatusText");
    if (statusText) {
        if (count > 0 && count < total) {
            statusText.innerHTML = `Mostrando resultados para: <strong class="text-primary">${count} colaborador(es) de nómina</strong> (<a href="#" onclick="clearSelectedUsers(); return false;">Ver todos</a>)`;
        } else {
            statusText.textContent = "Mostrando registros de todos los colaboradores";
        }
    }

    // Sincronizar cuadrito visual
    renderSelectedUsersBadges();
}

// Consultar y descargar TODOS los tiempos
async function fetchTimeRecords() {
    const dateFrom = document.getElementById("dateFrom").value;
    const dateTo = document.getElementById("dateTo").value;

    if (!dateFrom || !dateTo) {
        alert("Por favor selecciona un rango de fechas válido.");
        return;
    }

    const btn = document.getElementById("btnConsultar");
    const spinner = document.getElementById("btnSpinner");
    const icon = document.getElementById("btnIcon");
    const text = document.getElementById("btnText");
    const exportBtn = document.getElementById("btnExportar");

    // UI de carga
    btn.disabled = true;
    spinner.classList.remove("d-none");
    icon.classList.add("d-none");
    text.textContent = "Consultando nómina...";

    try {
        const criterion = document.querySelector('input[name="dateCriterion"]:checked')?.value || "work_date";

        const response = await fetch("/api/times", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                date_from: dateFrom,
                date_to: dateTo,
                criterion: criterion,
                user_ids: appState.selectedUserIds.length > 0 ? appState.selectedUserIds : null
            })
        });

        let data;
        try {
            data = await response.json();
        } catch (jsonErr) {
            throw new Error(`Error ${response.status}: El servidor no devolvió una respuesta válida.`);
        }

        if (response.ok && data.success) {
            appState.records = data.records;
            appState.taskUserSummary = data.task_user_summary || [];
            appState.usersSummary = data.users_summary;
            appState.kpis = data.kpis;

            // Actualizar lista de colaboradores si descubrió nuevos
            if (data.known_users && data.known_users.length > 0) {
                appState.users = data.known_users;
                renderUserCheckboxes(data.known_users);
            }

            // Actualizar KPIs
            document.getElementById("kpiTotalHoras").textContent = data.kpis.total_hours_formatted;
            document.getElementById("kpiHorasDecimal").textContent = `${data.kpis.total_hours_decimal} hrs decimales`;
            document.getElementById("kpiTrabajadores").textContent = data.kpis.active_workers_count;
            document.getElementById("kpiTareas").textContent = data.kpis.tasks_count;
            document.getElementById("kpiRegistros").textContent = data.kpis.total_records;

            // Renderizar gráficos
            renderCharts(data.users_summary, data.records);

            // Renderizar ambas tablas
            filterAllTables();

            exportBtn.disabled = (data.records.length === 0);
        } else {
            alert("Aviso de Bitrix24: " + (data.error || "No se pudo consultar la información."));
        }
    } catch (error) {
        console.error("Error en fetchTimeRecords:", error);
        alert(error.message || "Ocurrió un error al comunicarse con el servidor.");
    } finally {
        btn.disabled = false;
        spinner.classList.add("d-none");
        icon.classList.remove("d-none");
        text.textContent = "Consultar Tiempos";
    }
}

// Filtrar y Renderizar ambas tablas
function filterAllTables() {
    filterSummaryTable();
    filterDetailTable();
}

// 1. Tabla de Resumen por Persona y Tarea
function filterSummaryTable() {
    const q = removeAccents(document.getElementById("searchTable").value);
    const tbody = document.getElementById("tableSummaryBody");
    const footerCount = document.getElementById("tableFooterCount");

    let filtered = appState.taskUserSummary || [];

    // Filtro por selección múltiple de colaboradores (comparación segura como texto)
    if (appState.selectedUserIds && appState.selectedUserIds.length > 0) {
        const selSet = new Set(appState.selectedUserIds.map(id => String(id).trim()));
        filtered = filtered.filter(item => selSet.has(String(item.user_id).trim()));
    }

    if (q) {
        filtered = filtered.filter(item =>
            removeAccents(item.task_title || "").includes(q) ||
            removeAccents(item.user_name || "").includes(q) ||
            removeAccents(item.group_name || "").includes(q)
        );
    }

    footerCount.textContent = `${filtered.length} tarea(s) trabajadas`;

    if (filtered.length === 0) {
        tbody.innerHTML = `
            <tr>
                <td colspan="6" class="text-center py-5 text-muted">
                    <i class="fa-regular fa-folder-open fa-2x mb-2 text-secondary opacity-50"></i>
                    <p class="mb-0">No se encontraron tareas con tiempos registrados para la selección actual.</p>
                </td>
            </tr>
        `;
        return;
    }

    let html = '';
    filtered.forEach(item => {
        const taskUrl = `${BITRIX_DOMAIN}/company/personal/user/${item.user_id}/tasks/task/view/${item.task_id}/`;
        html += `
            <tr>
                <td class="ps-4 text-nowrap">
                    <div class="fw-semibold text-dark">${item.user_name}</div>
                    <small class="text-muted">${item.user_position || 'Colaborador'}</small>
                </td>
                <td>
                    <div class="fw-semibold text-dark text-truncate" style="max-width: 420px;" title="${item.task_title}">
                        ${item.task_title}
                    </div>
                    <small class="text-muted">ID: #${item.task_id}</small>
                </td>
                <td>
                    <span class="badge bg-light text-dark border">${item.group_name || 'General'}</span>
                </td>
                <td class="text-center text-nowrap">
                    <span class="time-badge">${item.hours_formatted}</span>
                    <div class="text-muted" style="font-size: 0.72rem;">${item.hours_decimal} hrs</div>
                </td>
                <td class="text-center">
                    <span class="badge bg-secondary-subtle text-secondary px-2 py-1">${item.records_count}</span>
                </td>
                <td class="text-center text-nowrap">
                    <a href="${taskUrl}" target="_blank" class="btn btn-sm btn-outline-primary" title="Abrir tarea en Bitrix24">
                        <i class="fa-solid fa-arrow-up-right-from-square"></i>
                    </a>
                </td>
            </tr>
        `;
    });

    tbody.innerHTML = html;
}

// 2. Tabla de Detalle Línea por Línea
function filterDetailTable() {
    const q = removeAccents(document.getElementById("searchTable").value);
    const tbody = document.getElementById("tableDetailBody");

    let filtered = appState.records || [];

    // Filtro por selección múltiple de colaboradores (comparación segura como texto)
    if (appState.selectedUserIds && appState.selectedUserIds.length > 0) {
        const selSet = new Set(appState.selectedUserIds.map(id => String(id).trim()));
        filtered = filtered.filter(r => selSet.has(String(r.USER_ID).trim()));
    }

    if (q) {
        filtered = filtered.filter(r => 
            removeAccents(r.TASK_TITLE || "").includes(q) ||
            removeAccents(r.USER_NAME || "").includes(q) ||
            removeAccents(r.COMMENT_TEXT || "").includes(q) ||
            removeAccents(r.GROUP_NAME || "").includes(q)
        );
    }

    if (filtered.length === 0) {
        tbody.innerHTML = `
            <tr>
                <td colspan="7" class="text-center py-5 text-muted">
                    <i class="fa-regular fa-folder-open fa-2x mb-2 text-secondary opacity-50"></i>
                    <p class="mb-0">No se encontraron registros de tiempo con los filtros seleccionados.</p>
                </td>
            </tr>
        `;
        return;
    }

    let html = '';
    filtered.forEach(r => {
        const comment = r.COMMENT_TEXT ? r.COMMENT_TEXT : '<span class="text-muted fst-italic">Sin comentario</span>';
        const taskUrl = `${BITRIX_DOMAIN}/company/personal/user/${r.USER_ID}/tasks/task/view/${r.TASK_ID}/`;

        let cDate = String(r.CREATED_DATE || '').replace('T', ' ');
        let datePart = cDate.split(' ')[0] || '';
        let timePart = (cDate.split(' ')[1] || '').substring(0, 8);

        html += `
            <tr>
                <td class="ps-4 text-nowrap">
                    <div class="fw-semibold text-dark">${datePart}</div>
                    <small class="text-muted">${timePart}</small>
                </td>
                <td class="text-nowrap">
                    <div class="fw-semibold text-dark">${r.USER_NAME}</div>
                    <small class="text-muted">${r.USER_POSITION || 'Colaborador'}</small>
                </td>
                <td>
                    <div class="fw-semibold text-dark text-truncate" style="max-width: 350px;" title="${r.TASK_TITLE}">
                        ${r.TASK_TITLE}
                    </div>
                    <small class="text-muted">ID: #${r.TASK_ID}</small>
                </td>
                <td>
                    <span class="badge bg-light text-dark border">${r.GROUP_NAME || 'General'}</span>
                </td>
                <td class="text-center text-nowrap">
                    <span class="time-badge">${r.HOURS_FORMATTED}</span>
                    <div class="text-muted" style="font-size: 0.72rem;">${r.HOURS_DECIMAL} hrs</div>
                </td>
                <td style="max-width: 300px;">
                    <div class="text-secondary small text-truncate" title="${r.COMMENT_TEXT || ''}">
                        ${comment}
                    </div>
                </td>
                <td class="text-center text-nowrap">
                    <a href="${taskUrl}" target="_blank" class="btn btn-sm btn-outline-primary" title="Abrir tarea en Bitrix24">
                        <i class="fa-solid fa-arrow-up-right-from-square"></i>
                    </a>
                </td>
            </tr>
        `;
    });

    tbody.innerHTML = html;
}

// Renderizar Gráficos con Chart.js
function renderCharts(usersSummary, records) {
    const chartsRow = document.getElementById("chartsRow");
    chartsRow.style.display = "flex";

    // 1. Gráfico de Barras: Horas por Colaborador
    const topUsers = usersSummary.slice(0, 10);
    const userLabels = topUsers.map(u => u.name);
    const userData = topUsers.map(u => u.hours_decimal);

    if (appState.charts.usersBar) {
        appState.charts.usersBar.destroy();
    }

    const ctxBar = document.getElementById("chartUsersBar").getContext("2d");
    appState.charts.usersBar = new Chart(ctxBar, {
        type: 'bar',
        data: {
            labels: userLabels,
            datasets: [{
                label: 'Horas Trabajadas',
                data: userData,
                backgroundColor: '#0076fe',
                borderRadius: 6
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { display: false },
                tooltip: {
                    callbacks: {
                        label: (ctx) => `${ctx.parsed.y} horas registradas`
                    }
                }
            },
            scales: {
                y: {
                    beginAtZero: true,
                    title: { display: true, text: 'Horas' }
                },
                x: {
                    ticks: {
                        maxRotation: 45,
                        minRotation: 0,
                        font: { size: 10 }
                    }
                }
            }
        }
    });

    // 2. Gráfico Donut: Horas por Proyecto / Grupo
    const projectHours = {};
    records.forEach(r => {
        const group = r.GROUP_NAME || 'General';
        projectHours[group] = (projectHours[group] || 0) + (r.SECONDS / 3600);
    });

    const projectLabels = Object.keys(projectHours);
    const projectData = Object.values(projectHours).map(v => Math.round(v * 10) / 10);

    if (appState.charts.projectsDoughnut) {
        appState.charts.projectsDoughnut.destroy();
    }

    const ctxDoughnut = document.getElementById("chartProjectsDoughnut").getContext("2d");
    appState.charts.projectsDoughnut = new Chart(ctxDoughnut, {
        type: 'doughnut',
        data: {
            labels: projectLabels,
            datasets: [{
                data: projectData,
                backgroundColor: [
                    '#0076fe', '#10b981', '#f59e0b', '#8b5cf6', '#ec4899', '#06b6d4', '#64748b'
                ]
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    position: 'bottom',
                    labels: { boxWidth: 12, font: { size: 11 } }
                }
            }
        }
    });
}

// Exportar a Excel para Nómina
async function exportToExcel() {
    if (!appState.records || appState.records.length === 0) {
        alert("No hay registros para exportar.");
        return;
    }

    const dateFrom = document.getElementById("dateFrom").value;
    const dateTo = document.getElementById("dateTo").value;
    const exportBtn = document.getElementById("btnExportar");

    exportBtn.disabled = true;
    exportBtn.innerHTML = `<span class="spinner-border spinner-border-sm me-1"></span> Generando...`;

    let recordsToExport = appState.records;
    let taskSummaryToExport = appState.taskUserSummary;
    let usersSummaryToExport = appState.usersSummary;

    if (appState.selectedUserIds.length > 0) {
        recordsToExport = recordsToExport.filter(r => appState.selectedUserIds.includes(r.USER_ID));
        taskSummaryToExport = taskSummaryToExport.filter(tu => appState.selectedUserIds.includes(tu.user_id));
        usersSummaryToExport = usersSummaryToExport.filter(u => appState.selectedUserIds.includes(u.user_id));
    }

    try {
        const response = await fetch("/api/export", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                records: recordsToExport,
                task_user_summary: taskSummaryToExport,
                users_summary: usersSummaryToExport,
                date_from: dateFrom,
                date_to: dateTo
            })
        });

        if (!response.ok) throw new Error("Error al exportar");

        const blob = await response.blob();
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = url;
        a.download = `Reporte_Nomina_Bitrix24_${dateFrom}_al_${dateTo}.xlsx`;
        document.body.appendChild(a);
        a.click();
        window.URL.revokeObjectURL(url);
        a.remove();
    } catch (err) {
        console.error("Error al exportar:", err);
        alert("Ocurrió un error al generar el archivo Excel de Nómina.");
    } finally {
        exportBtn.disabled = false;
        exportBtn.innerHTML = `<i class="fa-solid fa-file-excel me-1"></i> Exportar`;
    }
}
