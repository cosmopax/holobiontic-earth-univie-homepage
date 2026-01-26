# Project Vision: Holobiontic Earth (2026)

> **"The mastery of biological substrates as the ultimate technological platform."**

## 1. Core Vision & Philosophy

**Transition to a HoloBiontic Civilization:** A planetary superorganism where "Logos" (Code) and "Bios" (Life) merge.
The website serves as the **digital cortex** for this initiative, moving beyond a simple portfolio to become a "Living Interface" for planetary symbiosis data.

### Key Pillars

* **Biologization:** Designing sentient matter and organic processes.
* **Infosphere:** Global brain symbiosis prioritizing empathy over throughput.
* **Resilience through Autarky:** Hacking bureaucracy to redirect resources into the bioeconomy.
* **Strategic Operationalization:** Translating visionary theory into patents and ventures.

## 2. Aesthetic & Design Rules (The "Academic Futurism" V2 Standard)

**Reference Implementation:** This project MUST mimic the architecture of the **Patrick Schimpl Academic Homepage (V50)** but with a distinct thematic skin.

* **Theme:** **"Earth/Symbiosis"**
  * **Primary Palette:** Deep Biological Greens, Earth Tones, Gold Accents (contrast with the Onyx/Bordeaux of the Patrick site).
  * **Typography:**
    * Heads: **Cinzel** (Noble, "Gothic Architecture").
    * Body: **Cormorant Garamond** (Scholarly, Classical).
    * Code/Tech: **JetBrains Mono**.
* **Architecture ("The Floor Tile" System):**
  * **True 3D Tiles:** 10px CSS 3D thickness (`rotateY(90deg)`).
  * **Glassmorphism:** Large blur/translucent backdrops for content clusters.
  * **Universal Link Parity:** Exact layout parity with the `patrick-homepage-univie` cluster (Blog, Projects, Resources).

## 3. Roadmap & Tasklist

### Phase 1: Infrastructure Upgrade (Immediate)

* [ ] **Sync Tools:** Copy latest `tools/build.py` and `tools/verify_links.py` from `patrick-homepage-univie` to ensure V50 compatibility.
* [ ] **Theme Definition:** Update `content/index.css` variables to reflect the Green/Gold "Symbiosis" palette.
* [ ] **Navigation:** Implement the "Logo-Dropdown" (Burger Menu Evolution) standard.

### Phase 2: Content Engine (The "ScholarFlow" Integration)

* **Deep Research Source:** `import/Building an Agential Research Agent.pdf`
  * *Action:* Ingest this document into the vector database to train the Agent Swarm.
* [ ] **Bibliography Ingestion:** Execute the "Holobiontic Bibliography Extraction" mission (Chapter 5.3 of Master's Thesis, pp. 168-217).
  * *Tool:* `scihub_fixed.py` (located in root `automation_tools/`).
  * *Target:* 600+ citations to be scraped and added to `content/research/`.

### Phase 3: Autonomous Operations

* [ ] **Agent Enrollment:** Deplay specific `Scout` and `Analyst` agents to monitor:
  * Synthetic Biology
  * Planetary Computing
  * Anticipatory Governance
* [ ] **Daily Digest:** Automate the "Morning Briefing" via `fetch_digest.py`.

## 4. Existing Resources & Documentation

### Documentation (Knowledge Base)

* **Vision:** `patrick_schimpl_academic_identity/artifacts/vision/holobiontic_civilization.md`
* **Architecture:** `univie_academic_homepages_infrastructure/artifacts/implementation/academic_hub_v50_project_architecture.md`
* **Acquisition:** `scholarflow_academic_acquisition/artifacts/use_cases/holobiontic_bibliography_handover.md`

### Code Assets

* **`tools/build.py`**: Core Static Site Generator (Python).
* **`automation_tools/scihub_fixed.py`**: (In Workspace Root) Primary paper acquisition tool.
* **`import/Building an Agential Research Agent.pdf`**: Primary theoretical corpus for the agent swarm.

## 5. Rules & Governance

1. **The "Hollow Content" Hazard:** Never overwrite existing research indices without a backup.
2. **Forensic Aesthetic Lock:** Do not deviate from the V50 "Floor Tile" geometry. Innovations should happen in *content*, not *layout*.
3. **Local-First Control:** All content changes originate in `content/` (Markdown/CSV), never via direct HTML edits in `site/`.
