# Security

[Back to the README](../README.md)

What this project guarantees and checks in the tests. The rules apply to
the app, the catalog, the connection test and the files it writes.

- `~/.local/share/opencode/auth.json` is **never** read or written; a test
  compares its bytes before and after the whole flow (search, filter,
  register, set default, save) and requires them to stay identical.
- An API key is **never** shown or stored in the catalog, the cache, the
  preview or `opencode.json`.
- Credentials are managed with environment variables (`env`) and with
  `/connect`. There is no key-management feature; any future addition
  would be optional and explicitly authorized by the user.
- No key is passed on the command line and no credential is sent to a
  catalog provider.
- The connection test is anonymous unless you press **Probar con mi
  clave**; in that case the key comes from the declared variable,
  travels only over HTTPS or to loopback and is redacted from any
  message. The test follows no redirects and never contacts cloud
  metadata addresses.
- URLs and imported data are validated before being accepted; writes are
  atomic and **never silently overwrite**: there is always a backup and a
  warning if the file changed outside the app.
- No scripts or npm packages are downloaded or executed automatically.

The catalog is data, not configuration: a model reaches `opencode.json`
only when you press **Agregar a OpenCode** (“Add to OpenCode”). Searching
and testing never write to disk.
