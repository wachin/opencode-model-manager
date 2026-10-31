# Background: OpenCode + free B.AI

[Back to the README](../README.md)

This tool started as a companion to a Spanish-language tutorial about
installing OpenCode on Linux and Termux and using DeepSeek V4 Flash and
Hy3 through B.AI for free during a limited-time promotion. That tutorial
is no longer part of this repository.

[B.AI](https://chat.b.ai/) can be configured as an OpenCode provider to
use the `deepseek-v4-flash` (1-million-token context) and `hy3` models
**for free (limited-time promotion)**. The resulting `opencode.json`
configuration is the one this GUI edits comfortably:

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

The full flow is (as an example, since promotions expire and new ones
appear):

```
Linux or Android/Termux
        │
        ▼
     OpenCode        (/connect stores the API key separately, in auth.json)
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

**Workflow summary:**

1. Install OpenCode (on Linux or on Android via
   [Termux](https://github.com/guysoft/opencode-termux)).
2. Create your API key at `https://chat.b.ai/key`.
3. Inside OpenCode, run `/connect`, choose **Other** and use the provider
   ID `bai`, pasting your API key there.
4. Create `opencode.json` with the content above — or better: use this
   GUI, search `B.AI` in the catalog, check the model's real context and
   register it with one click.
5. Inside OpenCode, choose the model with `/models`.

> **Important:** promotions are temporary. Check the **Usage** section of
> B.AI regularly to monitor your account consumption.

A port built with this workflow (OpenCode + DeepSeek V4 Flash):
<https://github.com/wachin/TBO>.
