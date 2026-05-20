## ✅ Tarea completada — Documentación completa de selectores

Ambos PDFs fueron descargados exitosamente. A continuación la tabla de selectores y el resumen del flujo.

---

## 📋 Tabla de Selectores Recopilados

| # | Paso | Elemento | ID | Name | Clase CSS | XPath Absoluto (simplificado) | XPath Relativo Estable | Observaciones |
|---|------|----------|-----|------|-----------|-------------------------------|------------------------|---------------|
| 1 | Cerrar alerta fraude | Botón "Entendido" | — | — | `bcp-ffw-btn bcp-ffw-btn-primary` | `...dialog[1]/button[1]` | `//dialog//button[normalize-space(.)="Entendido"]` | Aparece en la primera carga de sesión como modal. **No siempre presente.** |
| 2 | Menú lateral: "Consulta de operaciones" | `<p>` (texto) / `<bcp-menu-option-sidebar>` (contenedor) | — | — | `paragraph-md bcp-font-demi white` | `.../bcp-menu-option-sidebar[8]/div[1]/div[1]` | `//bcp-menu-option-sidebar[.//p[normalize-space(text())="Consulta de operaciones"]]` | Web Component `bcp-menu-option-sidebar`. El índice `[8]` puede cambiar si se añaden ítems. Usar XPath relativo. |
| 3 | Submenú: "Estado de operaciones" | `<p>` (texto) / `<bcp-menu-suboption-sidebar>` | — | — | `paragraph-md bcp-font-demi white` | `.../bcp-menu-option-sidebar[8]/div[1]/div[2]/bcp-menu-suboption-sidebar[2]/...` | `//p[normalize-space(text())="Estado de operaciones"]` | Web Component `bcp-menu-suboption-sidebar`. El índice `[2]` es posición dentro del grupo desplegado. Verificar en cada sesión si el menú está expandido. |
| 4 | Campo "Desde" | `<input>` (nativo dentro de WC) | `bcp-input-consult-tray-1` | `inputDateFrom` | `bcp-ffw-form-control` | `.../bcp-input-consult-tray[1]/div[1]/input[1]` | `//*[@id="bcp-input-consult-tray-1"]` o `//input[@name="inputDateFrom"]` | **ID dinámico** con sufijo numérico (`-1`). El sufijo puede cambiar entre sesiones. Preferir `name="inputDateFrom"`. Requiere disparar eventos `input`/`change` manualmente. |
| 5 | Campo "Hasta" | `<input>` (nativo dentro de WC) | `bcp-input-consult-tray-2` | `inputDateTo` | `bcp-ffw-form-control` | `.../bcp-input-consult-tray[2]/div[1]/input[1]` | `//input[@name="inputDateTo"]` | Mismo patrón que "Desde". **ID dinámico**, usar `name="inputDateTo"`. El calendario emergente aparece al inyectar el valor; no requiere interacción adicional si se rellena con `form_input` + disparo de eventos. |
| 6 | Botón "Buscar" | `<button>` | — | — | `bcp-ffw-btn bcp-ffw-btn-primary bcp-ffw-btn-lg bcp-ffw-btn-block` | `.../bcp-button-consult-tray[1]/button[1]` | `//button[normalize-space(.)="Buscar"]` o `//bcp-button-consult-tray//button` | Sin ID. La clase `bcp-ffw-btn-primary` lo distingue del botón "Restablecer". Estable. |
| 7 | Fila 1 de tabla (op. 1) | `<bcp-table-row-consult-tray>` | — | — | `bcp-table-row-host-4-27-1 hydrated` | `.../bcp-table-consult-tray[1]/div[1]/div[3]/div[1]/bcp-table-row-consult-tray[2]` | `//bcp-table-row-consult-tray[@index="84068545"]` | Atributo `index` = código de solicitud de la operación. **Es el identificador más estable.** El índice posicional `[2]` (siendo `[1]` el header) puede variar por filtros/ordenamiento. La fila NO responde a `click()` del DOM nativo; usar `el.click()` por JavaScript programático. |
| 8 | Fila 2 de tabla (op. 2) | `<bcp-table-row-consult-tray>` | — | — | `bcp-table-row-host-4-27-1 hydrated` | `.../bcp-table-row-consult-tray[3]` | `//bcp-table-row-consult-tray[@index="84068414"]` | Mismo patrón que fila 1. **El atributo `index` es el código de solicitud.** Verificar que el ordenamiento por defecto sea cronológico descendente. |
| 9 | Botón "Descargar PDF" — Op. 1 (Transferencia) | `<button>` | — | — | `bcp-ffw-btn bcp-ffw-btn-outline-primary bcp-ffw-btn-block` | `.../lib-transfer-button-report[1]/lib-transfer-buttons-in-line[1]/div[1]/div[1]/bcp-button-ntlc-commons-widgets[1]/button[1]` | `//bcp-button-ntlc-commons-widgets//button[contains(., "Descargar PDF")]` | Parent WC: `BCP-BUTTON-NTLC-COMMONS-WIDGETS`. URL generada: GET `/ux-ntlc-transfer-operation-v2/.../transfer-operations/reports/{codigo}?reportType=CONSULT&transferType=TXDEFERRED`. Hay también botones "Constancia de operación" e "Imprimir PDF" en esta vista. |
| 10 | Botón "Volver" — Op. 1 | `<a>` | — | — | `bcp-ffw-btn btn-text bcp-ffw-btn-md` | `.../ntlc-button-return[1]/bcp-button-4wdaaa[1]/a[1]` | `//ntlc-button-return//a` | `href=""`. Navega por Angular Router. Estable mientras la estructura `ntlc-button-return > a` se mantenga. |
| 11 | Botón "Descargar PDF" — Op. 2 (Autodesembolso) | `<button>` | — | — | `bcp-ffw-btn bcp-ffw-btn-outline-primary bcp-ffw-btn-md` | `.../fec-button-export-pdf[1]/bcp-button-fec-operation-detail[1]/button[1]` | `//fec-button-export-pdf//button[contains(., "Descargar PDF")]` | Parent WC diferente: `BCP-BUTTON-FEC-OPERATION-DETAIL`. Vista con **tabs** (Información / Cronograma de pagos), cada tab tiene su propio botón "Descargar PDF". URL generada: POST `/ux-ntlc-credit-order-v5/.../financing-transactions/{codigo}/export`. **No hay botones "Constancia" ni "Imprimir PDF".** |
| 12 | Botón "Volver" — Op. 2 | `<a>` | — | — | `bcp-ffw-btn btn-text` | `.../ele-fec-operation-detail[1]/app-operation-detail[1]/div[1]/app-return-button[1]/bcp-button-fec-operation-detail[1]/a[1]` | `//app-return-button//a` | Clase CSS ligeramente diferente (`btn-text` sin `bcp-ffw-btn-md`). URL de retorno diferente: regresa a `#/h/bandeja-consulta`. |

---

## 🔄 Resumen del Flujo Optimizado

### Pasos verificados:

1. **Cerrar modal de alerta de fraude** (condicional): `//dialog//button[normalize-space(.)="Entendido"]`

2. **Expandir "Consulta de operaciones"** (clic en el Web Component):
   - `//bcp-menu-option-sidebar[.//p[normalize-space(text())="Consulta de operaciones"]]` → hacer `.click()` via JS

3. **Hacer clic en "Estado de operaciones"**:
   - `//p[normalize-space(text())="Estado de operaciones"]` → clic visual o `.click()` JS

4. **Ingresar fecha "Desde"**:
   - Selector: `//input[@name="inputDateFrom"]`
   - Método: `form_input` con valor `22/04/2026` + disparar eventos `input` y `change` por JS
   - El calendario se abre automáticamente; no requiere acción adicional si el campo "Hasta" también se rellena

5. **Ingresar fecha "Hasta"**:
   - Selector: `//input[@name="inputDateTo"]`
   - Método: igual que el campo "Desde"

6. **Hacer clic en "Buscar"**:
   - `//button[normalize-space(.)="Buscar"]`

7. **Abrir operación N** (clic programático obligatorio):
   - `document.querySelector('bcp-table-row-consult-tray[index="{codigo_solicitud}"]').click()`
   - **⚠️ IMPORTANTE**: El clic visual/ref no funciona. Solo funciona `el.click()` por JavaScript

8. **Descargar PDF** (según tipo de operación):
   - Transferencias: `//bcp-button-ntlc-commons-widgets//button[contains(., "Descargar PDF")]`
   - FEC/Autodesembolso: `//fec-button-export-pdf//button[contains(., "Descargar PDF")]`
   - En vista FEC hay 2 botones (uno por tab); usar el del tab activo "Información de operación"

9. **Volver a la lista**:
   - Transferencias: `//ntlc-button-return//a`
   - FEC/Autodesembolso: `//app-return-button//a`

---

## ⚠️ Selectores a re-verificar entre sesiones

| Selector | Estabilidad | Razón |
|----------|------------|-------|
| `//input[@name="inputDateFrom"]` | ✅ Alto | El `name` no cambia |
| `//input[@name="inputDateTo"]` | ✅ Alto | El `name` no cambia |
| `bcp-table-row-consult-tray[@index="N"]` | ✅ Alto | `index` = código de solicitud fijo |
| `//bcp-menu-option-sidebar[.//p[...]]` | ✅ Alto | Basado en texto visible |
| `bcp-input-consult-tray-1` (ID) | ⚠️ Bajo | El número puede cambiar entre deploys |
| `bcp-table-row-consult-tray[2]` (posición) | ⚠️ Bajo | Depende del ordenamiento activo |
| `bcp-menu-option-sidebar[8]` (índice posicional) | ⚠️ Bajo | Cambia si se agrega/quita un ítem del menú |
| Endpoints de descarga | ✅ Estable | Atados al código de solicitud (`84068545`, `84068414`) |