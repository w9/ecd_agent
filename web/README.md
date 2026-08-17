# Clinical site feasibility chat UI

Separate Vite + React + Tailwind + shadcn/ui front end for the FastAPI query API.

```bash
# from the repo root, with the API already running (`just dev`)
just chat
# http://127.0.0.1:5173
```

Vite proxies `/query` and `/protocols` to `http://127.0.0.1:8000`. Each send replaces the previous exchange; the API stays one-shot.
