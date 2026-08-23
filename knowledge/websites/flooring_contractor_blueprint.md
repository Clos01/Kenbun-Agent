# 🏛️ Kenbun Blueprint: High-Conversion Flooring Contractor Websites

This blueprint captures the architectural patterns, pricing formulas, and conversion design tokens used for building high-ticket flooring contractor websites optimized for Google Business Profile traffic and local contractor B2B lead generation.

---

## 1. Core Economics & Pricing Structure

* **Material Tier:** MSI Cyrus Luxury Click Plank (100% Waterproof Rigid Core, 12-mil Wear Layer, Pre-attached Acoustic Pad)
  * **Wholesale Price:** $2.00 / sqft
  * **Primary Colorways:** *Fauna* (Warm Natural Oak) and *Whitfield Grey* (Modern Architectural Slate)
* **Labor Tiers:**
  * **Click-Lock LVP / LVT:** $2.00 / sqft (Floating installation)
  * **Glue-Down LVP / LVT:** $1.50 / sqft (Commercial adhesives & high-traffic turnover)
  * **Commercial Cove Base:** Custom per linear foot / scope
* **Industry Waste Allowance:** Standard +10% material buffer for room cuts and diagonal corners.

---

## 2. Interactive Lead-Generation Components (21st.dev Standard)

1. **Live Square-Footage Estimator:**
   * Sliders ranging from 100 to 4,500 sq ft.
   * Real-time calculation: $\text{Total} = (\text{SqFt} \times \text{Labor Rate}) + (\text{SqFt} \times 1.10 \times \text{Material Rate})$.
   * Seamless transition to 1-click booking modal with pre-filled scope.
2. **Aceternity Spotlight Product Showcase:**
   * Interactive texture and swatch visualizer for *Fauna* and *Whitfield Grey*.
   * Technical spec pill breakdown (waterproof, wear layer, acoustic rating).
3. **B2B & Multi-Family Fast-Track:**
   * High-volume turnover pricing for Property Managers.
   * W9 / COI / $1M+ General Liability proof for General Contractors.
   * Commercial cove base & after-hours scheduling for Office Fit-outs.
4. **Local SEO & Google Profile Trust Matrix:**
   * Specific city pill coverage: Charlotte NC, Mount Holly NC, Greensboro NC, Fort Mill SC, Salisbury NC, Gastonia NC, Monroe NC.
   * JSON-LD `HomeAndConstructionBusiness` Schema with localized coordinates and service offer catalog.

---

## 3. Project File Structure Pattern

```
/Users/carlosrivas/Dev/Projects/<project-name>/
├── src/
│   ├── app/
│   │   ├── layout.tsx         # JSON-LD LocalBusiness Schema & Metadata
│   │   ├── globals.css        # Heritage design tokens & glassmorphism
│   │   └── page.tsx           # Master landing page layout
│   ├── components/
│   │   ├── navigation/        # Sticky navbar & mobile drawer
│   │   ├── hero/              # Animated hero with trust metrics
│   │   ├── calculator/        # 21st.dev interactive cost estimator
│   │   ├── products/          # MSI Cyrus colorway visualizer
│   │   ├── contractor/        # B2B & GC fast-track portal
│   │   ├── locations/         # Localized NC & SC service area grid
│   │   ├── reviews/           # 5-star Google review cards
│   │   ├── leads/             # Lead capture & on-site measure modal
│   │   └── footer/            # Regional NAP (Name, Address, Phone) footer
```
