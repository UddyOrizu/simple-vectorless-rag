#!/usr/bin/env python3
"""Seed the corpus with four real documents and, importantly, WITH TAG
DESCRIPTIONS -- this is the fixture the auto-tag-mapping feature needs
to be worth demoing: try a question that never uses a tag's name and
watch it get inferred from what the tag actually means.

    python seed_corpus.py
"""
import asyncio
import sys

from app import db, ingest, repository

TAGS = [
    ("core", "The main, real corpus documents, as opposed to synthetic test data."),
    ("financial", "Financial results: revenue, costs, dividends, margins, capital expenditure."),
    ("fy2025", "Applies to the FY2025 reporting and policy year, effective 1 April 2025."),
    ("board", "Matters reported to, or decided by, the board of directors."),
    ("hr-policy", "Human resources policy: leave, relocation, benefits, and employee entitlements."),
    ("uk", "Applies to United Kingdom-based employees or operations."),
    ("ireland", "Applies to Ireland-based employees or operations, including the Dublin clinical partnership site."),
    ("netherlands", "Applies to Netherlands-based employees or operations, including the Rotterdam clinical partnership site."),
    ("it-security", "Information security controls: access control, incident response, privileged accounts, system security."),
    ("compliance", "Regulatory and contractual compliance obligations, including for suppliers and vendors."),
    ("procurement", "Vendor selection, contract approval thresholds, and ongoing supplier management."),
]

ANNUAL_REPORT = """# Meridian Health Group — FY2025 Annual Report

## Executive Summary

Meridian Health Group is a diversified healthcare services provider operating across
outpatient diagnostics, occupational health, and specialty pharmacy distribution. This
report covers our FY2025 annual results and is intended for internal circulation to
management, finance, and the board.

Meridian Health Group's total revenue for FY2025 was £412.6 million, up 8.3% year-on-year,
driven primarily by growth in the diagnostics segment and the continued rollout of our
occupational health contracts across the Midlands and North West regions. Operating
margin improved to 14.1%, from 12.7% in FY2024, reflecting cost discipline in
procurement and a full year of synergies from the Ashcombe Diagnostics acquisition
completed in March 2024.

The board approved a final dividend of 9.2 pence per share, bringing the total FY2025
dividend to 14.5 pence per share, a 6% increase on the prior year. Headcount grew from
3,140 to 3,410 full-time equivalents over the course of the year, with the majority of
new hires concentrated in diagnostics and in the expanding international assignments
programme supporting our new Dublin and Rotterdam clinical partnerships (see the HR
policy manual for the allowances that apply to those assignments).

## Company Overview

### History and Structure

Meridian Health Group was founded in 2008 as a single diagnostics clinic in Manchester
and has grown, through a combination of organic expansion and seven acquisitions, into
a group with 46 sites across the United Kingdom and Ireland, plus a new clinical
partnership footprint in continental Europe established in FY2025.

### Markets Served

Meridian Health Group serves three principal customer groups: NHS trusts and integrated
care boards, who account for approximately 47% of group revenue; corporate occupational
health clients, who account for approximately 34% of group revenue; and private
pharmacy and specialty distribution customers, who account for the remaining 19%.

## Financial Performance

### Revenue by Segment

Diagnostics segment revenue was £239.3 million in FY2025, up 11.2% year-on-year.
Occupational Health segment revenue was £127.9 million, up 4.1% year-on-year. Specialty
Pharmacy Distribution revenue was £45.4 million, broadly flat year-on-year at 0.9%
growth, as the division absorbed one-off costs associated with a warehouse relocation
in Warrington.

### Cost Structure

Cost of sales for FY2025 was £267.8 million, representing 64.9% of revenue. Staff
costs, the largest single cost category, were £198.4 million, up 9.7% year-on-year.
IT and software licensing costs were £14.7 million, up 22% year-on-year, reflecting
continued investment in the group's information security programme.

### Capital Expenditure

Total capital expenditure for FY2025 was £28.6 million. The board has approved a
further £34 million of capital expenditure for FY2026, subject to quarterly review.

## Risk Factors

### Regulatory Risk

Meridian Health Group operates in a heavily regulated environment, subject to Care
Quality Commission registration requirements in England and equivalent frameworks in
Scotland, Wales, and the Republic of Ireland.

### Operational Risk

Key operational risks include clinical staffing shortages, supply chain disruption, and
information security incidents affecting patient data. The group maintains a dedicated
clinical risk committee, chaired by the Chief Medical Officer.

### Market Risk

A growing proportion of the international assignments programme introduces limited
euro-denominated cost exposure that the group does not currently hedge.
"""

HR_POLICY = """# Meridian Health Group — Human Resources Policy Manual

This manual sets out Meridian Health Group's HR policies as they apply to all
employees, effective from 1 April 2025.

## Annual and Sick Leave

Full-time employees are entitled to 25 days of annual leave per year, rising to 28
days after five continuous years of service. Sick leave is paid at full pay for the
first 20 working days of absence in any rolling 12-month period, and at half pay for a
further 20 working days.

## Domestic Relocation Allowance

Employees who relocate more than 50 miles within the United Kingdom or Ireland to take
up a new role are eligible for a domestic relocation allowance of up to £1,200.

## International Assignments

Meridian Health Group's international assignments programme supports employees taking
up postings at our clinical partnership sites in Dublin and Rotterdam.

Employees on assignments of less than six months are classified as short-term
assignees and receive a per diem of £85 for each day at the overseas site, paid
monthly in arrears.

Employees relocating internationally for assignments longer than six months receive a
one-time settling-in allowance of £4,750, paid within the first payroll cycle after
arrival, separate from and in addition to any removal costs reimbursement.

In addition, long-term international assignees receive a monthly housing supplement of
£1,650, home leave flights to the UK or Ireland twice per year, and a monthly
cost-of-living adjustment reviewed quarterly by finance. Tuition reimbursement of up
to £8,000 per academic year is available for dependent children, subject to approval
from the Chief People Officer.

International assignees remain enrolled in the UK pension scheme unless local
regulations require otherwise. Assignments are reviewed annually.

## Benefits and Wellbeing

All employees are automatically enrolled in the group private medical insurance scheme
after a three-month qualifying period. The group also provides an employee assistance
programme and an annual wellbeing allowance of £150.
"""

IT_SECURITY_POLICY = """# Meridian Health Group — Information Security Policy

This document sets out the minimum information security controls applicable to all
Meridian Health Group systems handling patient, employee, or commercially sensitive
data.

## Access Control Principles

Access is granted on a least-privilege basis. Standard user accounts are subject to
password rotation every 90 days and must use multi-factor authentication for remote
access. Standard access recertification is carried out twice per year, in April and
October.

## Incident Response

Any suspected information security incident must be reported within one hour of
discovery. Incidents are classified from Severity 1 (major, executive notification
required) to Severity 4 (minor). Severity 1 and 2 incidents are reported to the
board's audit and risk committee, and, where required, to the Information
Commissioner's Office within 72 hours.

## Privileged Access Review

Privileged accounts -- any account with administrative rights over production
systems, databases, or the identity provider -- are reviewed quarterly, with the
fourth review of each calendar year completed no later than 15 December, ahead of the
year-end audit. Each review must be signed off by both the system owner and the Chief
Information Officer, with evidence retained for seven years.

Any privileged account inactive for more than 30 consecutive days is automatically
suspended. Break-glass emergency access is logged separately and reviewed within 24
hours of use.

## Supplier System Access

Third-party suppliers granted system access are subject to the same access control
principles as employees, reviewed on the same quarterly cadence as privileged
accounts. See the vendor and procurement policy for onboarding requirements.
"""

VENDOR_POLICY = """# Meridian Health Group — Vendor and Procurement Policy

## Supplier Onboarding

All new suppliers with access to Meridian Health Group systems or data must complete a
security and compliance questionnaire prior to onboarding, and suppliers handling
patient data must provide evidence of appropriate data processing agreements and, where
applicable, current ISO 27001 or equivalent certification.

## Contract Thresholds

Contracts under £25,000 may be approved by a divisional managing director. Contracts
between £25,000 and £150,000 require Chief Financial Officer sign-off. Any contract
above £150,000, or a multi-year contract above £300,000 total, must be reviewed by the
procurement committee and approved by at least two executive team members.

## Ongoing Supplier Review

Suppliers are reassessed annually against the same questionnaire used at onboarding.
Any supplier with a reportable security incident in the preceding 12 months is subject
to an out-of-cycle review before contract renewal.
"""

DOCUMENTS = [
    ("meridian-annual-report", ANNUAL_REPORT, ["core", "financial", "fy2025", "board"]),
    ("meridian-hr-policy", HR_POLICY, ["core", "hr-policy", "fy2025", "uk", "ireland", "netherlands"]),
    ("meridian-it-security-policy", IT_SECURITY_POLICY, ["core", "it-security", "compliance", "fy2025"]),
    ("meridian-vendor-policy", VENDOR_POLICY, ["core", "procurement", "compliance", "fy2025"]),
]


async def main():
    pool = await db.connect()

    print("Creating tags with descriptions...")
    for name, description in TAGS:
        await repository.create_tag(pool, name, description)
        print(f"  {name}")

    print("\nIngesting documents (this calls Claude for section + document summaries)...")
    for doc_id, content, tags in DOCUMENTS:
        status = await ingest.ingest_document(pool, doc_id, content, explicit_tags=tags)
        print(f"  [{status:9s}] {doc_id}")

    print("\nDone. Try:")
    print('  curl -X POST localhost:8000/api/search -H "Content-Type: application/json" \\')
    print('    -d \'{"question": "What happens if I move to the Rotterdam office for work?"}\'')
    print("  (note: no tag named 'rotterdam' exists -- this should auto-infer 'netherlands' "
          "and 'hr-policy' from their descriptions, not from keyword overlap.)")

    await db.disconnect()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        sys.exit(1)
