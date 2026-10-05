# Podman — fase 2

## Levantar

```bash
cp .env.example .env
podman compose up --build -d
podman ps
podman logs onboarding-agent-phase2
```

## Token

```bash
TOKEN=$(podman exec onboarding-agent-phase2 python /app/scripts/create_dev_token.py)
```

PowerShell:

```powershell
$TOKEN = podman exec onboarding-agent-phase2 python /app/scripts/create_dev_token.py
```

El token incluye:

```text
onboarding:start onboarding:read
```

## Probar

```bash
curl http://localhost:8080/api/v1/onboarding/start \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"prospect_name":"Juan Perez","document_id":"1712345678","product":"cuenta_ahorros"}'
```

## LLM local/compatible opcional

La configuración por defecto es `LLM_MODE=mock`. Para conectar un endpoint compatible con chat completions cambia `.env`:

```env
LLM_MODE=openai_compatible
LLM_BASE_URL=http://host.containers.internal:11434
LLM_API_KEY=local-placeholder
LLM_MODEL=your-model
```

Recrea el contenedor:

```bash
podman compose up --build -d
```

El workflow, las políticas y el tool gateway no cambian al sustituir el proveedor LLM.
