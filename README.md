# Onboarding Agent Orchestrator — Fase 2

Implementación de referencia para un onboarding bancario multiagente con **frontera API segura**, **workflow determinista**, **subagentes especializados**, **control de tools**, **estado persistente**, **RAG local de políticas** y **uso de LLM limitado a redacción no decisional**.

La arquitectura parte del diagrama original incluido en `docs/original-architecture.drawio.html`, pero en fase 2 hace explícita la separación:

```text
Frontend
   |
   v
FastAPI / Security Boundary
   |
   v
OnboardingOrchestrator
   |
   v
OnboardingWorkflow (FSM determinista)
   |
   +--> IdentityAgent -----------+
   +--> RiskAgent ---------------+--> ToolGateway --> External Tools (mock)
   +--> DocumentationAgent ------+
   |          |
   |          +--> PolicyRetriever (RAG local)
   |
   +--> CustomerResponseAgent --> PII Guard --> LLM Provider
   |
   +<--> State Repository (SQLite)
```

## Principios de seguridad aplicados

1. **El frontend no es una frontera de confianza.** FastAPI vuelve a validar el contrato aunque el frontend ya haya validado.
2. **Los agentes no se exponen por HTTP.** La única entrada es el API.
3. **El LLM no decide aptitud ni el siguiente paso.** La secuencia está codificada en una máquina de estados con transiciones permitidas.
4. **Least privilege para tools.** Cada agente tiene una allow-list y cada tool valida sus argumentos con esquemas estrictos.
5. **Fail closed ante incertidumbre.** Baja confianza, riesgo alto, fallo de tool o falta de evidencia de política derivan a revisión manual.
6. **PII fuera del prompt.** Nombre y documento no se envían al proveedor LLM; un guard determinista bloquea posibles filtraciones antes y después de la llamada.
7. **No se exponen internals al frontend.** La respuesta pública excluye request PII, texto del corpus RAG y audit trail interno.

## Flujo determinista

El componente `app/application/workflows/onboarding_workflow.py` define las únicas transiciones válidas:

```text
RECEIVED
   -> VERIFY_IDENTITY
      -> GENERATE_RESPONSE                 (reject/manual review)
      -> CHECK_RISK
         -> GENERATE_RESPONSE              (manual review)
         -> RETRIEVE_POLICY
            -> GENERATE_RESPONSE           (manual review)
            -> PREPARE_DOCUMENTATION
               -> GENERATE_RESPONSE
                  -> COMPLETED
```

No existe una transición directa `RECEIVED -> APPROVED`, ni un agente puede escoger el siguiente estado.

### Reglas funcionales

- `verified = false` -> `rejected`
- `verified = true` y `confidence < 0.8` -> `manual_review`
- `risk_level = high` -> `manual_review`
- error de verificación externa -> `manual_review`
- evidencia de política no recuperable -> `manual_review`
- documentación no soportada por la política recuperada -> `manual_review`
- resto -> `approved`

## RAG de políticas

Para fase 2 se usa un retriever local y reemplazable:

- Puerto: `app/application/ports/policy_retriever.py`
- Adaptador: `app/infrastructure/rag/local_policy_retriever.py`
- Corpus demo: `docs/policies/onboarding_policy.md`

El retriever lexical es intencionalmente simple para que la PoC sea reproducible en Podman sin infraestructura adicional. La interfaz permite sustituirlo después por Azure AI Search, pgvector, Elasticsearch u otro motor sin cambiar el workflow.

La evidencia recuperada **no decide por LLM**. `DocumentationAgent` comprueba de forma determinista que los documentos entregados por la tool estén soportados por la política recuperada.

> El corpus incluido es únicamente demostrativo y no representa políticas reales del Banco.

## LLM

El LLM se utiliza únicamente para redactar la respuesta al cliente después de que la decisión ya existe.

Por defecto:

```env
LLM_MODE=mock
```

Así la solución funciona offline y en Podman sin credenciales.

Opcionalmente existe un adaptador para endpoints compatibles con `/v1/chat/completions`:

```env
LLM_MODE=openai_compatible
LLM_BASE_URL=http://host.containers.internal:11434
LLM_API_KEY=local-placeholder
LLM_MODEL=your-model
```

Si el proveedor falla, la generación de respuesta hace fallback a una plantilla determinista. El fallo del LLM **nunca altera la decisión de onboarding**.

## API

### `POST /api/v1/onboarding/start`

Request:

```json
{
  "prospect_name": "Juan Perez",
  "document_id": "1712345678",
  "product": "cuenta_ahorros"
}
```

Validaciones backend principales:

- `document_id`: exactamente 10 dígitos
- `product`: `cuenta_ahorros` o `cuenta_corriente`
- campos extra: rechazados
- JWT válido
- scope `onboarding:start`
- límite de tamaño del body

### `GET /api/v1/onboarding/{onboarding_id}`

Requiere scope `onboarding:read`.

La respuesta pública incluye decisión, resultados necesarios, escalamiento, documentación y mensaje al cliente, pero **no** retorna:

- `document_id`
- request completo
- corpus/policy evidence
- audit trail interno

## Ejecución con Podman

```bash
cp .env.example .env
podman compose up --build -d
podman ps
podman logs onboarding-agent-phase2
```

Genera un token de desarrollo desde el contenedor para garantizar que usa el mismo secret/configuración:

```bash
TOKEN=$(podman exec onboarding-agent-phase2 python /app/scripts/create_dev_token.py)
```

Ejecuta el caso feliz:

```bash
curl http://localhost:8080/api/v1/onboarding/start \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "prospect_name": "Juan Perez",
    "document_id": "1712345678",
    "product": "cuenta_ahorros"
  }'
```

Swagger: `http://localhost:8080/docs`

Health: `http://localhost:8080/health`

## Casos reproducibles de los mocks

| Caso | Entrada | Resultado |
|---|---|---|
| Happy path | documento terminado en `8` | `approved` |
| Identidad no verificada | documento terminado en `0` | `rejected` |
| Confianza baja | documento terminado en `1` | `manual_review` |
| Alto riesgo | documento terminado en `9` | `manual_review` |
| Falla identidad | documento terminado en `0000` | `manual_review` |
| Falla riesgo | nombre contiene `Toolfail Risk` | `manual_review` |
| Falla documentación | nombre contiene `Toolfail Doc` | `manual_review` |

## Tests

```bash
python -m pytest -q
```

Estado actual: **16 tests passing**.

Se cubre:

- aprobación
- rechazo
- baja confianza
- riesgo alto
- persistencia
- autenticación JWT
- autorización por scopes
- bypass de validación del frontend
- campos extra maliciosos
- bloqueo de tools no autorizadas
- argumentos extra hacia tools
- transición inválida del workflow
- detección de PII
- verificación de que nombre/documento no llegan al LLM
- recuperación de evidencia RAG
- ocultamiento de internals en la respuesta pública

## Estructura

```text
app/
  domain/
    models.py
    policies.py
  application/
    orchestrator.py                  # fachada de aplicación
    workflows/
      onboarding_workflow.py         # FSM determinista
    agents/
      identity.py
      risk.py
      documentation.py
      response.py
    ports/
      repository.py
      tool_gateway.py
      policy_retriever.py
      llm.py
  infrastructure/
    api/
      main.py
      auth.py
      schemas.py
    persistence/
      sqlite_repository.py
    tools/
      gateway.py
      mocks.py
    rag/
      local_policy_retriever.py
    security/
      pii_guard.py
    llm/
      mock_provider.py
      openai_compatible_provider.py
docs/
  architecture.md
  original-architecture.drawio.html
  policies/
Containerfile
compose.yaml
tests/
```

## Qué sigue después de fase 2

Para una fase productiva, los siguientes reemplazos pueden hacerse detrás de los puertos ya definidos: IdP corporativo/OIDC, base gestionada, vector store/AI Search, proveedor LLM corporativo, secret manager, observabilidad distribuida, rate limiting externo, circuit breaker/retries, colas/eventos y políticas reales versionadas. Esos elementos no son necesarios para demostrar el control de flujo y seguridad de esta PoC.
