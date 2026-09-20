"""openFDA device endpoints.

The only genuine API in the stack. Used for supporting evidence: product codes
and cleared predicates for comparable devices. Never used to classify, because
FDA classification answers a different legal question.

  /device/classification.json  product code taxonomy
  /device/510k.json            clearances and predicates

Unauthenticated calls are rate limited. A free key raises the ceiling.
"""

BASE_URL = "https://api.fda.gov"


def search_510k(query: str, limit: int = 10) -> list[dict]:
    raise NotImplementedError


def classification_for_product_code(code: str) -> dict | None:
    raise NotImplementedError
