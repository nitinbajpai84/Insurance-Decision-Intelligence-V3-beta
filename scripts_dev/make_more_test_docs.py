"""Generate a spread of synthetic claim-document types to populate the V3
beta demo with realistic variety (claim form already covered separately).
Not part of the app — dev/demo helper only."""
from PIL import Image, ImageDraw


def render(lines, path):
    img = Image.new("RGB", (900, 700), "white")
    d = ImageDraw.Draw(img)
    y = 20
    for line in lines:
        d.text((30, y), line, fill="black")
        y += 26
    img.save(path)
    print("saved", path)


render(
    [
        "MOUNT ELIZABETH MEDICAL CENTRE",
        "DISCHARGE SUMMARY",
        "",
        "Patient: Brandi Reynolds",
        "Claim reference: CLM001609",
        "Admission date: 2026-06-18   Discharge date: 2026-06-24",
        "",
        "Attending Surgeon: Dr. Wei-Lin Ho",
        "Procedure: Laparoscopic cholecystectomy",
        "Diagnosis: Acute cholecystitis with gallstones",
        "",
        "Clinical summary:",
        "Patient presented with acute right-upper-quadrant pain. Ultrasound",
        "confirmed cholelithiasis. Procedure performed without complication.",
        "Patient recovered well post-operatively, discharged in stable",
        "condition with standard analgesia and follow-up in 2 weeks.",
        "",
        "Billed amount: SGD 18,400.00",
        "Insurer portion (per policy schedule): SGD 16,560.00",
        "",
        "No pre-existing condition disclosure discrepancies noted.",
    ],
    "scripts_dev/test_doc_medical_report.png",
)

render(
    [
        "CLAIMS ADJUSTER FIELD NOTE",
        "",
        "Claim: CLM002863 (Briana Kennedy)",
        "Adjuster: Farah Osman   Date of visit: 2026-06-29",
        "",
        "Site: Vehicle collision, Tampines Ave 5 junction.",
        "",
        "Observations:",
        "Rear-end collision, moderate damage to bumper and boot panel.",
        "Other party's dashcam footage requested but not yet received.",
        "Claimant's account of the incident is broadly consistent with the",
        "damage pattern observed on site.",
        "",
        "Repair estimate obtained: SGD 5,317.40 (Tampines Auto Body Works)",
        "",
        "No red flags identified. Recommend proceeding to settlement once",
        "repair invoice is submitted. Standard turnaround expected.",
    ],
    "scripts_dev/test_doc_adjuster_note.png",
)

render(
    [
        "RAFFLES HOSPITAL — ONCOLOGY DEPARTMENT",
        "MEDICAL REPORT FOR INSURANCE CLAIM",
        "",
        "Patient: Ricky Cisneros",
        "Claim reference: CLM000924",
        "Report date: 2026-06-28",
        "",
        "Diagnosis: Stage II colorectal carcinoma, confirmed via biopsy",
        "2026-05-30. Patient commenced chemotherapy 2026-06-10.",
        "",
        "This diagnosis qualifies under the policy's Critical Illness",
        "rider (Section 4.2, malignant cancer definition).",
        "",
        "Treatment plan: 6 cycles FOLFOX, reassessment via CT at cycle 4.",
        "",
        "Estimated total treatment cost: SGD 42,000.00",
        "",
        "Note: patient's policy was underwritten 14 months prior to",
        "diagnosis; outside the standard 90-day exclusion window, but",
        "within the 2-year contestability period — worth a routine",
        "underwriting file review per standard practice, not a specific",
        "concern raised by the treating physician.",
    ],
    "scripts_dev/test_doc_critical_illness.png",
)
