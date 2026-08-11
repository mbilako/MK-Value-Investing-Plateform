# Local logout-failure proof of concept

This PoC uses only in-process state and synthetic credentials. It opens no
listener and sends no network traffic.

## Requirements

- Windows PowerShell 5.1 or later

## Run

```sh
powershell -NoProfile -ExecutionPolicy Bypass -File .\poc.ps1
```

The script simulates a valid browser session, a `503` logout failure before
revocation, the vulnerable UI transition to `unauthenticated`, and a
subsequent `/auth/me` reload that restores the previous user. It changes only
in-memory variables and requires no cleanup.
