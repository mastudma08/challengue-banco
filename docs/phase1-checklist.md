# Checklist de aceptación — fase 1

- [x] Endpoint solicitado implementado.
- [x] Orquestador principal implementado.
- [x] Subagentes Identity, Risk, Documentation y Response.
- [x] Tools 1-3 mockeadas.
- [x] Umbral de identidad 0.8 aplicado.
- [x] Riesgo high escala a revisión manual.
- [x] Fallos de tools producen mitigación y no una decisión silenciosa.
- [x] Estado persistido entre pasos y consultable por ID.
- [x] Audit trail de transiciones.
- [x] Allow-list de tools por agente.
- [x] Agentes no expuestos directamente.
- [x] JWT en el API edge para la demo.
- [x] Containerfile y compose.yaml para Podman.
- [x] Tests de happy path, rechazo, escalamiento, persistencia, autorización y permisos de tools.
