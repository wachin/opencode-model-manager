# OpenCode API Manager

![](https://blogger.googleusercontent.com/img/b/R29vZ2xl/AVvXsEisuFUVre-MOxXm1lfvA_mEhp3GC8rcQ93U0N4E1erQ-1kmtIpbNgMbyebyA3SM38NTUuPfAOlmeXF9Fr5RNx2G4cHsWLrjC6wYngr27xBvPOKXzf8RTwnwXrUYT4v2nMLHhyphenhyphenMGBGXPCD-X3gA4QN-MxP8re58d9lEOZ5Srd-satUhSblTyae3uIWr1FlM/s1600-rw/Portada.jpg)

GUI en **Python / PyQt6** para descubrir, comparar y registrar modelos de
[OpenCode](https://opencode.ai/). Trabaja sobre dos capas separadas:

1. **El catálogo** — proveedores y modelos con su protocolo, endpoint,
   ventana de contexto, salida máxima, modalidades, capacidades y
   precios. Se alimenta de [Models.dev](https://models.dev) (MIT) con una
   semilla local y caché en disco, y **no forma parte de tu
   configuración**.
2. **`opencode.json`** — lo que OpenCode lee. Ahí solo se escribe lo que
   tú registras: agregar y eliminar modelos y proveedores, renombrarlos,
   cambiar el ID real (`modelID`), los límites (`limit`), el modelo
   predeterminado (`model`) y `small_model`, con copia de seguridad
   automática antes de cada guardado.

**Este programa no solicita ni almacena API keys.** OpenCode guarda las
credenciales de `/connect` por separado (en `auth.json`), y esta
herramienta nunca las lee, muestra ni modifica: puedes cambiar los
modelos sin volver a introducir la clave. Buscar en el catálogo
**tampoco** escribe nada: un modelo llega a `opencode.json` solo cuando
pulsas **Agregar a OpenCode**.

---

## Características

- **Catálogo separado de la configuración**: datos de modelos sin tocar
  tu `opencode.json` y sin instalar nada.
- **Fuentes y procedencia visibles**: semilla local + Models.dev (MIT),
  con fecha de última actualización; sin red sigues navegando desde la
  caché.
- **Búsqueda instantánea** sobre nombres, IDs, `modelID`, endpoint,
  descripción y etiquetas — funciona **plegues o despliegues** el árbol,
  porque filtra los datos, no los widgets.
- **Filtros combinables** (ámbito, protocolo, locales y nueve chips) con
  contador de coincidencias, botón de limpiar, ordenes y panel plegable.
- **Árbol proveedor → modelo a la derecha**: estrecho, alfabético,
  **todo plegado por defecto**, hijos cargados al expandir, indicador de
  cuántos modelos hay y diferencia clara entre registrado (`●`/`✓`) y
  solo-catalogo.
- **Ficha de modelo sin datos inventados**: lo desconocido se etiqueta
  `Desconocido`, `Sin datos de precio` o `Solo en catálogo (no
  registrado)`.
- **Siete acciones reales** en la ficha: Agregar a OpenCode, Editar,
  Fijar como predeterminado (`model`), Fijar como modelo ligero
  (`small_model`), Copiar ID, Copiar endpoint y Quitar de OpenCode.
- **Alta de proveedor personalizado** asistida, con pestaña *Importar
  JSON* que valida antes de aceptar nada.
- Edita `opencode.json` sin tocar `~/.local/share/opencode/auth.json`.
- Modo **global por defecto**: trabaja sobre
  `~/.config/opencode/opencode.json`; con el checkbox **Modo global**
  (persistente entre sesiones) alternas al `opencode.json` del
  repositorio actual.
- Cambia el ID y el nombre visible de cualquier modelo.
- Conserva propiedades adicionales de cada modelo
  (`limit`, `options`, `variants`, etc.).
- Copia de seguridad automática (`.backup`) antes de guardar, respaldos
  fechados en `opencode-backups/` y botón de respaldo manual.
- **Guardado atómico** (temporal + `fsync` + `os.replace`), validación
  previa y **detección de cambios externos**: si alguien editó el archivo
  desde tu última carga, pregunta antes de sobrescribir.
- **Checkbox LSP**: activa o desactiva los servidores LSP de OpenCode
  (clave `"lsp"` de `opencode.json`). Antes de activarlo comprueba si
  el servidor del lenguaje está instalado (para Python: **pyright**) y
  si falta, advierte con el comando de instalación: sin él, OpenCode
  seguirá mostrando *LSP* como desactivado.
- **Tema auto → claro → oscuro** (el botón **Tema** del encabezado). Se
  aplican las dos capas —la hoja de estilos y la `QPalette` de la
  aplicación—, así que popups de combos, diálogos, cuadros de mensaje y
  texto desactivado siguen el tema en lugar del tema del escritorio. El
  modo **auto** detecta si tu escritorio es oscuro leyendo la paleta del
  *estilo* (nunca la propia, para no realimentarse). Los contrastes están
  medidos en los tests: texto ≥ 7:1 y texto atenuado ≥ 4.5:1 sobre todas
  las superficies, en los dos temas.
- Recuerda tamaño, posición, el ancho del árbol y el tema entre sesiones
  (la ventana se reencuadra al monitor para que nunca salga de la
  pantalla).
- Normaliza automáticamente la clave antigua `providers` a `provider`
  (formato estable de OpenCode) al cargar, avisando con un diálogo.
- Detección automática de la configuración local:
  `OPENCODE_CONFIG` → `./opencode.json` → búsqueda hacia arriba en un
  repositorio git → `~/.config/opencode/opencode.json`.
- La red **nunca** bloquea la interfaz: descargar y parsear el catálogo
  ocurre en un `QThread`, y el resultado llega por señal ya completo.

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

## Interfaz

Tres zonas, con `QSplitter` entre el espacio de trabajo y el árbol:

```
┌──────────────────────────────────────────────────────────────────┐
│ Cabecera: título · archivo · búsqueda · Filtros · acciones       │
├───────────────────────────────────────┬──────────────────────────┤
│ Espacio de trabajo (3 páginas)        │ Árbol (derecha)          │
│  · Resumen de configuración           │  ● Acme AI  (3)          │
│  · Resultados de búsqueda/filtros     │    ✓ Acme Coder          │
│  · Ficha del modelo seleccionado      │    ✓ Acme Legacy         │
│                                       │      Acme Lite           │
│                                       │  Zeta Labs  (1)          │
└───────────────────────────────────────┴──────────────────────────┘
```

- **Cabecera**: nombre de la app, ruta del `opencode.json` activo,
  búsqueda con debounce de 160 ms, botón **Filtros** (plegable), orden,
  contador de coincidencias y los botones de acción (Abrir, Recargar,
  Refrescar catálogo, +Proveedor, +Modelo, Vista previa, Tema, Copiar
  archivo, Guardar).
- **Árbol de proveedores** (columna derecha, arrastrable entre 210 y
  560 px): orden alfabético, **siempre plegado al arrancar y al
  reconstruir tras guardar**; los hijos se crean solo al expandir, así
  miles de modelos no cuestan nada. `●` y negrita = proveedor registrado
  en `opencode.json`; `✓` en verde = modelo ya registrado; sin marca =
  solo en el catálogo. El paréntesis es el número de modelos.
- **Ficha del modelo**: un clic en un resultado o en el árbol la rellena;
  si no hay coincidencias, la lista muestra el aviso «Sin coincidencias
  con esta búsqueda y filtros.» en lugar de quedarse hueca. La vista se
  recorta (hasta 300 filas) pero el contador dice siempre el total real.

---

## Catálogo de modelos

| Aspecto | Detalle |
|---|---|
| Fuente remota | `https://models.dev/api.json` (licencia **MIT**, sst/models.dev) |
| Semilla local | B.AI, Ollama, LM Studio, llama-server y OpenRouter |
| Caché en disco | `$XDG_CACHE_HOME/opencode-model-manager/models_dev.json` + `models_dev.meta.json` (con `fetched_at`, `source` y `license`) |
| Arranque | Un hilo carga la caché y publica el catálogo por señal; sin red, sigues navegando offline |
| Actualizar | Botón **Refrescar catálogo** o `Ctrl+Shift+R` (descarga y reescribe la caché) |
| Procedencia | Cada proveedor/modelo indica `seed`, `models.dev`, `config` o `cache`; Models.dev gana sobre la semilla |

Reglas que el código cumple y los tests exigen:

- Para **mostrar** el catálogo no se descargan ni se ejecutan paquetes
  npm ni código de proveedores: solo se lee JSON.
- La petición es `urllib` anónima con `Accept-Encoding: gzip`: **sin
  credenciales**, sin claves en cabeceras ni en argumentos.
- Ninguna entrada se escribe en `opencode.json` por aparecer en los
  resultados: hay que registrarla.
- De un modelo del catálogo solo se copian a la configuración los campos
  fiables (`name`, `modelID`, `limit`, `cost`, `modalities` y las
  capacidades declaradas); si el JSON de origen trae algo parecido a una
  clave, no llega al archivo.

---

## Búsqueda y filtros

La búsqueda recorre: nombre del modelo y del proveedor, ID de modelo,
`modelID`, ID de proveedor, endpoint/`baseURL`, descripción, familia,
tipo y modalidades.

| Grupo | Opciones |
|---|---|
| Ámbito | Todos · Registrados en OpenCode · Sin registrar |
| Protocolo | Cualquier protocolo · OpenAI-compatible · OpenAI · Anthropic · Google · Otros |
| Ubicación | Casilla **Locales** (Ollama, LM Studio, llama.cpp…) |
| Modelo (chips) | Gratis · De pago · Nivel gratis · Código · Razonamiento · Visión · Tool calling · Multimodal · Contexto ≥ 200k |
| Orden | A → Z · Proveedor · Contexto · Precio, con botón ↑↓ para invertir |

- **Todos los mandos aplican al instante**: cada combo, cada casilla y
  cada chip dispara la búsqueda por sí solo; no hay que pulsar nada más.
- **«Otros»** incluye los protocolos no listados (Bedrock, Azure u otros
  SDK), no solo los que se llaman literalmente `other`.
- **Contexto** ordena de mayor a menor por defecto; los modelos con
  contexto desconocido quedan siempre al final. **Precio** ordena por
  coste combinado entrada/salida, con `Gratis` como 0 y los sin precio
  al final.
- Un modelo **no** se marca como multimodal o con visión si el catálogo
  no declara sus modalidades: preferimos `Desconocido` a adivinar.

---

## Ficha del modelo: cero datos inventados

| Campo | Sin datos |
|---|---|
| Ventana de contexto / Salida máxima | `Desconocido` |
| Tool calling · Razonamiento · Visión · Streaming · Modalidades | `Desconocido` |
| Precio | `Sin datos de precio` (o `Gratis` si es 0/0) |
| Estado en OpenCode | `Registrado` o `Solo en catálogo (no registrado)` |

La fila **API / Base URL** usa el `baseURL` de tu configuración cuando
existe; solo si el proveedor no está registrado muestra el endpoint del
catálogo.

**Quitar de OpenCode** borra la entrada de `opencode.json` (con
confirmación) pero deja intacta la del catálogo, así que puedes volver a
registrarla cuando quieras.

---

## Registrar un proveedor personalizado

Botón **+ Proveedor**: diálogo con dos pestañas.

1. **Formulario** — ID del proveedor (debe coincidir con el que usaste
   en `/connect`), nombre visible, Base URL, protocolo, `npm` del AI SDK,
   variable de entorno de autenticación, cabeceras personalizadas
   (`Key: value` por línea) y modelos inicial(es).
2. **Importar JSON** — pega el bloque de `opencode.json`, el objeto del
   proveedor suelto (con `"id"`) o una lista, pulsa **Validar** y, si es
   correcto, **Aplicar al formulario**.

La validación rechaza ID ausente, Base URL que no sea `http(s)` válido,
nombre vacío, cabeceras mal formadas, claves desconocidas y modelos sin
ID, y muestra el motivo exacto en rojo antes de dejar aceptar. La
autenticación se deja siempre en `/connect` o en la variable de entorno
indicada: **el formulario no tiene campo de API key**.

Al registrar un modelo del catálogo se conserva lo que ya estuviera
escrito a mano (`modelID`, `options`, `variants`, límites personalizados)
y solo se añaden los datos nuevos.

---

## Atajos de teclado

| Tecla | Acción |
|---|---|
| `Ctrl+F` | Enfocar la búsqueda |
| `Ctrl+R` | Recargar el `opencode.json` actual |
| `Ctrl+Shift+R` | Refrescar el catálogo desde Models.dev |
| `Ctrl+S` | Guardar (valida, respalda y escribe de forma atómica) |
| `Ctrl+O` | Abrir un `opencode.json` concreto |
| `Esc` | 1º limpia búsqueda **y filtros** · 2º pliega el panel de filtros |
| `Enter` (en resultados) | Abrir la ficha del modelo resaltado |
| `Supr` | Quitar de OpenCode, con confirmación |

---

## Credenciales y seguridad

Lo que este proyecto garantiza y comprueba en los tests:

- **Nunca** se lee ni se escribe `~/.local/share/opencode/auth.json`; un
  test compara sus bytes antes y después de todo el flujo (buscar,
  filtrar, registrar, fijar predeterminado, guardar) y exige que sigan
  idénticos.
- **Nunca** se muestra ni se almacena una API key en el catálogo, en la
  caché, en la vista previa ni en `opencode.json`.
- Las credenciales se gestionan con variables de entorno (`env`) y con
  `/connect`. No existe ninguna función de gestión de claves; cualquier
  añadido futuro sería opcional y con autorización explícita del usuario.
- Ninguna clave se pasa por línea de órdenes y ninguna credencial se
  envía a un proveedor de catálogo.
- URLs y datos importados se validan antes de aceptarse; la escritura es
  atómica y **no sobrescribe en silencio**: siempre hay respaldo y aviso
  si el archivo cambió por fuera.
- No se descargan ni ejecutan scripts o paquetes npm automáticamente.

---

## Guarda, respaldo y detección de cambios externos

Al pulsar **Guardar**:

1. Se valida la estructura (`$schema`, `provider`, `models`, `model`,
   `small_model`, `lsp`) y se comprueba que el JSON resultante sea
   correcto.
2. Si el archivo cambió desde tu última carga, se pregunta si
   sobrescribir o recargar — nunca se pisa sin avisar.
3. Se crea `opencode.json.backup` y una copia fechada
   `opencode-backups/opencode_AAAAMMDD_HHMMSS_micros.backup.json` (con
   microsegundos para que dos guardados seguidos no colisionen).
4. Se escribe en un temporal, se hace `fsync` y se reemplaza con
   `os.replace`, de modo que un corte no deja el archivo a medias.

**Ningún mando escribe por sí solo.** Agregar un modelo, editar, fijar
`model`/`small_model`, quitar un modelo o **quitar un proveedor** se
aplican en memoria y se anuncian en la barra de estado. Mientras algo esté
pendiente, el botón se lee **`Guardar ●`** —con el aviso «hay cambios sin
escribir en opencode.json» al pasar el ratón— y al cerrar la ventana se
pregunta antes de perder los cambios. De ahí que al quitar un proveedor
su fila siga en el árbol: lo que se va es la marca `●` de registrado, y el
nombre permanece porque viene del catálogo de Models.dev.

### Por qué «Quitar» está gris, y dónde sí se puede quitar

Cada fila del árbol sale de una de estas tres situaciones, y la ficha lo
dice con la misma frase en el tooltip de la fila, en una fila visible
llamada **Desde esta ventana** (por si el tooltip de un botón apagado no
llega a verse) y en los propios botones:

| Situación | Qué se ve | Qué hacer |
|---|---|---|
| Registrado en el archivo abierto | `●` en negrita y ficha con «Proveedor» | Editar y quitar funcionan aquí mismo |
| Registrado en **otro** `opencode.json` | Badge «Registrado en otro archivo» y la ruta exacta en el aviso | Abrir ese archivo con **Abrir…** o cambiar de modo |
| Solo fila del catálogo | Badge «Solo catálogo» y «no hay nada que editar ni quitar» | No se borra: es dato de Models.dev, no tu configuración |

El atajo `Supr` repite el aviso por la barra de estado, con la ruta del
archivo donde sí está, porque por teclado no hay botón gris que frene.

Para poder nombrar ese otro archivo la aplicación **lee** (solo lectura, al
cargar la configuración) los `opencode.json` estándar que no tiene abiertos:
el global, el del proyecto según `discover_config()` y el que señale
`OPENCODE_CONFIG`. Nunca lee `auth.json` ni ningún otro archivo, y una ruta
ilegible o un JSON roto se ignoran en silencio.

---

## Arquitectura del código

| Módulo | Responsabilidad |
|---|---|
| `omm/catalog.py` | Dataclasses `ProviderEntry`/`ModelEntry`, semilla, parser de Models.dev, caché con metadatos, procedencia, `adopt()` |
| `omm/search.py` | `Filters`, coincidencia de texto, filtros por ámbito/protocolo/chips y las cuatro ordenaciones |
| `omm/registry.py` | Frontera catálogo ↔ configuración: `add_catalog_model_to_config`, `add_provider_to_config`, eliminaciones, `tree_data`, `provider_union`, `model_detail_rows`, `action_note` (por qué un mando no actúa), validaciones |
| `omm/main_window.py` | Ventana, estado (datos, no widgets), señales entre paneles, flujo de guardado |
| `omm/ui/panels.py` | Cabecera, árbol perezoso, resultados (con aviso de vacío), filtros, ficha, resumen |
| `omm/ui/dialogs.py` | Diálogo de proveedor (formulario + importar JSON), de modelo y vista previa |
| `omm/workers.py` | `CatalogLoadWorker` (`QThread`): nunca muta el catálogo de la GUI, lo entrega por señal |
| `omm/theme.py` | Paletas claro/oscuro (con mapa de roles de `QPalette`) y QSS; sin dependencias de Qt |

El paquete se importa desde `opencode_model_manager.py`, que sigue siendo
el punto de entrada de siempre.

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
   GUI, busca `B.AI` en el catálogo, revisa el contexto real del modelo
   y regístralo con un clic.
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
  **Abrir…** (`Ctrl+O`).

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

```bash
python3 -m unittest discover -s tests -v
```

**267 tests** en dos capas, en menos de tres segundos:

- **Headless con stub** (`tests/qt_stub.py`): la lógica de ventana,
  paneles y diálogos corre sin PyQt6, sin ventanas y sin tocar tu
  `QSettings` real. Cubre catálogo (parser de Models.dev, semilla, caché,
  procedencia, offline), búsqueda y filtros (ámbitos, protocolos
  incluidos Bedrock/Azure, chips y ordenes), la frontera
  catálogo↔configuración (`tests/test_registry.py`), el tema
  (`tests/test_theme.py`: contrastes WCAG medidos, orden y cobertura del
  QSS —cada `objectName` y cada clase de widget tiene su superficie— y
  que `apply_theme()` publica paleta y hoja de estilos en la aplicación) y
  los flujos de ventana (`tests/test_flows.py`): árbol plegado por
  defecto, buscar con el árbol plegado, cada mando de filtro aplicando por
  sí solo, `Enter` para abrir la ficha, botón `small_model`, registro,
  retirada, guardado, recarga y atajos. Y el quite de proveedores
  completo (`TestProviderRemoval`): pide confirmación, deja el archivo
  intacto hasta Guardar, avisa en la barra, marca el botón con `●`,
  descarta el `model` que apuntaba a ese proveedor y, si el proveedor solo
  está en el catálogo, el botón apagado explica por qué. La procedencia de
  cada entrada la vigila `TestEntryOriginIsExplained`: el tooltip de la
  fila, la fila visible de la ficha, el botón apagado y el aviso de `Supr`
  dicen lo mismo, nombran el archivo concreto cuando la entrada vive en
  otro `opencode.json` (caso B.AI) y el badge deja de llamar «solo
  catálogo» a algo registrado fuera. Al escribir ese test apareció un
  agujero de aislamiento: con `OPENCODE_CONFIG` en el entorno, el fixture
  podía acabar leyendo el `opencode.json` real del usuario; ahora el
  `setUp` lo retira. También vigila la ficha: cada fila
  entra con `addLayout`, así que `item.widget()` es `None`; el stub ahora
  replica ese detalle (y el reparenteo que hace Qt) y comprueba que la
  tarjeta contiene exactamente dos etiquetas por fila, vista nueva o
  vista repetida. Las restricciones de seguridad
  también se prueban: `auth.json` idéntico byte a byte, ninguna clave
  escrita y buscar no registra nada.
- **Qt auténtico** (`tests/test_app_launch.py`): arranca la aplicación
  real con `QT_QPA_PLATFORM=offscreen` sobre un HOME temporal, bombea el
  bucle de eventos hasta que el `QThread` publica la caché y ejecuta
  buscar → filtrar → expandir → registrar → fijar `small_model` →
  guardar. Comprueba que el proceso termina sin trazas, que el archivo
  final es JSON válido y conserva lo previo, que quedó un respaldo, que
  no quedan `.tmp` y que `auth.json` no se tocó. Con `findChildren(QLabel)`
  sobre la tarjeta de la ficha mide, tras tres vistas consecutivas, que
  sólo quedan las etiquetas de la fila visible (éste es el defecto del
  texto duplicado que reportó el usuario: con Qt real las etiquetas sí son
  hijas de la tarjeta, y el stub las ignoraba). Con el mismo binario quita
  un proveedor registrado (respondiendo «Sí» a la pregunta) y comprueba
  que el aviso sale en la barra, que el botón pasa a `Guardar ●`, que
  `opencode.json` no se tocó y que al cerrar aparece «Cambios sin
  guardar». Con el mismo binario, y con un **segundo** `opencode.json`
  pasado por `OPENCODE_CONFIG`, lee `toolTip(0)` de las filas del árbol y
  de sus modelos: la fila registrada dice en qué archivo está, la que vive
  en el archivo ajeno nombra los dos y el badge pasa a «Registrado en otro
  archivo». También fuerza una
  **paleta de sistema oscura** y mide píxeles de la ventana pintada: el
  tema claro tiene que salir claro (cabecera, workspace, barra de estado y
  el panel de pestañas del diálogo) y el oscuro oscuro. Se omite solo si
  PyQt6 no está instalado.

Usa `discover` (añade `tests/` al `PYTHONPATH` para encontrar
`support.py`). La suite cubre además la migración `providers` →
`provider`, el modo global (valor por defecto, alternancia y
persistencia), el checkbox LSP (escritura y borrado de la clave `"lsp"`,
detección de `pyright` en el `PATH` con y sin él instalado) y la
persistencia de geometría de ventana.

---

## Enlaces

- Tutorial completo (incluido en este repo):
  [OpenCode en Linux y Termux y usar gratis DeepSeek V4 Flash y Hy3 mediante B.AI](<OpenCode en Linux y Termux y usar gratis DeepSeek V4 Flash y Hy3 mediante B.AI.md>)
- OpenCode: <https://opencode.ai/> · Documentación:
  <https://opencode.ai/docs/>
- Catálogo de proveedores y modelos: <https://models.dev> (MIT)
- B.AI: <https://chat.b.ai/> · API key:
  <https://chat.b.ai/key>
- Port realizado con este flujo de trabajo (OpenCode + DeepSeek V4
  Flash): <https://github.com/wachin/TBO>
