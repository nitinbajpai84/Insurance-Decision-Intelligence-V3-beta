"""
Stage 2 integration layer.

Every external system enters the product through this package, along one
path:

    SOURCE -> INGESTION -> NORMALIZATION -> IDENTITY MATCHING
           -> CUSTOMER MODEL -> NEO4J -> QDRANT

Two rules hold everywhere in here:

1. A provider is reported connected only when a real credential-backed
   implementation says so. `registry.py` records which providers are
   actually implemented; nothing else may claim otherwise.
2. Imported data carries provenance (models.Provenance) from the moment
   it is read until it lands in the graph. Gemini may classify, match,
   extract, and summarize — it never writes customer truth on its own.
"""
