# Scrap Mantaras - Poder Judicial de la Nación

Script desarrollado en Python utilizando Playwright para automatizar la extracción de expedientes desde el Sistema de Consulta Web del Poder Judicial de la Nación (PJN).

Actualmente permite:

- Obtener la lista de expedientes del usuario logueado.
- Ingresar automáticamente al detalle de cada expediente.
- Obtener el último movimiento desde:
  - Actuaciones actuales.
  - Actuaciones históricas (cuando no existen actuaciones actuales).
- Exportar los resultados a Excel y CSV.
- Guardar el progreso de forma incremental.
- Evitar volver a procesar expedientes ya exportados.

---

# Requisitos

- Python 3.14+
- Google Chrome
- uv
- Playwright

---

# Instalación

Crear el entorno virtual:

```powershell
uv venv
```

Activarlo:

```powershell
.venv\Scripts\activate
```

Instalar dependencias:

```powershell
uv pip install -r requirements.txt
```

Instalar Chromium para Playwright:

```powershell
python -m playwright install chromium
```

---

# Ejecutar Chrome en modo Debug

El script se conecta a una instancia existente de Google Chrome utilizando el protocolo CDP.

Abrir Chrome con:

```powershell
& "C:\Program Files\Google\Chrome\Application\chrome.exe" `
--remote-debugging-port=9222 `
--user-data-dir="C:\dev\chrome-pjn-debug"
```

---

# Navegación

Una vez abierto Chrome:

1. Ir a:

https://pjn.gob.ar/gestion-judicial

2. Seleccionar:

```
Consultas y Gestión de Causas
```

3. Ingresar a:

```
Gestión Causas
```

4. Iniciar sesión.

5. Entrar en:

```
Mis Expedientes
```

6. Dejar abierta la pantalla:

```
Lista de Expedientes Relacionados
```

---

# Ejecutar el scraper

Con el entorno virtual activo:

```powershell
python main.py
```

El programa preguntará:

```
Número de pestaña con Lista de Expedientes Relacionados:
```

Ingresar el número correspondiente.

---

# Archivos generados

El script genera:

```
expedientes_pjn_detalle.xlsx
expedientes_pjn_detalle.csv
```

Los datos se guardan de forma incremental.

Si el archivo ya existe:

- No elimina la información existente.
- No vuelve a procesar expedientes ya exportados.

---

# Estado actual

Implementado:

- Lectura de expedientes.
- Navegación automática.
- Extracción del último movimiento.
- Consulta de actuaciones históricas.
- Exportación a Excel.
- Guardado incremental.
- Paginación.

Pendiente:

- Mejor manejo de errores.
- Recuperación automática de sesión.
- Detección automática de la pestaña correcta.
- Eliminación de pausas fijas mediante esperas inteligentes.