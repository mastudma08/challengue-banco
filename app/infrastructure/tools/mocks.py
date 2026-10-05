from typing import Any


class MockExternalTools:
    """Deterministic mocks so every decision path can be reproduced locally."""

    @staticmethod
    def verify_identity(document_id: str) -> dict[str, Any]:
        if document_id.endswith("0000"):
            raise RuntimeError("simulated identity provider outage")
        if document_id.endswith("0"):
            return {"verified": False, "confidence": 0.99}
        if document_id.endswith("1"):
            return {"verified": True, "confidence": 0.72}
        return {"verified": True, "confidence": 0.96}

    @staticmethod
    def check_risk_lists(name: str, document_id: str) -> dict[str, Any]:
        upper_name = name.upper()
        if "TOOLFAIL RISK" in upper_name:
            raise RuntimeError("simulated risk provider outage")
        if document_id.endswith("9") or "HIGH RISK" in upper_name:
            return {
                "risk_level": "high",
                "matches": [{"source": "mock_watchlist", "match": "simulated"}],
            }
        if "MEDIUM RISK" in upper_name:
            return {"risk_level": "medium", "matches": []}
        return {"risk_level": "low", "matches": []}

    @staticmethod
    def prepare_documentation(product: str, client_data: dict[str, Any]) -> dict[str, Any]:
        if "TOOLFAIL DOC" in client_data["prospect_name"].upper():
            raise RuntimeError("simulated documentation service outage")

        by_product = {
            "cuenta_ahorros": [
                "cedula_identidad",
                "formulario_kyc",
                "aceptacion_terminos",
            ],
            "cuenta_corriente": [
                "cedula_identidad",
                "formulario_kyc",
                "declaracion_origen_fondos",
                "aceptacion_terminos",
            ],
        }
        return {"required_documents": by_product[product]}
