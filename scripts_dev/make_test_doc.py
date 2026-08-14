"""One-off: generate a synthetic claim-form image to smoke test the ingestion
pipeline before real structured claims data exists in V3. Not part of the app."""
from PIL import Image, ImageDraw

img = Image.new("RGB", (900, 650), "white")
d = ImageDraw.Draw(img)
lines = [
    "MERIDIAN INSURANCE — CLAIM FORM",
    "",
    "Claim Number: CLM-2026-000481",
    "Date of Loss: 2026-07-22",
    "Date Filed: 2026-07-25",
    "",
    "Claimant: Priya Nandakumar",
    "Policy Number: POL-SG-88213",
    "Adjuster: Marcus Tan",
    "",
    "Loss Description:",
    "Water damage to living room flooring following a burst pipe.",
    "Plumber's report attached separately confirms sudden pipe failure,",
    "not gradual wear. Estimated repair cost SGD 4,250.",
    "",
    "Amounts:",
    "  Estimated repair cost: SGD 4,250.00",
    "  Deductible: SGD 500.00",
    "",
    "Adjuster notes: Claimant has filed 2 prior water-damage claims in the",
    "past 18 months at the same address — flag for review.",
]
y = 20
for line in lines:
    d.text((30, y), line, fill="black")
    y += 28

img.save("scripts_dev/test_claim_doc.png")
print("saved scripts_dev/test_claim_doc.png")
