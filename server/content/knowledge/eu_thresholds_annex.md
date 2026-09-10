# EU Corporate Compliance — Practical Thresholds & Decision Boundaries

> **Annex to the main regulation reference.** This document provides the specific numerical limits, time windows, monetary thresholds, and decision criteria that employees need in day-to-day compliance situations. Designed for RAG retrieval when a user asks "how much / how long / when exactly" questions.

---

## 1 · Anti-Corruption: Gifts, Meals & Hospitality Boundaries

### 1.1 EU-Level Framework

The **EU Anti-Corruption Directive** (adopted April 2026) defines bribery as providing an **"undue advantage"** to induce official action. Recital 13 states that **"very low-value gifts"** are NOT considered undue advantages — but **no EU-wide euro amount** is set. The boundary is left to Member State transposition and corporate policy.

**Key test (5 factors):**
1. **Intent** — Was the gift given to influence a decision?
2. **Recipient role** — Public official vs. private-sector counterpart (stricter for officials)
3. **Value** — Proportionate and customary for the business context?
4. **Frequency** — One-off vs. pattern of repeated gifts?
5. **Transparency** — Was it documented and disclosed?

> **Cash gifts are ALWAYS prohibited** regardless of amount, across all EU frameworks.

### 1.2 Germany-Specific Thresholds (StGB §§ 331–338, 299–301)

| Scenario | Threshold | Source | Action Required |
|---|---|---|---|
| Gift to/from a **public official** (Beamter / Amtsträger) | **≤ €25** generally tolerated ("socially adequate") | Federal administration circular (8 Nov 2004); BBG § 71 | Declare to employer; keep receipt |
| Gift to/from a **public official** | **> €25** | Same circular | **Must be refused** or handed to employing office |
| "Socially adequate" gift to **private-sector** counterpart | **≤ €30** common benchmark | Case law; no statutory de minimis | Record in gift register |
| Business meal with **private-sector** counterpart | **≤ €100 per person** generally accepted | Industry practice / Lexology guidance | Pre-approval recommended if >€50 |
| Cultural/sporting event invitation | **Up to ~€100 per person** | Case law; assessed case-by-case | Document business purpose; no +1 without approval |
| Any gift/hospitality to **public official** | **€0 recommended** as safest approach | Legal advice consensus | "In general, it is advisable not to provide any benefits to public officials" |

> ⚠ **Germany has NO statutory de minimis.** Courts apply a "very strict approach" — even branded pens or promotional items *could* be problematic. The €25/€30 figures are administrative/practical guidelines, not legal safe harbours.

### 1.3 Common Corporate Policy Benchmarks (EU-wide practice)

| Item | Typical Limit | Notes |
|---|---|---|
| Individual gift (giving or receiving) | **€50–100 per person per occasion** | Most MNCs cap at €50 for public-sector, €100 for private |
| Business meal | **€75–150 per person** | Must have legitimate business purpose; document attendees |
| Hospitality event (conference dinner, etc.) | **€100–200 per person** | Pre-approval if exceeds threshold |
| Annual cumulative per recipient | **€150–250 per year** | Track across all gifts/meals to same person |
| Travel & accommodation for third parties | **Always requires pre-approval** | Regardless of amount |
| Anything involving a **public official** | **Pre-approval always required** | Even within monetary limits |
| Charitable donation linked to a deal | **Prohibited** | Never tie donations to business advantage |

### 1.4 EU Anti-Corruption Directive — Penalty Benchmarks

| Offence | Minimum Penalty (Natural Person) | Minimum Penalty (Legal Person) |
|---|---|---|
| Bribery of public officials | Min. limitation period **8 years** | Min. fine: **5% of global turnover** or **€40 million** |
| Bribery in private sector | Min. limitation period **5 years** | Same framework |
| Trading in influence | Min. limitation period **5 years** | Same framework |
| Obstruction of justice | Min. limitation period **5 years** | Same framework |

---

## 2 · Data Protection (GDPR): Specific Decision Thresholds

### 2.1 Breach Notification Timeline

```
BREACH OCCURS
    │
    ▼
AWARENESS (= "clock starts")  ←── Not when breach happened, but when you KNOW
    │
    ├── Within 72 HOURS ──→  Notify Supervisory Authority (Art. 33)
    │                         IF breach likely to result in RISK to individuals
    │                         Content: nature, numbers affected, DPO contact,
    │                                  consequences, mitigation measures
    │                         (Phased notification OK if full info unavailable)
    │
    ├── WITHOUT UNDUE DELAY ──→  Notify Affected Individuals (Art. 34)
    │                              IF breach likely to result in HIGH RISK
    │                              (higher threshold than authority notification)
    │                              Exceptions: data encrypted; risk eliminated;
    │                              disproportionate effort → public communication
    │
    └── ALWAYS ──→  Document in internal breach register (Art. 33(5))
                     Even if NO notification is required
```

> **Pending reform:** The Commission's Digital Omnibus proposal (Nov 2025) would raise the authority notification threshold to "high risk" (matching the individual notification standard) and extend the deadline from **72 to 96 hours**. Not yet in force as of Sep 2026.

### 2.2 DPO Appointment Criteria (Art. 37)

You **must** appoint a DPO if ANY of these apply:
1. You are a **public authority** or body (except courts)
2. Core activities involve **regular and systematic monitoring** of data subjects on a **large scale**
3. Core activities involve **large-scale processing of special category data** (Art. 9) or criminal conviction data (Art. 10)

> "Large scale" — EDPB considers: number of data subjects, volume of data, duration/permanence of processing, geographical extent. A single doctor is NOT large scale; a hospital IS.

### 2.3 DPIA Mandatory Triggers (Art. 35)

A DPIA is **required** when processing is **likely to result in a high risk**, including:
- **Systematic & extensive profiling** with significant effects on individuals
- **Large-scale processing** of special category / criminal data
- **Systematic monitoring** of publicly accessible areas on a large scale
- **New technologies** where risk is not well understood
- **AI-based automated decision-making** (especially under AI Act high-risk systems)

> National supervisory authorities publish **blacklists** of processing operations that always require a DPIA and **whitelists** that never do.

### 2.4 Fine Tiers

| Tier | Maximum Fine | Violations |
|---|---|---|
| **Upper tier** (Art. 83(5)) | **€20 million or 4% of global annual turnover** (whichever is higher) | Processing principles (Art. 5); lawful basis (Art. 6); consent (Art. 7); special categories (Art. 9); data subject rights (Arts. 12-22); international transfers (Arts. 44-49) |
| **Lower tier** (Art. 83(4)) | **€10 million or 2% of global annual turnover** | Controller/processor obligations (Arts. 25-39); certification body obligations; monitoring body obligations |
| **RoPA exemption** (Art. 30(5)) | Currently: enterprises with **< 250 employees** exempt from RoPA unless processing is not occasional, involves special categories, or is likely to result in a risk | Pending Omnibus: threshold may rise to **< 750 employees** (not yet in force) |

### 2.5 International Transfer Mechanisms

| Mechanism | When to Use |
|---|---|
| **Adequacy decision** | Recipient country deemed adequate by Commission (e.g., EU-US Data Privacy Framework, UK, Japan, South Korea, etc.) |
| **Standard Contractual Clauses (SCCs)** | Default for non-adequate countries; Commission Decision 2021/914; must conduct **Transfer Impact Assessment (TIA)** |
| **Binding Corporate Rules (BCRs)** | Intra-group transfers; requires DPA approval; takes 12-18 months |
| **Derogations (Art. 49)** | Explicit consent, contract necessity, legal claims, vital interests, public register — narrow interpretation; cannot be used for systematic/repeated transfers |

---

## 3 · AI Act: Classification Decision Tree & Specific Numbers

### 3.1 Risk Classification Quick Test

```
Is your AI system used for any Art. 5 PROHIBITED purpose?
  (social scoring, subliminal manipulation, exploitation of 
   vulnerabilities, real-time remote biometric ID in public
   spaces by law enforcement [with exceptions], emotion
   recognition in workplace/education, untargeted facial
   image scraping, predictive policing based solely on profiling)
    │
    YES → BANNED. Discontinue immediately. Fine: €35M / 7%
    │
    NO → Is it listed in Annex III high-risk categories?
         (biometrics, critical infrastructure, education/training,
          employment/worker management, essential services access,
          law enforcement, migration, justice/democracy)
         OR covered by Annex I harmonised legislation
         (medical devices, vehicles, toys, machinery, etc.)?
           │
           YES → HIGH-RISK. Full compliance required by Aug 2026.
           │     (Risk management, data governance, documentation,
           │      logging, transparency, human oversight, conformity
           │      assessment, EU database registration)
           │
           NO → Does it interact directly with natural persons?
                (chatbots, deepfake generators, emotion recognition
                 [non-prohibited], biometric categorisation [non-prohibited])
                  │
                  YES → TRANSPARENCY OBLIGATIONS (Art. 50)
                  │     Disclose AI interaction; label generated content
                  │
                  NO → MINIMAL/NO RISK. No specific obligations.
                        BUT: AI literacy duty (Art. 4) applies to ALL.
```

### 3.2 Fine Tiers

| Tier | Cap | Applies To | SME Calculation |
|---|---|---|---|
| **Tier 1** | **€35M or 7% turnover** (higher of two) | Art. 5 prohibited practices only | Lower of two amounts |
| **Tier 2** | **€15M or 3% turnover** (higher of two) | High-risk non-compliance; GPAI obligations; transparency violations | Lower of two amounts |
| **Tier 3** | **€7.5M or 1% turnover** (higher of two) | Supplying misleading information to authorities | Lower of two amounts |

> **Cross-over with GDPR:** Art. 99(8) prevents double penalties for the same factual act. But two separate violations (e.g., unlawful scraping under AI Act + processing without consent under GDPR) can each trigger a separate fine.

> **Revenue breakpoint:** Above **€500M** annual revenue, AI Act Tier 2 (3%) always exceeds GDPR upper tier (€20M cap).

### 3.3 AI Literacy Obligation (Art. 4)

- Applies to **ALL organisations** deploying or providing AI systems in the EU
- In force since **2 February 2025**
- No specific training hours mandated, but staff must have **"a sufficient level of AI literacy"** considering: technical knowledge, experience, education, context of AI use, and the persons/groups affected
- Must cover **ALL staff** who operate or are affected by AI systems, not just technical teams

---

## 4 · Anti-Money Laundering: Specific Numerical Triggers

### 4.1 Cash & Transaction Thresholds (from July 2027)

| Threshold | Obligation | Source |
|---|---|---|
| **> €10,000 cash** in commercial transaction | **PROHIBITED** (single payment or linked operations) | AMLR Reg. (EU) 2024/1624 |
| **≥ €3,000 cash** in commercial transaction | **Mandatory customer ID verification (KYC)** | AMLR |
| **≥ €1,000 crypto** occasional transaction | **Full customer due diligence** by CASP | AMLR |
| **≥ €1,000 crypto transfer** (to/from self-hosted wallet) | **Additional verification checks** (via CASP) | Transfer of Funds Reg. (EU) 2023/1113 |
| **Bank deposits** of any amount | **Not** subject to €10,000 cash prohibition, but monitored | AMLR |
| **Private individual-to-individual** cash transactions | **Exempt** from the €10,000 prohibition | AMLR |

### 4.2 Beneficial Ownership Thresholds

| Criterion | Threshold |
|---|---|
| Standard beneficial ownership | **≥ 25%** ownership or voting rights |
| Higher-risk structures (trusts, complex holding) | **≥ 15%** |
| Trustee update deadline for changes | **28 calendar days** |
| Record retention for CDD documents | **Minimum 5 years** after end of business relationship |

### 4.3 Penalties

| Offence | Minimum Penalty |
|---|---|
| Money laundering (22 predicate offences under AMLD6) | **Minimum 4 years** imprisonment |
| Structured transactions to avoid reporting | Criminal liability under national implementation |

---

## 5 · Cybersecurity: Incident Reporting Timelines

### 5.1 NIS2 Directive — Three-Stage Reporting

| Stage | Deadline | Content Required |
|---|---|---|
| **Early warning** | **Within 24 hours** of awareness | Whether the incident is suspected to be caused by unlawful/malicious acts; whether it could have cross-border impact |
| **Incident notification** | **Within 72 hours** of awareness | Initial assessment of severity and impact; indicators of compromise |
| **Final report** | **Within 1 month** of notification | Detailed description; root cause analysis; mitigation measures; cross-border impact |
| **Intermediate report** (if requested) | Upon CSIRT/authority request | Status updates between notification and final report |

> **Management liability:** NIS2 Art. 20 makes **management bodies personally accountable** for approving cybersecurity risk-management measures. Senior management can be **temporarily barred** from management functions for non-compliance.

### 5.2 DORA — Financial Sector ICT Incidents

| Classification | Reporting Deadline | Recipient |
|---|---|---|
| **Major ICT incident** | **Initial notification within 4 hours** of classification; intermediate report within 72h; final report within 1 month | National competent authority |
| **Significant cyber threat** | As soon as practicable | National competent authority (voluntary but encouraged) |
| **TLPT (Threat-Led Penetration Testing)** | **Every 3 years** minimum | Performed by external testers on live production systems |

### 5.3 GDPR Breach Notification (for comparison)

| Recipient | Deadline | Threshold |
|---|---|---|
| Supervisory authority | **72 hours** from awareness | Breach likely to result in **risk** |
| Affected individuals | **Without undue delay** (no fixed hours) | Breach likely to result in **high risk** |

### 5.4 AI Act Incident Reporting (Art. 73)

| Event | Obligation |
|---|---|
| Serious incident involving high-risk AI (death, serious health damage, serious damage to property/environment/fundamental rights) | Provider must report to **market surveillance authority** of the Member State where the incident occurred; **immediately** after establishing causal link, and no later than **15 days** of becoming aware |

---

## 6 · Employment Law: Specific Numerical Limits

### 6.1 Working Time (Directive 2003/88/EC)

| Limit | Value | Can Be Waived? |
|---|---|---|
| **Maximum weekly working hours** (incl. overtime) | **48 hours** (averaged over reference period of 4/6/12 months) | Yes, via individual opt-out (UK, some MS allow) |
| **Daily rest** | **11 consecutive hours** per 24h period | Derogations possible for shift work, specific sectors |
| **Weekly rest** | **24 consecutive hours** + 11h daily rest = **35h uninterrupted** per 7-day period | Can be averaged over 14-day reference period |
| **Rest break** during work | After **6 continuous hours** of work | Minimum break duration set by national law (usually 20-30 min) |
| **Paid annual leave** | **Minimum 4 weeks** (20 working days) | **Cannot** be replaced by payment in lieu (except on termination) |
| **Night work** (heavy/dangerous) | Max **8 hours** in any 24h period | — |
| **Night workers' health assessment** | **Free**, before assignment and at regular intervals | — |

### 6.2 Pay Transparency Directive — Specific Triggers

| Trigger | Threshold | Obligation |
|---|---|---|
| Job advertisements | **All employers** | Must state **salary range** (or at least starting salary) in posting; cannot ask candidates about pay history |
| Individual pay information right | **All employers** | Employees can request **average pay by gender** for their category of work |
| Gender pay gap reporting (first wave) | **≥ 250 employees** | Report **every year** starting from transposition (June 2026) |
| Gender pay gap reporting (second wave) | **100–249 employees** | Report **every 3 years** |
| **Joint pay assessment** trigger | Gender pay gap **> 5%** for any category | Mandatory if gap >5% AND not justified by objective gender-neutral factors AND not remedied within 6 months |
| Pay transparency penalties | Up to **4% of group annual turnover** | For systemic non-compliance |
| Burden of proof shift | **Automatic** | If employer fails to comply with transparency obligations, burden shifts to employer to prove no pay discrimination |

### 6.3 Whistleblower Protection (Directive 2019/1937)

| Requirement | Threshold / Detail |
|---|---|
| Internal reporting channel required | **≥ 50 employees** (some MS lower) |
| Acknowledgment of report | **Within 7 days** of receipt |
| Feedback to whistleblower | **Within 3 months** of acknowledgment |
| Protection scope | Covers breaches of EU law in: public procurement, financial services, AML, product safety, transport safety, environment, radiation protection, food safety, public health, consumer protection, data protection, competition |
| Retaliation prohibition | Dismissal, demotion, withholding of training/promotion, coercion, intimidation, harassment, blacklisting, damage to reputation — **ALL prohibited** |

### 6.4 Platform Work Directive — Key Numbers

| Element | Detail |
|---|---|
| **Employment presumption** | If platform controls work (≥ set of indicators defined by national law); **rebuttable** — platform bears burden of proof |
| Algorithmic management transparency | Workers must be informed about **automated monitoring** and **automated decision-making** systems |
| Human review | Workers have right to **human review** of automated decisions that **significantly affect** working conditions |

---

## 7 · Environmental & ESG: Reporting Thresholds

### 7.1 CSRD Reporting Scope (Post-Omnibus Directive 2026/470)

| Company Category | Employee Threshold | Turnover Threshold | Balance Sheet Threshold | Reporting Start |
|---|---|---|---|---|
| **Large PIEs (public interest entities)** | **> 500** | Already reporting | Already reporting | FY2024 (reports in 2025) |
| **Other large companies** (EU law definition: 2 of 3 criteria) | **> 250** | **> €50M** | **> €25M** | FY2025 (reports in 2026) |
| **Companies previously in wave 3** (now exempted by Omnibus) | **< 1,000** | Removed from scope | Removed from scope | **Pushed out** — FY2027 earliest |
| **Listed SMEs** (voluntarily) | < 250 | — | — | Opt-in from FY2026 with simplified standards |

### 7.2 CS3D / CSDDD Due Diligence Scope (Post-Omnibus)

| Criterion | Threshold |
|---|---|
| EU companies in scope | **> 5,000 employees AND > €1.5B worldwide net turnover** |
| Non-EU companies in scope | **> €1.5B EU-generated turnover** |
| Pre-Omnibus 3-wave phasing | **Removed** — single threshold now |
| Application date | **July 2029** |
| Transposition deadline | **July 2028** |

### 7.3 CBAM — Carbon Border Mechanism

| Element | Threshold / Value |
|---|---|
| **De minimis exemption** | **≤ 50 tonnes** net mass of CBAM goods per year per importer → fully exempt |
| **Scope** | Iron, steel, aluminium, cement, fertilisers, electricity, hydrogen |
| Declaration deadline | **30 September** of the year following imports |
| Certificate price | Based on **quarterly average EU ETS allowance auction prices** |
| First certificate purchases | **February 2027** (covering 2026 imports) |

### 7.4 EU Taxonomy — Alignment Criteria

| Element | Requirement |
|---|---|
| **Substantial contribution** | Activity must substantially contribute to ≥1 of 6 environmental objectives |
| **Do No Significant Harm (DNSH)** | Must not significantly harm any of the other 5 objectives |
| **Minimum safeguards** | Must comply with OECD Guidelines, UN Guiding Principles, ILO core conventions |
| **Disclosure** | Taxonomy-aligned % of **Revenue, CapEx, OpEx** |

---

## 8 · Competition Law: Specific Decision Boundaries

### 8.1 Merger Notification Thresholds (EU Merger Regulation)

| Criterion | Value |
|---|---|
| **Combined worldwide turnover** of all undertakings | **> €5 billion** |
| **EU-wide turnover** of each of at least two undertakings | **> €250 million** each |
| **UNLESS** each undertaking achieves > ⅔ of EU turnover in a single Member State | Not notifiable at EU level (MS jurisdiction) |
| **Alternative test** | Combined worldwide > €2.5B; combined turnover in each of ≥3 MS > €100M; individual turnover in each of those ≥3 MS > €25M; EU-wide individual > €100M each |

### 8.2 Dominance Assessment

| Indicator | Threshold |
|---|---|
| Market share below which dominance is **unlikely** | **< 40%** |
| Market share suggesting possible dominance | **40–50%** (presumption increases with share) |
| Market share creating **strong presumption** of dominance | **> 50%** (CJEU AKZO precedent) |

### 8.3 Fine Caps (Antitrust)

| Violation | Maximum Fine |
|---|---|
| Art. 101/102 TFEU violations | **10% of worldwide annual turnover** |
| **DMA** violations (gatekeepers) | **10% turnover**; **20% for repeat offences** |
| **DSA** violations | **6% of worldwide turnover** |
| **Failure to notify merger** | Up to 10% of turnover |

### 8.4 De Minimis — When Agreements Are Not Caught

| Type of Agreement | Market Share Threshold (per-party) |
|---|---|
| **Horizontal** (competitors) | **< 10%** on relevant market |
| **Vertical** (different levels of supply chain) | **< 15%** on relevant market |
| **Hardcore restrictions** (price fixing, market sharing, output limitation) | **NEVER** benefit from de minimis — caught regardless of market share |

---

## 9 · Product Safety: Recall & Reporting Timelines

### 9.1 GPSR — General Product Safety Regulation

| Obligation | Timeline / Threshold |
|---|---|
| Notify national authority of dangerous product | **Immediately** upon becoming aware |
| Report via **Safety Gate** (RAPEX) system | **Within 3 working days** of becoming aware of serious risk |
| Product recall completion target | No fixed legal deadline but "without delay"; authorities can order specific timeframes |
| Online marketplace obligation | Remove dangerous product from listing **within 2 business days** of order from authority |

### 9.2 Product Liability Directive (Revised) — Transposition by Dec 2026

| Element | New Rule |
|---|---|
| **Scope expansion** | Now covers **software, AI systems, digital services** (not just physical products) |
| **Limitation period** for bringing claims | **3 years** from awareness of damage, defect, and identity of liable person |
| **Long-stop period** | **10 years** from placing product on market (extendable to **25 years** for latent personal injury) |
| **Burden of proof** | Court may order **defendant to disclose evidence**; if refused, defect is **presumed** |
| **AI-specific provision** | If product's **complexity** makes proving defect/causation excessively difficult, court may presume defect and/or causation |

---

## 10 · Cross-Regulation Penalty Comparison

| Regulation | Max Fine (Fixed) | Max Fine (% Turnover) | Applies From |
|---|---|---|---|
| **GDPR** (upper tier) | €20M | **4%** | 2018 |
| **AI Act** (prohibited practices) | €35M | **7%** | Feb 2025 |
| **AI Act** (high-risk / GPAI) | €15M | **3%** | Aug 2026 |
| **AI Act** (misleading info) | €7.5M | **1%** | Aug 2026 |
| **NIS2** (essential entities) | €10M | **2%** | Oct 2024 (transposition) |
| **NIS2** (important entities) | €7M | **1.4%** | Oct 2024 (transposition) |
| **DMA** (gatekeepers) | — | **10%** (20% repeat) | Mar 2024 |
| **DSA** | — | **6%** | Feb 2024 |
| **DORA** | Set by national authority | — | Jan 2025 |
| **Antitrust** (Art. 101/102) | — | **10%** | Ongoing |
| **Pay Transparency Dir.** | — | **4%** | Jun 2026 |
| **AMLR** | — | **5% of turnover** or **€10M** or **2× benefit gained** | Jul 2027 |
| **EU Anti-Corruption Dir.** (legal persons) | **€40M** | **5%** | ~2028 (transposition) |

---

## 11 · Quick-Reference: "Can I Do This?" Decision Cards

### 🍽️ Card 1: "My supplier invited me to dinner"

```
Is the supplier a PUBLIC-SECTOR entity?
  YES → Extra caution. In Germany: keep under €25.
         In most MS: check local public-official gift rules.
         Pre-approval required if any doubt.
  NO  → Private sector:
         Is the meal ≤ €100/person?
           YES → Generally acceptable IF:
                  ✓ Legitimate business purpose
                  ✓ Not during active tender/procurement
                  ✓ Documented (who, when, why, amount)
                  ✓ No expectation of return favour
           NO  → Requires pre-approval from compliance.
                  If > €150/person → likely requires senior
                  management sign-off.
ALWAYS: Log in gift/hospitality register.
NEVER: Accept cash, gift cards, or personal favours.
```

### 🔓 Card 2: "We had a data breach"

```
Step 1: CONTAIN the breach immediately
Step 2: ASSESS risk to individuals
Step 3: DOCUMENT everything in breach register (mandatory regardless)

Is there a RISK to individuals' rights/freedoms?
  NO  → No external notification required.
         Still document internally (Art. 33(5)).
  YES → Notify supervisory authority within 72 HOURS.
         Is there a HIGH RISK to individuals?
           YES → Also notify affected individuals
                  WITHOUT UNDUE DELAY.
           NO  → Authority notification only.

Clock starts: moment of AWARENESS, not moment of breach.
Phased notification: OK if full info not available in 72h.
Late notification: must explain delay reason.
```

### 🤖 Card 3: "We want to deploy an AI tool"

```
Step 1: Check Art. 5 prohibited list
  → If hit: STOP. Cannot deploy.

Step 2: Check Annex III (high-risk uses)
  → If hit: full compliance needed
     (risk management, data governance, documentation,
      logging, transparency, human oversight, conformity
      assessment, EU database registration)

Step 3: Does it interact with humans directly?
  → Label it clearly as AI (Art. 50 transparency)

Step 4: ALL staff using AI must have AI literacy training
  → This is already in force since Feb 2025

Record in AI system inventory. Conduct a DPIA if it
processes personal data.
```

### 💶 Card 4: "Client wants to pay in cash"

```
Is the payment for a COMMERCIAL transaction?
  Is the total amount (incl. linked payments) > €10,000?
    YES → PROHIBITED from July 2027. Refuse the payment.
  Is the total ≥ €3,000?
    YES → Must perform KYC: verify identity with
          government-issued ID. Keep records 5 years.
  Is it a crypto payment ≥ €1,000?
    YES → Full CDD required (if you're a CASP).

Is the payment between TWO PRIVATE INDIVIDUALS (non-commercial)?
  → Cash prohibition does NOT apply.
    But: still monitor for suspicious patterns.
```

### 👥 Card 5: "Do we need to report our gender pay gap?"

```
How many employees?
  ≥ 250 → Report EVERY YEAR (from June 2026 transposition)
  100–249 → Report EVERY 3 YEARS
  < 100 → No mandatory reporting (but pay transparency
           still applies: salary ranges in job ads, etc.)

Is your gender pay gap > 5% for any job category?
  YES → Joint pay assessment MANDATORY
        (with worker representatives)
        IF gap cannot be justified by objective,
        gender-neutral criteria AND not remedied
        within 6 months.
  NO  → Continue monitoring.

Penalties: up to 4% of group annual turnover for
systemic non-compliance.
```
