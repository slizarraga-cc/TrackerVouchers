## ✅ Tarea completada — 2 PDFs descargados

**PDF 1:** Transferencia a otros bancos locales - Diferida | N° 02020082 | $510,006.00
**PDF 2:** Autodesembolso - Financiamiento | N° D00004742168 | $200,000.00

---

# 📋 DOCUMENTACIÓN DE FLUJO AUTOMATIZADO
## Estado de Operaciones — Descarga de PDFs (Telecrédito BCP)

---

### 🔗 URL DIRECTA
```
https://www.tlcbcp.com/#/h/bandeja-consulta
```
> Navegar directamente a esta URL evita tener que expandir el menú lateral manualmente.

---

### PASO 1 — Navegar a "Estado de operaciones"

**Método rápido (JS click):**
```javascript
// Selector del submenú "Estado de operaciones"
const menuOp = document.querySelectorAll('#target-sidebar bcp-menu-option-sidebar');
const consultaOpEl = menuOp[7]; // "Consulta de operaciones" (índice 7, base 0)
const subOptions = consultaOpEl.querySelectorAll('bcp-menu-suboption-sidebar');
for (let sub of subOptions) {
  if (sub.textContent.trim() === 'Estado de operaciones') {
    sub.querySelector('.ms-child').click();
    break;
  }
}
```

| Elemento | XPath | Alternativa |
|----------|-------|-------------|
| Menú "Consulta de operaciones" | `//*[@id="target-sidebar"]/bcp-menu-option-sidebar[8]/div/div[1]` | JS: `querySelectorAll('bcp-menu-option-sidebar')[7]` |
| Submenú "Estado de operaciones" | `//*[@id="target-sidebar"]/bcp-menu-option-sidebar[8]/div/div[2]/bcp-menu-suboption-sidebar[2]/div/div[1]/bcp-paragraph/p` | JS: buscar por texto `.ms-child` |

---

### PASO 2 — Ingresar rango de fechas y buscar

| Elemento | ID / Selector | XPath |
|----------|--------------|-------|
| Campo **"Desde"** | `id="bcp-input-consult-tray-6"` / `name="inputDateFrom"` | `//*[@id="bcp-input-consult-tray-6"]` |
| Campo **"Hasta"** | `id="bcp-input-consult-tray-7"` / `name="inputDateTo"` | `//*[@id="bcp-input-consult-tray-7"]` |
| Botón **"Buscar"** | `class="bcp-ffw-btn bcp-ffw-btn-primary bcp-ffw-btn-lg bcp-ffw-btn-block"` | `...bcp-button-consult-tray/button` |

**Código rápido:**
```javascript
// Ingresar fecha y ejecutar búsqueda
document.getElementById('bcp-input-consult-tray-6').value = '22/04/2026';
document.getElementById('bcp-input-consult-tray-6').dispatchEvent(new Event('input', {bubbles:true}));
document.getElementById('bcp-input-consult-tray-7').value = '22/04/2026';
document.getElementById('bcp-input-consult-tray-7').dispatchEvent(new Event('input', {bubbles:true}));

// Hacer clic en Buscar
document.querySelector('button.bcp-ffw-btn-primary').click();
```
> ⚠️ Los IDs de campos (`bcp-input-consult-tray-6` y `7`) pueden cambiar entre sesiones. Verificar con `name="inputDateFrom"` / `name="inputDateTo"` como alternativa.

---

### PASO 3 — Hacer clic en una operación

| Elemento | Selector | XPath |
|----------|----------|-------|
| Fila 1 (div clickeable) | `bcp-table-row-consult-tray:nth-of-type(2) .row-hover-container` | `...bcp-table-row-consult-tray[2]/div` |
| Fila 2 (div clickeable) | `bcp-table-row-consult-tray:nth-of-type(3) .row-hover-container` | `...bcp-table-row-consult-tray[3]/div` |
| Fila N | `bcp-table-row-consult-tray:nth-of-type(N+1) .row-hover-container` | `...bcp-table-row-consult-tray[N+1]/div` |

**Código rápido:**
```javascript
// Abrir la operación N (comenzando desde 1)
function abrirOperacion(n) {
  const rows = document.querySelectorAll('bcp-table-row-consult-tray');
  const row = rows[n]; // rows[1]=primera, rows[2]=segunda...
  if (row) row.querySelector('.row-hover-container').click();
}
abrirOperacion(1); // Primera operación
```

---

### PASO 4 — Descargar PDF

| Elemento | Selector | XPath / Clase |
|----------|----------|--------------|
| Botón **"Descargar PDF"** (transferencias) | `button.bcp-ffw-btn-outline-primary` | `...lib-transfer-button-report[1]/.../button` |
| Botón **"Descargar PDF"** (FEC/créditos) | `button.bcp-ffw-btn-outline-primary` | `//*[@id="bcp-tab-0-body-1-2"]/app-payment-schedule-tab/...` |
| **API de descarga** | `GET https://apisux.ntlc.tlcbcp.com/ux-ntlc-transfer-operation-v2/channel/ntlc/v2/tra...` | — |

**Código rápido:**
```javascript
// Descargar PDF desde el detalle
const descargarBtn = Array.from(document.querySelectorAll('button'))
  .find(b => b.textContent.includes('Descargar PDF'));
if (descargarBtn) descargarBtn.click();
```

---

### PASO 5 — Volver a la lista

| Elemento | Selector | XPath |
|----------|----------|-------|
| Botón **"Volver"** (transferencias) | `a.bcp-ffw-btn.btn-text` | `...ntlc-button-return/bcp-button-4wdaaa/a` |
| Botón **"Volver"** (FEC/créditos) | `a.bcp-ffw-btn.btn-text` | `...app-return-button/bcp-button-fec-operation-detail/a` |

**Código rápido:**
```javascript
// Volver a la lista
const volverBtn = Array.from(document.querySelectorAll('a'))
  .find(a => a.textContent.includes('Volver'));
if (volverBtn) volverBtn.click();
```

---

### 🚀 FLUJO COMPLETO AUTOMATIZADO (para próxima sesión)

```javascript
// ============================================================
// FLUJO: Descarga de PDFs - Estado de Operaciones (TLC BCP)
// Fecha objetivo: pasar como parámetro DD/MM/YYYY
// ============================================================

async function descargarPDFsOperaciones(fecha = '22/04/2026', maxPDFs = 2) {
  
  // PASO 1: Navegar a Estado de operaciones
  window.location.hash = '#/h/bandeja-consulta';
  await esperar(2000);

  // PASO 2: Rellenar fechas
  await rellenarFecha('inputDateFrom', fecha);
  await rellenarFecha('inputDateTo', fecha);

  // PASO 3: Buscar
  document.querySelector('button.bcp-ffw-btn-primary').click();
  await esperar(2000);

  // PASO 4: Iterar por operaciones y descargar PDFs
  const rows = document.querySelectorAll('bcp-table-row-consult-tray');
  let descargados = 0;

  for (let i = 1; i < rows.length && descargados < maxPDFs; i++) {
    const rowDiv = rows[i].querySelector('.row-hover-container');
    if (rowDiv) {
      rowDiv.click();
      await esperar(2000);

      // Descargar PDF
      const pdfBtn = Array.from(document.querySelectorAll('button'))
        .find(b => b.textContent.includes('Descargar PDF'));
      if (pdfBtn) {
        pdfBtn.click();
        descargados++;
        await esperar(2000);
      }

      // Volver
      const volverBtn = Array.from(document.querySelectorAll('a'))
        .find(a => a.textContent.includes('Volver'));
      if (volverBtn) {
        volverBtn.click();
        await esperar(2000);
      }
    }
  }
  console.log(`✅ ${descargados} PDF(s) descargados`);
}

// Helpers
function esperar(ms) { return new Promise(r => setTimeout(r, ms)); }

function rellenarFecha(name, valor) {
  const input = document.querySelector(`input[name="${name}"]`);
  if (input) {
    input.value = valor;
    input.dispatchEvent(new Event('input', { bubbles: true }));
    input.dispatchEvent(new Event('change', { bubbles: true }));
  }
}

// Ejecutar:
// descargarPDFsOperaciones('22/04/2026', 2);
```

---

### 📝 Observaciones importantes

1. **Los IDs de campos** (`bcp-input-consult-tray-6/7`) pueden variar entre sesiones. Usar `name="inputDateFrom"` y `name="inputDateTo"` es más estable.
2. **El calendario** bloquea el botón Buscar visualmente — usar `button.click()` vía JS evita este problema.
3. **Los botones "Descargar PDF"** tienen XPaths distintos según el tipo de operación (transferencias vs FEC/créditos), pero todos comparten el selector `button.bcp-ffw-btn-outline-primary`.
4. **La API de descarga** es: `apisux.ntlc.tlcbcp.com/ux-ntlc-transfer-operation-v2` (GET).
5. **Navegación directa** por hash `#/h/bandeja-consulta` es el método más rápido para llegar a Estado de operaciones.


-------------------------------------------------------------------------------------
Ve a la opción consulta de operaciones --> estado de operaciones, luego ingresa el rango de fecha (22/04/2026), después clic en buscar. Luego clic en cada operación y clic en descargar PDF. Después, clic en volver y realizar el mismo paso para cada operación, solo descarga máximo 2 pdf's. 

Al finalizar, crea un flujo para que en una segunda acción puedas realizarlo más rápido y fácil.
En cada  acción que tomes dentro de la página quiero que puedas obtener el código fuente y anotar los Xpath o identificadores de los elementos los cuales se clickean o presionan. A estos identificadores quiero que los guardes en la documentación de flujos.