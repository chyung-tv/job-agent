# JobLand Assistant: Vision and Architecture

## Goal
To simplify the job search process and maximize application quality by automating research and material preparation. The system transforms a broad search into a high-fidelity "application package" (Tailored CV, Cover Letter, and Research Report) sent directly to the user for final review.

## Core Workflow

1.  **Discovery (Search)**: Automate multi-engine searches (SerpAPI, Exa) to find fresh openings.
2.  **Extraction (Profile)**: Use `Docling` to parse the user's master CV/LinkedIn and create a "Living Profile".
3.  **Screening (Matcher)**: 
    *   A "ruthless" AI agent filters jobs by likelihood of landing.
    *   Provides a match score (0-100), identifying specific skill gaps and deal-breakers.
4.  **Intelligence (Researcher)**: For high-score jobs, a deep-dive agent researches the company's culture, mission, and recent news via Exa.
5.  **Fabrication (Generator)**:
    *   **Tailored CV**: Generate a full CV based on a Markdown/LaTeX template, re-prioritizing bullet points and keywords to match the specific job requirements.
    *   **Cover Letter**: Draft a personalized letter connecting the user's unique experience to the company's specific needs found during research.
6.  **Delivery (Notifier)**: Bundle the materials and send them to the user via Email (Nylas or Gmail API).

---

## Technical Modules

### 1. Search Service (`SerpApiJobsService`)
*   Current implementation handles Google Jobs pagination and factory instantiation.
*   Future: Support for additional job engines.

### 2. Profile Engine
*   **Tools**: `Docling` for high-fidelity PDF parsing.
*   **Role**: Converts the user's master experience into a structured data format for the Matcher.

### 3. High-Fidelity Matcher (`JobScreeningAgent`)
*   **Output**: `JobScreeningOutput` (Match Score, Probability, Reasons, Missing Skills).
*   **Role**: Only triggers the expensive research/generation phase for "High" probability matches.

### 4. Company Research Agent
*   **Search**: Uses Exa's `search` and `get_contents` to find culture and news.
*   **Output**: A concise "Company Dossier" used to inform the Generator.

### 5. Application Material Generator
*   **Engine**: `Jinja2` for template rendering.
*   **Logic**: Maps user experiences to job requirements to generate the most relevant CV possible.

### 6. Email Delivery Service
*   **Integration**: Nylas or Gmail API.
*   **Action**: Sends the application package to the user's inbox.

---

## Future Roadmap
*   **Interview Prep**: Generate a "Cheat Sheet" for the interview based on the company research.
*   **Application Tracking**: Automatically log which jobs were generated in a local DB or Google Sheets.
