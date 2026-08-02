# Product Specification: Classic Electronics Repair Assistant

**Version:** 0.6  
**Status:** Draft for implementation  
**License Intent:** Open-source / Freeware  
**Primary Goal:** Hardware preservation through accessibility

---

## 1. Overview

Build a free, open-source software system that assists people who already possess solid electronics skills in diagnosing, restoring, and modifying classic/vintage electronic devices they have limited prior experience with.

The system combines live visual observation of the workbench (cameras / OBS) with retrieval of schematics and service information, then uses multimodal LLMs to suggest logical next diagnostic steps and expected results. Interaction is designed to be primarily hands-free and eyes-free through speech (STT + TTS) so the operator can keep attention and hands on the work. It is intentionally designed for competent technicians facing unfamiliar platforms, not for complete beginners.

The project exists to encourage more people to take on classic hardware restoration and longevity work, thereby supporting the preservation of aging electronics.

---

## 2. Problem Statement

Many people have good general electronics knowledge (soldering, using a multimeter/scope, reading basic schematics, understanding power rails, digital logic, analog circuits, etc.) but lack the specific institutional knowledge of particular platforms (Apple II family, Commodore, Intellivision, Speak & Spell, early Macs, TRS-80, Atari, etc.).

Without that platform-specific knowledge, they are often reluctant to start projects on machines they have never worked on before. The result is that restorable hardware sits unused or is discarded.

Existing resources (service manuals, YouTube repair videos, forums) are valuable but require significant time to study before productive work can begin. A tool that can observe the current state of a board and tools in real time, cross-reference relevant documentation, and propose concrete next checks would lower the activation energy for these projects.

---

## 3. Goals

- Enable skilled electronics people to take on unfamiliar classic hardware with greater confidence.
- Support both pure restoration and practical longevity/modding work (capacitor upgrades, battery replacements, modern video outputs, etc.).
- Keep the tool fully local and open-source so users retain control of their data and workflow.
- Remain non-commercial and focused on hobbyist/preservation outcomes.
- Make the system useful even when the knowledge base is incomplete (graceful degradation).

### Non-Goals

- Fully autonomous repair.
- Replacement for fundamental electronics knowledge or safety practices.
- Serving complete beginners who do not already understand basic test equipment and component-level work.
- Commercial product or SaaS offering.
- Guaranteeing correct diagnosis (the human remains responsible).

---

## 4. Target Users

**Primary:** Electronics hobbyists and technicians who:
- Already know how to use a multimeter, oscilloscope, soldering iron, and basic diagnostic techniques.
- Want to work on classic/vintage platforms they have limited prior experience with.
- Own or can access a capable Windows gaming PC (or equivalent Linux machine).
- Care about hardware preservation and keeping old machines running.

**Secondary:** Experienced restorers who want a second opinion or faster lookup of expected values while working.

---

## 5. Core Capabilities

### 5.1 Live Visual Observation
- Accept one or more camera feeds (USB webcams, capture devices, or OBS virtual cameras / scenes).
- Continuously or on-demand analyze the visual scene: board under inspection, probe placement, multimeter/scope displays, visible damage, component markings, etc.
- Support multi-camera setups so the system can see both the overall board and a close-up of the probe or display simultaneously.

#### Visual Sampling Strategy
Workbench diagnostics are relatively slow compared with typical video workloads. High frame rates produce mostly redundant observations and waste compute given LLM analysis latency (commonly 1–4+ seconds per meaningful response on local hardware).

Recommended approach:
- **Background / continuous observation:** approximately 0.3–0.5 fps (one analysis every 2–5 seconds).
- **Active probing or interaction:** up to ~1 fps.
- **On-demand:** immediate analysis of the current frame(s) triggered by voice command (“look now”, “what do you see?”, “analyze this”) or by significant visual change (probe movement, new tool in view, large scene change, multimeter reading change).
- Multi-camera setups may use different rates (higher rate on the close-up/probe camera, lower rate on an overview camera).

Exact rates should be configurable. The values above are rational starting points to be refined through testing. The system should favor a hybrid model (low-rate continuous + change detection + explicit on-demand) over pure fixed high-FPS sampling.

### 5.2 Knowledge Retrieval (RAG)
- Ingest and index service manuals, schematics, board photos, component datasheets, and related documentation.
- Retrieve the most relevant schematic sections, expected voltage tables, common failure modes, and procedural guidance based on the current visual context and user queries.
- Handle multi-page PDFs and image-based schematics.

#### Documentation Strategy (Hybrid)
- **Primary path:** Users supply and import their own known-good schematics, service manuals, and notes. This remains the highest-quality and fully local mode.
- **Assisted discovery (optional):** At session start, or on request, the agent may search the web for candidate service manuals and schematics for the identified platform. It should prefer reputable sources (Internet Archive, established technical archives, manufacturer sites, well-known hobbyist repositories).
- The agent presents a short list of promising candidates (title, source, brief reason for relevance). The **user** chooses what to download and import into the local knowledge base.
- The system must **not** silently scrape or auto-ingest copyrighted manuals without explicit user selection.
- The tool must remain usable with zero pre-loaded documentation (graceful degradation to general electronics knowledge + live visual analysis), even if suggestions will be less precise.

### 5.3 Diagnostic Assistance
- Given the current visual state + retrieved knowledge, propose concrete next steps.
- Include expected results where possible (e.g., “Probe pin X of U12; expected ~5.0 V relative to ground”, “Check continuity between these two points; should be near 0 Ω”, “Look for bulging or leaking capacitors in this area”).
- Maintain short-term context of recent measurements and observations so suggestions build on prior steps.
- Support both structured diagnostic flows and free-form “what should I look at next?” interaction.

### 5.3.1 Initial Session Intake
- When a new diagnostic session is started (and the camera is active), the system should first prompt the operator—preferably by voice—to briefly describe:
  - The known fault or symptom (e.g., “it won’t power on at all”, “no video”, “keyboard dead”, “intermittent crashes”).
  - Any unusual observations from an initial visual inspection (burn marks, missing parts, corrosion, previous work, odd modifications, etc.).
- This initial context, combined with what the cameras currently see, is used to generate the first set of suggested checks.
- The intake should be lightweight and conversational; a short spoken reply is sufficient to get started.

### 5.4 Hands-Free Voice Interaction (STT + TTS)
- **Speech-to-Text (STT):** The operator must be able to issue queries, report observations, and request next steps using voice while keeping hands on the work and eyes on the board or instruments.
- **Text-to-Speech (TTS):** The system must speak its suggestions, expected values, and clarifying questions aloud so the operator does not need to look at a screen.
- Voice should be the primary interaction mode during active work. A conventional GUI remains available for setup, knowledge-base management, and review.
- Prefer local STT and TTS engines to maintain the local-first, privacy-preserving nature of the system.
- Support interruption and short back-and-forth dialogue (e.g., “What should I check next?”, “I’m measuring 4.2 volts on that pin”, “Is that within range?”).

### 5.5 Longevity & Modification Support
- Assist with common preservation tasks: capacitor replacement strategies, battery upgrades (e.g., NiCd → modern chemistry), clock battery remediation, etc.
- Help with practical modifications such as adding modern video outputs, RGB/SCART/HDMI adapters, or other quality-of-life improvements, when documentation exists.

### 5.6 Safety & Responsibility Framing
- Clearly communicate that the human operator remains responsible for all actions.
- Avoid authoritative language on high-risk procedures (high voltage, CRT work, etc.) and encourage verification against primary documentation.
- Voice responses should retain appropriate cautionary framing on risky procedures.

---

## 6. Technical Preferences & Constraints

- **Inference:** Local-first. Prefer open-weight multimodal models (examples: Qwen3-VL family, MiniCPM-o, and similar). Cloud APIs may be supported as optional fallbacks but must not be required.
- **Platform Priority:** Windows as the primary supported platform for end users (most accessible gaming PCs). Linux fully supported and preferred for development.
- **Capture:** Leverage OBS (open source) for flexible multi-camera and scene management. Direct camera access is also desirable.
- **Architecture Style:** Modular. Clear separation between:
  - Capture / vision input
  - Multimodal understanding
  - Retrieval (RAG)
  - Reasoning / agent loop
  - Speech input (STT) and speech output (TTS)
  - User interface
- **Extensibility:** Users must be able to add their own schematics, manuals, and private fine-tunes easily.
- **Performance Target:** Useful analysis latency on recommended hardware (typically a few seconds per observation cycle rather than true continuous 30 fps understanding). Voice interaction should feel responsive enough for natural workbench use. Visual sampling should follow the strategy in section 5.1 (default ~0.3–0.5 fps continuous, up to ~1 fps when active, plus on-demand triggers).
- **Audio:** Prefer local STT and TTS. Cloud speech services may be offered as optional fallbacks but must not be required.

---

## 7. Hardware Guidance (for documentation)

| Tier              | GPU VRAM   | Example Cards                          | Capability Level                                      |
|-------------------|------------|----------------------------------------|-------------------------------------------------------|
| Entry / Usable    | 12–16 GB   | RTX 3060 12GB, 4060 Ti 16GB, used 3080 | Quantized models, frame/clip analysis                 |
| Recommended       | 24 GB      | RTX 3090 / 4090, used workstation cards| Larger VLMs, smoother multi-image + longer context    |
| High-end          | 32 GB+     | RTX 5090 or multi-GPU                  | Maximum quality and future headroom                   |

**System:** 32 GB RAM minimum (64 GB preferred), modern multi-core CPU, fast NVMe storage, good USB bandwidth for cameras.

---

## 8. Knowledge & Data Strategy

- **Primary path:** Users supply their own schematics, service manuals, and notes. The system must make ingestion straightforward.
- **Assisted discovery:** The agent may help locate candidate documentation via web search, but final selection and import remain under user control (see section 5.2).
- **Optional curated content:** If permission is obtained from relevant content creators (e.g., Adrian’s Digital Basement, This Does Not Compute, and others), curated transcript or diagnostic segment datasets may be included under clear terms.
- **Permission-first approach:** Any use of third-party creator content for training or distribution requires explicit permission. The project will seek such permission and respect all boundaries set by creators.
- **Private fine-tuning:** The system should support users performing their own private LoRA / fine-tunes on models using data they have rights to.

---

## 9. Open Source & Distribution

- The complete workflow, tooling, and documentation will be published as freeware / open source on GitHub.
- A setup / installation script must be provided to help users get a working environment quickly. The script may be interactive where needed (e.g., choosing platform, model size, camera preferences, or optional components).
- No commercial licensing or paid tiers.
- Clear documentation of hardware requirements, installation, and how users can build their own knowledge bases.
- The project should remain usable and valuable even if no external creator datasets are ever included.

---

## 10. Creator Collaboration

- Contact relevant YouTube creators who produce high-quality classic electronics repair content to:
  1. Request permission for appropriate use of transcripts or diagnostic segments.
  2. Optionally invite them to test early versions on upcoming projects.
- Honest feedback (positive or negative) from domain experts is highly valued and may itself become useful content for the creators.
- All such collaboration is optional and must remain low-pressure.

---

## 11. Success Criteria

The project is successful if:

- A competent electronics person can use it to productively work on a machine they have never repaired before, with less time spent studying manuals up front.
- The tool provides genuinely useful next-step suggestions grounded in the actual visual state of the board and the retrieved documentation.
- The operator can interact primarily by voice while keeping hands and eyes on the work.
- Domain experts (including invited creators) can evaluate it and provide meaningful feedback.
- The open-source release is clear, documented, and usable by others on common Windows gaming hardware.
- It contributes, even modestly, to more classic hardware being restored and kept running.

---

## 12. Out of Scope (Initial Version)

- Automated component ordering or parts inventory.
- Direct control of test equipment (beyond reading displays visually).
- Mobile / phone-only primary interface.
- Guaranteed correctness of any diagnosis.
- Support for extremely high-voltage or life-critical systems without strong human oversight warnings.

---

## 13. Future Considerations (Not Required for v1)

- Deeper integration with specific diagnostic ROMs or test cartridges.
- Community-shared (properly licensed) knowledge packs for popular platforms.
- Improved continuous streaming / proactive observation modes.
- Better support for analog scope waveform interpretation.
- Multi-language documentation and UI.

---

**End of Specification**