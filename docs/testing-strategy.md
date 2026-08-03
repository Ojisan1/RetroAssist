# RetroAssist Testing Strategy

**Status:** Draft for inclusion in the main execution plan  
**Last updated:** 2026-08-02

## 1. Testing Philosophy

RetroAssist is a multimodal, vision-grounded diagnostic assistant. Traditional unit tests alone are insufficient. We need a layered testing approach that validates:

1. Visual understanding and grounding
2. Agent reasoning given visual context
3. Graceful degradation (no camera / empty knowledge base)
4. End-to-end session flow
5. Safety language and uncertainty handling

Because real broken hardware is scarce and time-consuming to set up, we rely heavily on **synthetic and proxy visual data**.

## 2. Test Data Structure

```
tests/
├── unit/                     # Pure logic tests (config, safety, chunking, etc.)
├── integration/
├── e2e/
└── fixtures/
    ├── images/               # Curated keyframes for automated tests
    │   ├── power_supply/
    │   ├── logic_board/
    │   ├── meter_readings/
    │   └── empty_bench/
    ├── queries/              # Matching text queries / expected behaviors
    ├── sessions/             # Full scripted session transcripts
    └── private/              # gitignored – real YouTube-derived frames (local only)
```

### Data Handling Rules

- Anything under `fixtures/private/` **must** be gitignored and never committed.
- Public test images should be synthetic, public-domain, or clearly licensed.
- Real repair video frames are allowed only for local development and manual testing.
- Do not ship copyrighted YouTube frames with the project.

## 3. Automated Visual + Agent Tests (Core Regression Suite)

Use **curated screenshots + matching text queries**.

Each test case consists of:
- One or more images (overview + close-up preferred)
- A realistic technician query
- Optional expected behaviors (must mention certain checks, must include safety language, must cite retrieval, etc.)

### Example Test Cases

| ID       | Visual Context                        | Technician Query                                      | What we assert                                                                 |
|----------|---------------------------------------|-------------------------------------------------------|--------------------------------------------------------------------------------|
| PS-01    | Power supply board, obvious blown fuse| "No power at all. What should I check first?"         | Suggests visual inspection of fuse / fuse continuity + safety note about mains |
| PS-02    | Close-up of 5V regulator area         | "I'm getting 0V on the 5V rail"                       | Suggests checking input to regulator, output capacitors, etc.                  |
| LOGIC-01 | Busy logic board, no obvious damage   | "It powers on but no video. Where do I start?"        | Asks clarifying questions or suggests clock / reset / video section checks     |
| METER-01 | Multimeter showing 0.00V              | "Probing the 12V rail, reading zero"                  | Acknowledges the reading and suggests upstream checks                          |
| EMPTY-01 | Empty bench / no board                | "What do you see?"                                    | Correctly reports no board visible                                             |
| NO-KB-01 | Board image + empty knowledge base    | "Help me diagnose this Apple II"                      | Falls back to general electronics knowledge + vision; does not hallucinate specific manual pages |

These tests can be run headlessly with mocked or recorded VLM responses for speed, and occasionally against a real local model.

## 4. Live Proxy Testing (Manual + Exploratory)

Feed real electronics repair YouTube videos through OBS Virtual Camera into the running system.

**Workflow:**
1. Play a high-quality repair video (from well-known classic computing / arcade repair channels).
2. Route it through OBS → Virtual Camera.
3. Point RetroAssist at the virtual camera.
4. Interact via text or voice with realistic queries that match what is currently on screen.

This mode is excellent for:
- Testing continuous sampling and “look now”
- Discovering latency and timing issues
- Evaluating how well the vision + agent loop tracks a real repair session over time

This is primarily for human evaluation, not CI.

## 5. Full Session Script Tests

Create a small number of complete scripted sessions that include:
- Intake
- Multiple “look now” moments
- Measurement reports from the technician
- Follow-up questions
- Expected safety language

These can be run as integration tests with mocked vision/STT.

## 6. Mapping to Development Phases

| Phase              | Testing Focus                                      |
|--------------------|----------------------------------------------------|
| Phase 2 (Capture)  | Reliable frame capture from OBS Virtual Camera + real webcams |
| Phase 3 (Vision)   | Keyframe tests with known boards and meter readings |
| Phase 4 (RAG)      | Retrieval quality against sample manuals + empty KB behavior |
| Phase 5 (Agent)    | Full visual + query test cases (table above)       |
| Phase 6 (Speech)   | Same scenarios via voice (PTT and open-mic)        |
| Phase 7 (UI/E2E)   | Complete session using virtual camera + text/voice |

## 7. CI Recommendations

- Unit + integration tests run on every push.
- A small subset of visual keyframe tests run in CI (using recorded/mocked VLM responses).
- Full live virtual camera testing remains manual.
- Nightly or pre-release job can run a broader set of visual regression tests if a GPU runner is available.

## 8. Vertical Slice Acceptance Criteria

The early vertical slice (after Phase 1 + 2 + 4 + 5; vision = Phase 3 in the execution plan) must pass a basic set of the automated visual + agent test cases defined above before speech and polished UI work proceeds.

**Phase 5.5 status:** Gate GREEN on mocked path — run `retroassist test-visual --basic` or see [vertical-slice.md](vertical-slice.md).

## 9. Future Extensions

- Expand the keyframe library across more platforms (Apple II, C64, arcade boards, etc.).
- Add waveform / oscilloscope image understanding tests later.
- Community-contributed test cases (with proper licensing).
