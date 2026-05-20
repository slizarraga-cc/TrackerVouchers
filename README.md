# RPA Bancos — Descarga de Comprobantes

Prototipo de automatizacion de descarga de comprobantes bancarios.
Actualmente soportado: **BCP Telecredito**.

---

## Requisitos

- Docker + Docker Compose
- Python 3.10+

---

## Setup inicial

```bash
# 1. Instalar dependencias Python
pip install -r requirements.txt

# 2. Copiar y configurar variables de entorno
cp .env.example .env
# Editar .env con credenciales si se desea auto-login

# 3. Levantar el browser en Docker
docker compose up -d

# 4. Verificar que el contenedor este listo
docker compose ps
```

---

## Uso

```bash
# Descargar PDFs del dia (maximo 2 por defecto)
python main.py ejecutar --banco bcp --fecha-desde 22/04/2026

# Descargar PDFs de un rango de fechas
python main.py ejecutar --banco bcp --fecha-desde 01/04/2026 --fecha-hasta 30/04/2026

# Cambiar el maximo de PDFs
python main.py ejecutar --banco bcp --fecha-desde 22/04/2026 --max-pdfs 10

# Usar Chrome local en vez de Docker (requiere chromedriver instalado)
python main.py ejecutar --banco bcp --fecha-desde 22/04/2026 --local
```

### Opciones disponibles

| Opcion | Default | Descripcion |
|--------|---------|-------------|
| `--banco` | `bcp` | Banco a procesar |
| `--fecha-desde` | requerido | Fecha inicio DD/MM/YYYY |
| `--fecha-hasta` | = fecha-desde | Fecha fin DD/MM/YYYY |
| `--max-pdfs` | `2` | Maximo de PDFs a descargar |
| `--local` | — | Usar Chrome local |
| `--remoto` | default | Usar Selenium Grid en Docker |

---

## Login (accion requerida)

El login es siempre manual por politicas de seguridad del banco.

1. Ejecuta `python main.py ejecutar ...`
2. Abre el visor en tu browser: **http://localhost:7900** (contrasena: `rpa123`)
3. Completa el login manualmente en la ventana del browser.
4. Presiona **ENTER** en la terminal para continuar.

---

## Donde se guardan los PDFs

Los PDFs se descargan en la carpeta `downloads/` del proyecto.
Esta carpeta esta mapeada como volumen al contenedor Docker.

---

## Estructura del proyecto

```
rpa-bancos/
├── docker-compose.yml          # Selenium Grid + Chrome + noVNC
├── .env.example                # Template de variables de entorno
├── requirements.txt
├── main.py                     # CLI de entrada
├── config/
│   └── banks/
│       └── bcp.yaml            # Configuracion BCP
├── downloads/                  # PDFs descargados
├── logs/                       # Logs de ejecucion
└── src/
    ├── core/
    │   ├── driver.py           # Setup del WebDriver
    │   └── base_flow.py        # Clase base con utilidades comunes
    └── banks/
        └── bcp/
            ├── selectors.py    # Todos los XPaths/selectores BCP
            ├── login.py        # Flujo de login BCP
            └── flows/
                └── descarga_comprobantes.py  # Flujo principal
```

### Agregar un nuevo banco

1. Crear `src/banks/{nuevo_banco}/`
2. Agregar `selectors.py`, `login.py`, y `flows/` siguiendo la estructura de BCP
3. Agregar `config/banks/{nuevo_banco}.yaml`
4. Registrar el banco en `main.py` (`BANCOS_DISPONIBLES` y `_ejecutar_{banco}`)

---

## Monitoreo

- **noVNC**: http://localhost:7900 — ver el browser en tiempo real
- **Selenium Grid UI**: http://localhost:4444/ui — estado del Grid
- **Logs**: carpeta `logs/rpa_YYYY-MM-DD.log`
