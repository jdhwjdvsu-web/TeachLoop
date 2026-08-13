# Third-party components and references

TeachLoop is an original implementation. The repositories below are kept in
`D:\教师\references` as independent references and are not vendored into this
source tree.

## Runtime dependencies

- LangGraph — MIT — workflow orchestration
- Streamlit — Apache-2.0 — teacher workbench UI
- pandas — BSD-3-Clause — class-data aggregation
- Pydantic — MIT — structured data validation
- SymPy — BSD-3-Clause — mathematical verification
- pypdf — BSD-3-Clause — future textbook PDF ingestion
- python-docx — MIT — future lesson-plan export
- httpx — BSD-3-Clause — server-side OpenAI-compatible HTTP client
- PyYAML — MIT — subject-pack and education-skill manifest loading

## Reference repositories

### OpenTutor

- Source: https://github.com/zijinz456/OpenTutor
- Local reference: `D:\教师\references\OpenTutor`
- License: MIT
- Usage: architecture and learning-data-model reference only
- Pinned commit: `c1b7c376bd9df118cf2c2d3b683108a022d0cc84`

### EduAgent

- Source: https://github.com/StudentTraineeCenter/edu-agent
- Local reference: `D:\教师\references\EduAgent`
- License: MIT
- Usage: RAG, document-processing, and quiz-workflow reference only
- Pinned commit: `77c9ee5c12e99c6ab96143c9f035acce878b1311`

### education-agent-skills

- Source: https://github.com/GarethManning/education-agent-skills
- Local reference: `D:\教师\references\education-agent-skills`
- License: CC BY-SA 4.0
- Usage: 12 selected skill identifiers, orchestration metadata, and pedagogical design reference
- Pinned commit: `4be2795b574e91bdcbb6bda01ab235a05cfadbcc84`
- Attribution details: `education_skills/NOTICE.md`

No upstream source code or original `SKILL.md` body has been copied into TeachLoop at this stage.
