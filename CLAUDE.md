# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Environment Setup

This project uses **direnv** with a Python 3.13 virtualenv (`.direnv/python-3.13/`). The `.envrc` runs `layout python` automatically when entering the directory.

Install dependencies:
```bash
pip install -r requirements.txt
```

Required environment variables (`.env`):
- `SELENIUM_GRID_URL` — Selenium Grid endpoint (default: `http://localhost:4444`)
- `VNC_PASSWORD` — VNC password for the remote browser session

A Selenium Grid instance must be running before executing any flows. The driver connects to `$SELENIUM_GRID_URL/wd/hub` in remote mode, or falls back to a local ChromeDriver when `remote=False`.

## Architecture

```
src/
  core/
    driver.py        # get_driver(remote=True) — builds Chrome WebDriver
    base_flow.py     # BaseFlow ABC — Selenium helpers (waits, clicks, forms, nav)
  banks/
    bcp/
      selectors.py   # BCPSelectors — all XPath/CSS constants for tlcbcp.com
      flows/
        descarga_comprobantes.py  # DescargaComprobantes(BaseFlow)
downloads/           # PDFs land here (remote: /home/seluser/Downloads)
logs/                # Log output
manual/              # Selector documentation from exploratory sessions
```

### Core pattern

All bank flows extend `BaseFlow` and implement `ejecutar(**kwargs)`. `BaseFlow` provides:
- `esperar_elemento` / `esperar_clickeable` — explicit waits (XPath only)
- `click_js(element)` — JS click (required for BCP Web Components; native Selenium `.click()` does not work)
- `rellenar_fecha(name, valor)` — fills date inputs via JS `nativeInputValueSetter` + dispatches `input`/`change` events (required because Web Components ignore `.send_keys()`)

### BCP-specific notes

- **Target site:** `https://www.tlcbcp.com/#/h/bandeja-consulta` — navigate directly to avoid menu interaction
- **Web Components:** BCP uses custom elements (`bcp-table-row-consult-tray`, `bcp-button-ntlc-commons-widgets`, etc.). Only JS clicks work; native Selenium clicks are silently ignored.
- **Date input IDs are dynamic** (`bcp-input-consult-tray-N`); always use `name="inputDateFrom"` / `name="inputDateTo"`.
- **Table rows:** use the `index` attribute (`bcp-table-row-consult-tray[@index="N"]`) as the stable business identifier. Re-fetch rows after each navigation to avoid stale element references.
- **Two operation types** require different selectors:
  - Transferencias: `BTN_DESCARGAR_PDF_TRANSFER`, `BTN_VOLVER_TRANSFER`
  - FEC/Autodesembolso: `BTN_DESCARGAR_PDF_FEC`, `BTN_VOLVER_FEC`
  - Generic fallback exists for both

All selectors are centralized in `src/banks/bcp/selectors.py` with documented stability levels (ALTA/MEDIA/BAJA). Prefer ALTA selectors; avoid positional indices.

### Adding a new bank

1. Create `src/banks/{bank}/selectors.py` with a selectors class.
2. Create `src/banks/{bank}/flows/{flow_name}.py` extending `BaseFlow`.
3. Document selectors in `manual/` following the existing pattern.
