# OpenCode Model Manager

![](https://blogger.googleusercontent.com/img/b/R29vZ2xl/AVvXsEisuFUVre-MOxXm1lfvA_mEhp3GC8rcQ93U0N4E1erQ-1kmtIpbNgMbyebyA3SM38NTUuPfAOlmeXF9Fr5RNx2G4cHsWLrjC6wYngr27xBvPOKXzf8RTwnwXrUYT4v2nMLHhyphenhyphenMGBGXPCD-X3gA4QN-MxP8re58d9lEOZ5Srd-satUhSblTyae3uIWr1FlM/s1600-rw/Portada.jpg)

GUI en **Python / PyQt6** para administrar proveedores y modelos de
[OpenCode](https://opencode.ai/) editando gráficamente el archivo
`opencode.json`: agregar y eliminar modelos, renombrarlos, cambiar el
proveedor, elegir el modelo predeterminado (`model`) y `small_model`,
con copia de seguridad automática antes de cada guardado.

**Este programa no solicita ni almacena API keys.** OpenCode guarda las
credenciales de `/connect` por separado (en `auth.json`), y esta
herramienta nunca las lee, muestra ni modifica: puedes cambiar los
modelos sin volver a introducir la clave.

---

## Características

- Edita `opencode.json` sin tocar `~/.local/share/opencode/auth.json`.
- Modo **global por defecto**: trabaja sobre
  `~/.config/opencode/opencode.json`; con el checkbox **Modo global**
  (persistente entre sesiones) alternas al `opencode.json` del
  repositorio actual.
- Cambia el ID y el nombre visible de cualquier modelo.
- Agrega y elimina modelos; edita el nombre visible del proveedor.
- Selecciona el modelo predeterminado (`model`) y `small_model`.
- Conserva propiedades adicionales de cada modelo
  (`limit`, `options`, `variants`, etc.).
- Copia de seguridad automática (`.backup`) antes de guardar y botón de
  respaldo manual a `opencode-backups/`.
- **Checkbox LSP**: activa o desactiva los servidores LSP de OpenCode
  (clave `"lsp"` de `opencode.json`). Antes de activarlo comprueba si
  el servidor del lenguaje está instalado (para Python: **pyright**) y
  si falta, advierte con el comando de instalación: sin él, OpenCode
  seguirá mostrando *LSP* como desactivado.
- Recuerda el tamaño y la posición de la ventana entre sesiones
  (reencuadrada al monitor para que nunca salga de la pantalla).
- Normaliza automáticamente la clave antigua `providers` a `provider`
  (formato estable de OpenCode) al cargar, avisando con un diálogo.
- Detección automática de la configuración local:
  `OPENCODE_CONFIG` → `./opencode.json` → búsqueda hacia arriba en un
  repositorio git → `~/.config/opencode/opencode.json`.

---

## Requisitos e instalación

Necesitas **Python 3** y **PyQt6**:

```bash
pip install PyQt6
```

Y para ejecutar:

```bash
python3 opencode_model_manager.py
```

### Servidor LSP para Python (recomendado)

Si quieres que OpenCode tenga autocompletado, análisis de tipos y
diagnósticos sobre tus archivos Python, instala también **pyright**:

```bash
npm install -g pyright
```

Comprueba que quedó en el `PATH`:

```bash
pyright --version
command -v pyright
```

> **Nota:** si instalaste paquetes globales de npm en tu HOME (con
> `npm config set prefix ~/.local/npm`), el binario queda en
> `~/.local/npm/bin` — asegúrate de que ese directorio esté en tu
> `PATH`, igual que para `opencode`.

---

## Activar LSP en OpenCode (checkbox LSP)

OpenCode puede trabajar con servidores LSP (*Language Server
Protocol*) para analizar tu código mientras el agente lo edita. Si
ves el mensaje `LSPs are disabled` en OpenCode, es porque la clave
`"lsp"` no está activada en tu `opencode.json`.

Con esta GUI es un clic: marca el checkbox **LSP** (junto a **Modo
global**) y se escribe y guarda `"lsp": true` al instante:

```json
{
  "$schema": "https://opencode.ai/config.json",
  "lsp": true,
  "provider": {
    "bai": { "...": "..." }
  }
}
```

Al marcarlo, la herramienta comprueba si el servidor del lenguaje
está instalado en el `PATH`:

- **Si está instalado** (p. ej. `pyright`): guarda y listo — al
  reiniciar, OpenCode mostrará `LSPs will activate as files are read`.
- **Si falta**: guarda `"lsp": true` igualmente, pero muestra un
  aviso con el comando de instalación y explica que **OpenCode
  seguirá mostrando LSP como desactivado** hasta que lo instales y
  reinicies OpenCode:

  ```text
  Servidor LSP no encontrado
  ─────────────────────────
  LSP se guardará como activado, pero falta el servidor del lenguaje
  en el PATH...
    • pyright  →  npm install -g pyright
  ```

Al desmarcar el checkbox, la clave `"lsp"` se elimina del archivo.

---

## ¿Para qué sirve? Contexto: OpenCode + B.AI gratis

Esta herramienta nació como acompañamiento del tutorial
**«Cómo instalar OpenCode en Linux y Termux y usar gratis (tiempo
limitado): DeepSeek V4 Flash y Hy3 mediante B.AI»**, que está incluido
en este repositorio:

- 📄 [OpenCode en Linux y Termux y usar gratis DeepSeek V4 Flash y Hy3 mediante B.AI.md](<OpenCode en Linux y Termux y usar gratis DeepSeek V4 Flash y Hy3 mediante B.AI.md>)

En ese tutorial se configura [B.AI](https://chat.b.ai/) como proveedor
de OpenCode para usar **gratis (promoción de tiempo limitado)** los
modelos `deepseek-v4-flash` (contexto de 1 millón de tokens) e `hy3`.
La configuración resultante en `opencode.json` es la que esta GUI edita
cómodamente:

```json
{
  "$schema": "https://opencode.ai/config.json",
  "provider": {
    "bai": {
      "npm": "@ai-sdk/openai-compatible",
      "name": "B.AI",
      "options": {
        "baseURL": "https://api.b.ai/v1"
      },
      "models": {
        "deepseek-v4-flash": {
          "name": "DeepSeek V4 Flash (B.AI)"
        },
        "hy3": {
          "name": "Hy3 (B.AI)"
        }
      }
    }
  }
}
```

El flujo completo es (como ejemplo ya que caducan con frecuencia y aparecen otras):

```
Linux o Android/Termux
        │
        ▼
     OpenCode        (/connect guarda la API key aparte, en auth.json)
        │
        ▼
@ai-sdk/openai-compatible
        │
        ▼
 https://api.b.ai/v1
        │
        ▼
       B.AI
      ╱    ╲
     ▼      ▼
DeepSeek   Hy3
V4 Flash
```

**Resumen del flujo de trabajo:**

1. Instala OpenCode (en Linux o en Android vía
   [Termux](https://github.com/guysoft/opencode-termux)).
2. Crea tu API key en `https://chat.b.ai/key`.
3. Dentro de OpenCode ejecuta `/connect`, elige **Other** y usa el ID
   de proveedor `bai` pegando ahí tu API key.
4. Crea `opencode.json` con el contenido de arriba — o mejor: usa esta
   GUI, que lo hace gráficamente.
5. Dentro de OpenCode, elige el modelo con `/models`.

> **Importante:** las promociones son temporales. Revisa periódicamente
> el apartado **Usage** de B.AI para comprobar el consumo de tu cuenta.

---

## Modo global vs modo de repositorio

| Modo | Archivo que se edita | Cuándo usarlo |
|---|---|---|
| **Global** (por defecto) | `~/.config/opencode/opencode.json` | Configuración válida para todos tus proyectos |
| **Repositorio** | `./opencode.json` del proyecto (o el que se detecte) | Configuración específica de un proyecto, versionable con git |

- Al primer arranque el checkbox **Modo global** aparece marcado; si
  desmarcas, se detecta automáticamente la configuración del
  repositorio actual y la preferencia queda guardada para las próximas
  sesiones.
- Si el archivo no existe, la aplicación ofrece crear uno básico.
- También puedes abrir cualquier `opencode.json` con el botón
  **Abrir opencode.json…** (`Ctrl+O`).

---

## Migración automática `providers` → `provider`

Si tu `opencode.json` usa la clave antigua `providers`, al cargarlo la
aplicación la migra a `provider` (formato estable de OpenCode) y te
avisa con un diálogo:

- Si solo existe `providers`, se renombra a `provider`.
- Si existen ambas, se fusionan **sin sobrescribir** lo que ya esté en
  `provider`, y se elimina `providers`.

El cambio se hace en memoria; se escribe al disco cuando guardas.

---

## Tests

La suite de tests corre headless (sin PyQt6 instalado, sin ventanas y
sin tocar tu QSettings real) gracias a un stub de Qt incluido en
`tests/qt_stub.py`:

```bash
python3 -m unittest discover -s tests -v
```

Cubre la migración `providers` → `provider`, el modo global (valor por
defecto, alternancia y persistencia), el checkbox LSP (escritura y
borrado de la clave `"lsp"`, detección de `pyright` en el `PATH` con
y sin él instalado), la persistencia de geometría de ventana y
restricciones transversales (por ejemplo, que `auth.json` jamás es
accesado por el código).

---

## Enlaces

- Tutorial completo (incluido en este repo):
  [OpenCode en Linux y Termux y usar gratis DeepSeek V4 Flash y Hy3 mediante B.AI](<OpenCode en Linux y Termux y usar gratis DeepSeek V4 Flash y Hy3 mediante B.AI.md>)
- OpenCode: <https://opencode.ai/> · Documentación:
  <https://opencode.ai/docs/>
- B.AI: <https://chat.b.ai/> · API key:
  <https://chat.b.ai/key>
- Port realizado con este flujo de trabajo (OpenCode + DeepSeek V4
  Flash): <https://github.com/wachin/TBO>
