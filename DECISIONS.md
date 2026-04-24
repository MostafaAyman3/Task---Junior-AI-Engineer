# Architectural Decisions & Tradeoffs (Interview Defense Shield)

This document outlines the core architectural choices made during the construction of the AI Data Assistant. It serves to defend the methodology used to achieve a resilient, production-ready system.

## 1. No Frameworks (Why No LangChain/LlamaIndex)
**Decision:** The agent orchestration, chaining, and prompt composition were implemented from scratch in pure Python without utilizing popular AI frameworks like LangChain, LlamaIndex, or CrewAI.

**Justification:** 
We bypassed bloated frameworks to achieve zero abstraction magic and absolute control over the REPL loop. Frameworks often hide the prompt structures, making debugging a nightmare when the LLM hallucinates or triggers a parsing error. By building the router natively, we achieved significantly lower latency and highly predictable JSON parsing. We know exactly what goes into the context window and exactly how it is extracted, allowing us to enforce strict bounds (e.g., maximum 12 history messages) to prevent `Payload Too Large` errors effortlessly.

## 2. In-Memory DataStore & Write-Through Persistence
**Decision:** We load the entire Excel workbooks into an in-memory `pandas.DataFrame` at startup, applying a "write-through" cache pattern where disk saves only trigger on mutation (insert/update/delete).

**Justification:**
We defended against over-engineering. Setting up a complex SQL database (PostgreSQL/SQLite) or a vector store for small-to-medium Excel files (< 1 million rows) introduces unnecessary schema migrations and I/O bottlenecks. Using Pandas in RAM allows for lightning-fast querying, instantaneous statistical aggregations (`groupby`, `mean`), and robust handling of missing `NaN` values. The write-through pattern ensures zero data loss by immediately flushing any mutation back to the `.xlsx` file on disk while keeping the blazing-fast read speeds intact.

## 3. Resilient Routing & Right-Sizing
**Decision:** The system utilizes `openai/gpt-oss-20b` (on Groq) as the primary router model, combined with an exponential backoff/fallback chain defaulting down to various `gemini` models.

**Justification:**
We optimized for both speed and cost-effectiveness by choosing a fast, right-sized open-source model through the Groq LPU engine for instantaneous logic routing. However, third-party APIs are inherently unstable (rate limits, internal 500s). To ensure a crash-proof, highly available system, we built a fallback matrix. If Groq times out or fails to parse, the system catches the exception gracefully and seamlessly redirects the payload to Google's Gemini models without the user ever noticing the downtime.

## 4. JSON Tool Calling vs. Python `exec()`
**Decision:** The LLM is strictly constrained to output structured JSON dictating which tools to use. We completely rejected the paradigm of allowing the LLM to write and execute arbitrary Python code.

**Justification:**
Security is paramount. Using `exec()` or `eval()` on LLM-generated code opens severe Remote Code Execution (RCE) vulnerabilities. Pre-defined deterministic Python functions (`execute_tool`) ensure that only intended, safe queries map to the DataFrame.

## 5. Destructive Action Guardrails
**Decision:** `update` and `delete` tools require a manual `confirm: true` flag that the LLM cannot bypass on its first generation pass.

**Justification:**
Data integrity cannot be fully entrusted to an autonomous agent. Enforcing a mandatory preview and user handshake prevents catastrophic data wiping caused by a hallucinated entity ID or a misunderstood natural language prompt.