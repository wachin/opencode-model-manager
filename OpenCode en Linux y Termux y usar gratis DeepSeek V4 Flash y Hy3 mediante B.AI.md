![](https://blogger.googleusercontent.com/img/b/R29vZ2xl/AVvXsEisuFUVre-MOxXm1lfvA_mEhp3GC8rcQ93U0N4E1erQ-1kmtIpbNgMbyebyA3SM38NTUuPfAOlmeXF9Fr5RNx2G4cHsWLrjC6wYngr27xBvPOKXzf8RTwnwXrUYT4v2nMLHhyphenhyphenMGBGXPCD-X3gA4QN-MxP8re58d9lEOZ5Srd-satUhSblTyae3uIWr1FlM/s1600-rw/Portada.jpg)

# Cómo instalar OpenCode en Linux y Termux y usar gratis (tiempo limitado): "DeepSeek V4 Flash" y "Hy3" mediante B.AI

OpenCode es un agente de inteligencia artificial para programación que funciona directamente desde la terminal. A diferencia de un chatbot convencional, puede examinar los archivos de un proyecto, modificar código, ejecutar comandos y ayudarnos en tareas de desarrollo de software.

En este tutorial veremos cómo:

- instalar OpenCode en Linux;
- instalar OpenCode en Android mediante Termux;
- obtener una API key de B.AI;
- aprovechar las promociones de tiempo limitado de **DeepSeek V4 Flash** y **Hy3**;
- configurar B.AI como proveedor de OpenCode;
- y consultar todos los demás modelos de inteligencia artificial disponibles en B.AI en caso de que posteriormente se quiera utilizar el servicio de pago.

> **Importante:** las promociones pueden cambiar. Al momento de escribir este tutorial, B.AI muestra **DeepSeek V4 Flash** y **Hy3** como *Limited-Time Free*. La documentación de B.AI indica expresamente que la promoción de DeepSeek V4 Flash se aplica al Chat y a la API a **0 Credits**. Antes de comenzar un trabajo grande conviene revisar el apartado **Usage** de B.AI para comprobar el consumo efectivo de la cuenta y confirmar que la promoción elegida continúa vigente

---

## 1. Requisitos

Necesitamos:

- **Node.js** (versión 22.19 o superior, o 24+). Si no lo tienes, instálalo desde el repositorio de NodeSource (instrucciones detalladas en [Cómo instalar node en Linux](https://facilitarelsoftwarelibre.blogspot.com/2026/08/como-instalar-nodejs-24-en-ubuntu-debian-etc.html)):

```bash
sudo apt update
sudo apt-get install -y curl
curl -fsSL https://deb.nodesource.com/setup_24.x | sudo -E bash -
sudo apt-get install -y nodejs
```

Comprueba la versión con:

```bash
node --version
```

> **Nota sobre permisos de npm:** si al instalar paquetes globales (`npm install -g ...`) aparece un error `EACCES: permission directed`, no modifiques los permisos de `/usr/lib`. En su lugar, configura las instalaciones globales en tu HOME:
>
> ```bash
> mkdir -p ~/.local/npm
> npm config set prefix ~/.local/npm
> echo 'export PATH="$HOME/.local/npm/bin:$PATH"' >> ~/.bashrc
> source ~/.bashrc
> ```

- **pnpm** (un gestor de dependencias). Si no lo tienes instálalo mediante npm:

```bash
sudo npm install -g pnpm
```

- **git**, para clonar el repositorio:

```bash
sudo apt install -y git
```

> **Ojo:** el paquete `dsh` que hay en `apt` **no es DeepSeek Harness**. Es un programa antiguo de Linux llamado *Distributed Shell*. Si lo instalas por error, no pasa nada, pero no sirve para lo que queremos. Para desinstalarlo si lo instalaste sin querer:
>
> ```bash
> sudo apt remove dsh libdshconfig1
> ```

---

# 1. Instalar OpenCode en Linux

OpenCode puede instalarse de varias maneras

[https://opencode.ai/](https://opencode.ai/)

![](https://blogger.googleusercontent.com/img/b/R29vZ2xl/AVvXsEj00S4b-8gUky48d7y6SvOd-W8AjDm0DAohVaLuKCuLlfWWx0-SWueqr4-Ivk58hyphenhyphen1NpEjDGK14yp8oxPLajOKND5MukorWmWKhpbEXPGg6rvjByUy4LgXorLaZ_PGPOaBHFREA7eIhY-vnnrY7GuFWhdqPR9UaexB57pVBkjV0mF38XhT9eX_y_hWibwU/s1033/opencode.ai.png)

Dispone de un instalador oficial:

```bash
curl -fsSL https://opencode.ai/install | bash
```


---

# 2. Instalar OpenCode en Android mediante Termux

La situación es diferente en Android.

Termux proporciona un entorno Linux sobre Android, pero Android utiliza Bionic como biblioteca C del sistema y existen otras diferencias respecto de una distribución GNU/Linux convencional.

Por este motivo existe el proyecto comunitario **opencode-termux**, que construye OpenCode específicamente para Android/Termux sobre arquitectura ARM64 (`aarch64`). El proyecto recompila componentes necesarios para que OpenCode pueda ejecutarse nativamente en este entorno.

Proyecto:

**guysoft/opencode-termux**

[https://github.com/guysoft/opencode-termux](https://github.com/guysoft/opencode-termux)

## Comprobar la arquitectura

En Termux:

```bash
uname -m
```

Para utilizar estos paquetes debe aparecer:

```
aarch64
```

## Actualizar Termux

```bash
pkg update && pkg upgrade
```

Instalar las herramientas necesarias:

```bash
pkg install curl ripgrep
```

## Descargar OpenCode para Termux

Es recomendable consultar primero las releases del proyecto:

[https://github.com/guysoft/opencode-termux/releases](https://github.com/guysoft/opencode-termux/releases)

Por ejemplo, una versión comprobada es OpenCode 1.17.9 para Android/Termux aarch64, publicada como release `v0.2.1`.

Puede descargarse así:

```bash
cd ~
curl -LO https://github.com/guysoft/opencode-termux/releases/download/v0.2.1/opencode_1.17.9_aarch64.deb
```

Comprobar el archivo:

```bash
ls -lh opencode_1.17.9_aarch64.deb
```

A continuación instalarlo:

```bash
dpkg -i opencode_1.17.9_aarch64.deb
```

Y asegurarse de que `ripgrep` esté instalado:

```bash
pkg install ripgrep
```

Finalmente:

```bash
opencode --version
```

Para iniciarlo:

```bash
opencode
```

El proyecto `opencode-termux` también ofrece otros formatos de instalación, incluyendo un ejecutable independiente y paquetes para Pacman.

> **Nota:** OpenCode evoluciona rápidamente. Antes de instalarlo en Termux conviene consultar la página de Releases y utilizar la versión más reciente compatible, en lugar de asumir que el número de versión mostrado en este tutorial continúa siendo el último.

---

# 3. ¿Qué es B.AI?

B.AI proporciona acceso mediante una misma API a diferentes modelos de inteligencia artificial.

Una ventaja especialmente interesante es que su API utiliza una interfaz compatible con el formato de OpenAI, lo que permite conectarla a aplicaciones que admiten proveedores personalizados, entre ellas OpenCode.

La dirección base que utilizaremos será:

```
https://api.b.ai/v1
```

---

# 4. Crear una API key de B.AI

Primero debemos crear una cuenta en B.AI.

```
https://chat.b.ai/
```

Luego de crearla podremos observar las promociones disponibles, por ejemplo:

"DeepSeek V4 Flash: Limited-Time Free"

"Hy3: Limited-Time Free"

![](https://blogger.googleusercontent.com/img/b/R29vZ2xl/AVvXsEjy8XOMBijyuiCvupyySXk-XAj3dqm173xqV5Kp-HitTlNRqILBnUMKC0ZBb01b8R2hbH5I13Qgag89adsVvc-ODRbCFB06_71rB0BA5YsMN3-Gff4YOAi-0iyJoYud0BitoGo12jeEwNDFgqrzGP0-TpYLVEqJ86apNI__ie5P-CtjSAyeIttAzV1GcMM/s1116/chat.b.ai_chat.png)

Después entramos en:

```
https://chat.b.ai/key
```

![](https://blogger.googleusercontent.com/img/b/R29vZ2xl/AVvXsEglgpgH8WMLxpRx0xYPLh3Wob4E0LRFaddoZFl-X6ouhF-EtM1uSVU3EuQFX8pmuY48TZ-x9YsJBptLiuKszp2hlBb7z1xacbDIPLrKTRDgQ1RFbIAoW874N7RlzRVlOK-LSvT-MKjeLMbAH1CaL4EzH0CT3JU8vDFHj051u_hqIercpBxlz-VID1d-jck/s1184/chat.b.ai_key.png)

Desde allí creamos una nueva API key.

La clave tendrá un aspecto parecido a:

```
sk-xxxxxxxxxxxxxxxxxxxxxxxx
```

Debemos copiarla y guardarla en un lugar seguro.

## ⚠️ No publicar la API key

Una API key funciona de manera parecida a una contraseña.

No debemos:

- publicarla en GitHub;
- incluirla en capturas de pantalla;
- escribirla en tutoriales;
- enviarla a otras personas;
- ni guardarla directamente dentro del código de nuestros programas.

En los ejemplos de este tutorial utilizaremos:

```
TU_API_KEY
```

El usuario debe reemplazarlo localmente por su verdadera clave.

---

# 5. DeepSeek V4 Flash gratis mediante B.AI

Esta es la parte más interesante del tutorial.

B.AI inició el **17 de agosto de 2026** una promoción para:

```
DeepSeek-V4-Flash
```

Durante esta promoción, su utilización mediante B.AI Chat y mediante la API se factura a:

```
0 Credits
```

Según B.AI, durante la promoción no se cobran los tokens de entrada, salida, escritura de caché ni lectura de caché.

Esto resulta especialmente interesante para programas como OpenCode, porque un agente de programación puede realizar numerosas peticiones mientras:

- examina archivos;
- estudia un proyecto;
- modifica código;
- ejecuta comandos;
- analiza errores;
- y continúa trabajando sobre los resultados.

DeepSeek V4 Flash está además orientado a tareas de programación y uso mediante agentes. Dispone de soporte para llamadas a herramientas (*tool/function calling*) y una ventana de contexto de hasta **1 millón de tokens**.

La promoción es temporal. B.AI indica que, cuando termine, el modelo volverá a su precio normal.

---


## 5.1. DeepSeek V4 Flash vs Hy3: ¿cuál utilizar?

B.AI muestra actualmente dos modelos con la indicación **Limited-Time Free**:

- **DeepSeek V4 Flash**
- **Hy3**

Los dos resultan interesantes para utilizar OpenCode como agente de programación, pero tienen características diferentes.

| Característica | DeepSeek V4 Flash | Hy3 |
|---|---|---|
| Programación | Sí, muy orientado a código | Sí, orientado a agentes de programación |
| Uso como agente | Sí | Sí |
| Tool / Function Calling | Sí | Sí |
| Contexto máximo | **1.000.000 tokens** | **256.000 tokens** |
| Entrada máxima publicada | — | **192.000 tokens** |
| Salida máxima | **384.000 tokens** | **128.000 tokens** |
| Multimodal | No, solo texto | No, solo texto |
| Trabajo con repositorios | Sí | Sí |
| Tareas de varios pasos | Sí | Sí |
| ID del modelo en B.AI | `deepseek-v4-flash` | `hy3` |

### ¿Cuál conviene utilizar en OpenCode?

Para proyectos grandes, **DeepSeek V4 Flash tiene una ventaja muy importante: su ventana de contexto de 1 millón de tokens**. Esto puede ser útil cuando OpenCode necesita mantener en contexto una gran cantidad de código, archivos y resultados obtenidos durante el trabajo.

**Hy3**, por su parte, está orientado al trabajo mediante agentes de ingeniería de software y resulta apropiado para tareas de programación que requieren planificación, utilización repetida de herramientas, modificación de código, depuración y trabajo de varios pasos.

Una estrategia práctica es tener **ambos configurados** y cambiar de uno a otro desde OpenCode mediante:

```text
/models
```

Así podemos probarlos con nuestros propios proyectos y decidir cuál obtiene mejores resultados en cada situación.

## 5.2. Comprobar el consumo en B.AI

Aunque estemos utilizando un modelo que aparece bajo una promoción gratuita, es recomendable comprobar periódicamente el consumo de nuestra cuenta.

Entramos en B.AI y en el menú lateral seleccionamos:

```text
Usage
```

Desde allí podemos revisar el uso realizado por nuestra cuenta.

Esto es especialmente recomendable porque las promociones son temporales y pueden cambiar. Además, que un modelo aparezca al consultar `/v1/models` significa que está disponible en el catálogo de la API, **no necesariamente que su utilización sea gratuita**.

Por esta razón, antes de comenzar un trabajo grande con OpenCode conviene comprobar que el modelo elegido continúa incluido en la promoción y revisar posteriormente el apartado **Usage**.

# 6. Conectar B.AI con OpenCode

Iniciamos OpenCode:

```bash
opencode
```

Dentro de OpenCode escribimos:

```
/connect
```

Buscamos la opción para agregar otro proveedor, normalmente:

```
Other
```

Cuando OpenCode solicite un identificador para el proveedor escribimos:

```
bai
```

Cuando solicite la API key, pegamos la clave que obtuvimos anteriormente.

OpenCode almacena sus credenciales separadamente, por lo que **no es necesario escribir nuestra API key directamente dentro de `opencode.json`**.

---

# 7. Configurar DeepSeek V4 Flash y Hy3

Ahora debemos indicarle a OpenCode dónde se encuentra la API de B.AI y qué modelo queremos utilizar.

Dentro del directorio del proyecto debemos crear:

```bash
gedit opencode.json
```

Pegamos lo siguiente para que OpenCode reconozca los modelos **DeepSeek V4 Flash (B.AI)** y **Hy3 (B.AI)**:

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
        "deepseek-v4-flash-vision-exp": {
          "name": "DeepSeek V4 Flash Vision Exp (B.AI)"
        }
      }
    }
  }
}
```

Guardamos 

Hay un detalle muy importante.

El identificador:

```
bai
```

debe coincidir con el identificador utilizado anteriormente al ejecutar `/connect`.

---

# 8. Iniciar OpenCode y seleccionar DeepSeek V4 Flash o DeepSeek V4 Flash Vision Exp

Entramos al directorio de nuestro proyecto:

```bash
cd MiProyecto
```

Ejecutamos:

```bash
opencode
```

Dentro de OpenCode podemos abrir la selección de modelos con:

```
/models
```

Allí buscamos:

```
B.AI
```

Debería aparecer:

```
DeepSeek V4 Flash (B.AI)
DeepSeek V4 Flash Vision Exp (B.AI)
```

Seleccionamos el modelo que queramos utilizar.

A partir de ese momento podemos pedirle tareas como:

```
Analiza este proyecto y explícame su arquitectura antes de realizar modificaciones.
```

O, por ejemplo:

```
Continúa con el port de este programa a PyQt6. Primero revisa el estado actual del proyecto y los cambios ya realizados antes de modificar archivos.
```

OpenCode podrá utilizar los agentes que estén disponibles como agente para inspeccionar, modificar y trabajar sobre nuestro proyecto. Podemos cambiar de modelo posteriormente mediante `/models`.

---

# 9. Comprobar directamente que la API funciona

También podemos comprobar la API desde la terminal sin utilizar OpenCode.

Usamos para el modelo "deepseek-v4-flash":

```bash
curl -X POST "https://api.b.ai/v1/chat/completions" \
  -H "Authorization: Bearer TU_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "deepseek-v4-flash",
    "messages": [
      {
        "role": "user",
        "content": "Hello World"
      }
    ],
    "stream": false,
    "max_tokens": 1000
  }'
```

Debemos sustituir:

```
`TU_API_KEY`
```

por nuestra verdadera API key.

Si recibimos una respuesta generada por el modelo, la API está funcionando correctamente.

---

# 10. ¿Qué ocurre con GPT, Claude, Gemini y los demás modelos?

B.AI no solamente ofrece DeepSeek

Su API proporciona acceso a numerosos modelos pertenecientes a diferentes familias, entre ellas:

- GPT;
- Claude;
- Gemini;
- DeepSeek;
- GLM;
- Kimi;
- Qwen;
- MiniMax;
- MiMo.

Pero hay que tener cuidado con algo:

> **Que un modelo aparezca disponible en la API no significa que sea gratuito.**

Algunos modelos requieren disponer de saldo o realizar un depósito.

Por ejemplo, si intentamos utilizar un modelo premium sin cumplir los requisitos de la cuenta, B.AI puede responder con un mensaje parecido a:

```
Access restricted. Deposit required to unlock premium models.
```

En este tutorial hemos configurado los dos modelos que B.AI muestra actualmente con la indicación **Limited-Time Free**:

```text
deepseek-v4-flash
deepseek-v4-flash Vision Exp
```

Sin embargo, debemos recordar que estas promociones son temporales. Antes de utilizar cualquiera de estos modelos conviene comprobar en la página de B.AI si la promoción continúa vigente y revisar el apartado **Usage** para verificar el consumo de Credits.

Los demás modelos que aparezcan al consultar la API no deben considerarse gratuitos simplemente porque aparezcan en la lista. Algunos tienen un precio por tokens y otros pueden requerir saldo o un depósito previo para poder utilizarlos.

---

# 11. Ver todas las inteligencias artificiales disponibles en B.AI

Si posteriormente queremos comprar Credits o simplemente queremos conocer los modelos que B.AI tiene disponibles mediante nuestra API, podemos consultarlos directamente.

Primero instalamos `jq`.

## En Debian, Ubuntu y derivados

```bash
sudo apt install jq
```

## En Termux

```bash
pkg install jq
```

Después ejecutamos:

```bash
curl -s "https://api.b.ai/v1/models" \
  -H "Authorization: Bearer TU_API_KEY" |
jq -r '.data[].id'
```

Sustituimos `TU_API_KEY` por nuestra clave.

Obtendremos una lista parecida a:

```
minimax-m3
minimax-m2.7
glm-5.1
glm-5.2
gpt-5.6-sol
gpt-5.6-terra
gpt-5.6-luna
gpt-5.5
gpt-5.4
gpt-5.2
claude-opus-5
claude-sonnet-5
claude-sonnet-4.6
gemini-3.1-pro
gemini-3.6-flash
kimi-k2.6
glm-5.3
kimi-k3
qwen3.8-max
deepseek-v4-flash
deepseek-v4-flash-vision-exp
deepseek-v4-pro
qwen3.8-27b
mimo-v2.5
mimo-v2.5-pro
```

La lista puede cambiar con el tiempo, por lo que **es preferible utilizar el comando anterior en lugar de depender de una lista escrita en un tutorial**.

---

# 12. Consultar los modelos sin `jq`

Si no queremos instalar `jq`, también podemos consultar directamente la respuesta JSON:

```bash
curl -s "https://api.b.ai/v1/models" \
  -H "Authorization: Bearer TU_API_KEY"
```

La información será menos cómoda de leer, pero mostrará los modelos que la API tiene disponibles.

---

# 13. Agregar posteriormente otros modelos a OpenCode

Supongamos que en el futuro decidimos utilizar el servicio de pago y queremos agregar otros modelos.

Podemos ampliar la sección `"models"` de nuestro `opencode.json`.

Por ejemplo, de lo que devolvió el comando anterior he hecho una lista que deseo probar:

deepseek-v4-flash
glm-5.3
qwen3.8-max
claude-sonnet-5
gpt-5.6-sol

Con esta lista podemos crear una configuración como la siguiente. También podemos pedir a una IA que nos ayude a preparar el bloque de configuración:

```json
"models": {
  "deepseek-v4-flash": {
    "name": "DeepSeek V4 Flash (B.AI)"
  },
  "glm-5.3": {
    "name": "GLM 5.3 (B.AI)"
  },
  "qwen3.8-max": {
    "name": "Qwen 3.8 Max (B.AI)"
  },
  "claude-sonnet-5": {
    "name": "Claude Sonnet 5 (B.AI)"
  },
  "gpt-5.6-sol": {
    "name": "GPT-5.6 Sol (B.AI)"
  }
}
```

Antes de utilizar modelos de pago conviene consultar siempre los precios actuales de B.AI, porque cada modelo puede tener precios diferentes para tokens de entrada, salida y caché.

---

# 14. ¿Por qué DeepSeek V4 Flash y Hy3 resultan interesantes para OpenCode?

Para un agente de programación no solamente importa que el modelo pueda generar código.

OpenCode necesita que el modelo pueda participar en un ciclo como este:

```
Usuario
   ↓
OpenCode
   ↓
B.AI
   ↓
DeepSeek V4 Flash / Hy3
   ↓
Analiza el proyecto
   ↓
Solicita ejecutar una herramienta
   ↓
OpenCode ejecuta el comando
   ↓
Devuelve el resultado al modelo
   ↓
El modelo analiza el resultado
   ↓
Modifica archivos, ejecuta pruebas
o realiza otra acción
```

DeepSeek V4 Flash y Hy3 admiten *tool calling* y están preparados para tareas de programación y trabajo mediante agentes. DeepSeek V4 Flash destaca además por su ventana de contexto de hasta 1 millón de tokens.

Esto permite utilizarlo no solamente para preguntas sencillas, sino también para trabajar como agente sobre proyectos de software.

---

# 15. Resumen

La configuración que hemos realizado queda de la siguiente manera:

```
Linux o Android/Termux
        │
        ▼
     OpenCode
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

De esta manera podemos utilizar OpenCode desde Linux o incluso desde un teléfono Android mediante Termux y conectarlo con DeepSeek V4 Flash o Hy3 utilizando la API de B.AI. Desde `/models` podemos cambiar entre los modelos que hayamos configurado.

La promoción documentada de DeepSeek V4 Flash comenzó el **17 de agosto de 2026** y B.AI indica que es temporal. B.AI también muestra Hy3 como **Limited-Time Free** en su interfaz. Por ello conviene comprobar el estado de ambas promociones y el apartado **Usage** antes de seguir este tutorial en el futuro.

Mientras la promoción permanezca activa, resulta una oportunidad especialmente interesante para quienes desarrollan software libre, mantienen proyectos grandes o quieren experimentar con agentes de programación sin consumir rápidamente créditos de servicios comerciales.

## Enlaces oficiales

**OpenCode:**

```
https://opencode.ai/
```

**Documentación de OpenCode:**

```
https://opencode.ai/docs/
```

**B.AI:**

```
https://chat.b.ai/
```

**Crear/administrar la API key de B.AI:**

```
https://chat.b.ai/key
```

**Documentación de la API de B.AI:**

```
https://docs.b.ai/llmservice/api/
```

**Información de DeepSeek V4 Flash en B.AI:**

```
https://docs.b.ai/llmservice/models/deepseek-v4-flash/
```

**Información de Hy3 en B.AI:**

```
https://docs.b.ai/llmservice/models/hy3/
```

**Promociones y cambios de precios de B.AI:**

```
https://docs.b.ai/llmservice/promotions-and-pricing-notices/
```

---

# 16. Caso real: el port de TBO a Python/PyQt6

Este tutorial se escribió a partir de un proyecto real que permite comparar la
experiencia práctica con los dos modelos promocionados.

El proyecto es **TBO**, un editor de cómics originalmente escrito en **C y GTK 3**
(abandonado desde 2013). Se reimplementó por completo en **Python/PyQt6**,
conservando compatibilidad con el formato histórico `.tbo`, añadiendo una
biblioteca de recursos, deshacer/rehacer, exportación PNG/PDF/SVG, traducciones
(inglés/español) y empaquetado para Debian.

Repositorio del port:

```
https://github.com/wachin/TBO
```

La experiencia con cada modelo fue la siguiente:

### Hy3

Se configuró el modelo `hy3` y se utilizó en OpenCode para iniciar el trabajo.
Durante esta prueba **solo fue posible realizar y enviar 3 commits**; a partir de
ese punto el agente devolvió un mensaje indicando que ya no se podía continuar
(hasta allí llegaba lo permitido). Con Hy3 no se pudo avanzar con el port.

### DeepSeek V4 Flash

Con el modelo `deepseek-v4-flash` se **completó el port completo de TBO a
PyQt6**, incluyendo:

- la reimplementación del modelo de documento y del lector/escritor `.tbo`;
- el lienzo interactivo y los comandos de deshacer/rehacer;
- la biblioteca de recursos (Doodles, Character, Accessories, Bubbles);
- la edición de texto y los iconos;
- la exportación a PNG, PDF y SVG;
- las traducciones con Qt Linguist;
- el empaquetado `.deb` y los flujos de CI;
- y la reorganización final del repositorio (código legacy bajo `legacy/`).

Este tutorial y los archivos de este repositorio fueron generados con **DeepSeek
V4 Flash** mediante B.AI, en OpenCode.

En resumen, en este caso real **Hy3 quedó limitado a unos pocos commits**, mientras
que **DeepSeek V4 Flash permitió terminar el proyecto completo**. Por ello, para
trabajos largos o de varias sesiones, DeepSeek V4 Flash resultó la opción más
fiable de las dos promociones vigentes en el momento de escribir este tutorial.

> Recuerda: las promociones son temporales. Antes de comenzar un trabajo grande
> conviene comprobar en B.AI que el modelo elegido sigue incluido en la promoción
> y revisar el apartado **Usage** durante el trabajo.

---

Dios les bendiga