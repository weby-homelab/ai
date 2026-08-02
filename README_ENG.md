<p align="center">
  <a href="./README.md">🇺🇦 Українська</a> | <strong>🇬🇧 English</strong>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/🇺🇦_Made_in-Ukraine-FFD700?style=for-the-badge&labelColor=0057B8" alt="Made in Ukraine">
  <img src="https://img.shields.io/badge/License-MIT-green?style=for-the-badge" alt="License MIT">
  <img src="https://img.shields.io/badge/AI-Local_First-blueviolet?style=for-the-badge" alt="AI Local First">
  <img src="https://img.shields.io/badge/Status-Active_Development-brightgreen?style=for-the-badge" alt="Status">
</p>

<h1 align="center">🧠 AI-HomeLab</h1>
<h3 align="center">Home AI Labs in Ukraine 🇺🇦</h3>

<p align="center">
  <strong>Local AI · Multi-Agent Systems · Blackout Resilience</strong>
</p>

---

Welcome to the central repository of the **AI-HomeLab** initiative! This project is designed to build a culture of responsible, secure, and practical use of AI models and autonomous agents in home environments on a budget within Ukraine.

> **Why is this necessary?** The boundary between a regular ChatGPT user and an engineer who knows how to locally deploy, quantize, and orchestrate AI agents defines the future of the technology job market and digital security in Ukraine.

---

## 📌 TABLE OF CONTENTS

* [📜 Memorandum and Project Philosophy](#-memorandum-and-project-philosophy)
* [⚡ Quick Start](#-quick-start)
* [💻 Minimum Requirements](#-minimum-requirements)
* [🛠️ Repository Structure](#️-repository-structure)
* [📚 Modules and Navigation](#-modules-and-navigation)
* [🗺️ Roadmap](#️-roadmap)
* [🔐 Security](#-security)
* [🤝 Join the Community](#-join-the-community)
* [📄 License](#-license)

---

## 📜 MEMORANDUM AND PROJECT PHILOSOPHY

Every AI-HomeLab community member and repository contributor shares four fundamental principles:

### 1. 🛡️ Technological Hygiene and Security

We follow safety and development hygiene principles. Previously, a complete ban on models from China was in place. Now, **the restriction on using certain Chinese local models (specifically, Qwen and DeepSeek series) has been lifted, strictly for local testing, comparison, and performance enhancements in agentic coding**. At the same time, any Russian AI models and tools (such as YandexGPT, GigaChat) remain under a **STRICT AND LIFETIME BAN**. High-quality reasoning models of Western origin (such as the Ornith series by the US-based DeepReinforce Team) are highly recommended.

> [!CAUTION]
> **Categorically Prohibited models and tools:** YandexGPT, GigaChat, or any other AI services and models from companies based in the aggressor state of the Russian Federation.

| Category | Tools |
|---|---|
| **LLM Models** | Meta LLaMA 4 (Scout/Maverick), Google Gemma 4, Mistral (Large 3 / Medium 3.5 / Small 4), Microsoft Phi-4 (Reasoning/Vision/Multimodal), Qwen 3.6 (Dense/MoE)*, DeepSeek-V4 (Flash/Pro)* |
| **Cloud APIs** | OpenAI (GPT-5.5/5.4, GPT-5.4 mini/nano), Anthropic (Claude 4.x / 4.6 / 4.5), Google (Gemini 3.5/3.1) |
| **Inference** | Ollama, vLLM, llama.cpp |
| **Orchestration** | LangGraph, CrewAI, PydanticAI |

*\*Note: Chinese models (Qwen, DeepSeek) are allowed strictly for local testing, comparison, and performance enhancements in agentic coding according to the Memorandum.*

### 2. 🔒 Locality and Data Sovereignty

Sensitive Ukrainian data (personal information, internal company documents, local registries) **must not leave the perimeter** of our country or personal computer.

We learn to deploy AI locally (via Ollama/vLLM), ensuring complete autonomy from third-party servers:

```mermaid
flowchart LR
    subgraph SECURE["🏠 Your Home Server — Secure Perimeter"]
        direction LR
        USER["🧑‍💻 User"]
        UI["🖥️ Open WebUI"]
        LLM["🧠 Ollama / vLLM"]
        DATA["📁 Your Data"]
        EMB["🔗 Embeddings"]

        USER -->|Request| UI
        UI -->|Inference| LLM
        LLM -->|Response| UI
        UI -->|Response| USER
        DATA -->|RAG| EMB
        EMB -->|Context| LLM
    end

    CLOUD["☁️ External Servers"]
    SECURE -.-x|"🚫 Data NEVER\nleaves the perimeter"| CLOUD

    style SECURE fill:#0d1117,stroke:#58a6ff,stroke-width:3px,color:#c9d1d9
    style USER fill:#1f6feb,stroke:#58a6ff,color:#ffffff
    style UI fill:#238636,stroke:#2ea043,color:#ffffff
    style LLM fill:#8957e5,stroke:#a371f7,color:#ffffff
    style DATA fill:#d29922,stroke:#e3b341,color:#0d1117
    style EMB fill:#f778ba,stroke:#f778ba,color:#0d1117
    style CLOUD fill:#da3633,stroke:#f85149,color:#ffffff
```

### 3. ⚡ Cost and Energy Efficiency

We create solutions adapted to **Ukrainian realities**. This means:

- **Maximum results on consumer hardware** — RTX 3060/4060/5060 or Apple Silicon
- **Use of free/cheap APIs** — Gemini 3.5 Flash / 3.1 Flash-Lite, GPT-5.4 mini for hybrid systems
- **Aggressive model quantization** — Q4/Q8 via GGUF to save VRAM
- **🔋 Blackout Resilience** — optimizing power consumption for stable lab operation from inverters and power stations (EcoFlow, Bluetti) during power outages

> [!TIP]
> A typical home lab consumes **80-150W** — less than an electric kettle. A single 2000Wh power station will last for **13-25 hours** of continuous operation.

### 4. 🚀 Practicality and Career Boost

A home lab is not just a hobby, it is **the best line on your CV**. We focus not on writing "prompts", but on developing complex logic:

- **Multi-agent systems** — autonomous AI agent teams solving complex tasks
- **RAG (Retrieval-Augmented Generation)** — searching and generating based on your documents
- **Type-safe integrations** — robust, production-ready code with validation via Pydantic
- **Real pet projects** — that convert into job offers and successful products

### 5. 🔄 Architectural Component Interaction

A modern home AI lab functions as a three-tier architecture (Orchestration ↔ Inference ↔ Tools), integrated via open and standardized protocols:

```mermaid
flowchart TD
    ORCH["🏗️ Orchestration & Logic\n(LangGraph / CrewAI / PydanticAI)"]
    LOCAL["🧠 Local Inference\n(Ollama / vLLM / llama.cpp)"]
    CLOUD["☁️ Cloud APIs\n(GPT-5.5 / Claude 4.6 / Gemini 3.5)"]
    MCP["🔌 Model Context Protocol\n(MCP Servers)"]
    RES["📁 Sources & Tools\n(Files, DBs, Web APIs)"]

    ORCH -->|API requests| LOCAL
    ORCH -->|API requests| CLOUD
    LOCAL -->|Universal Access| MCP
    CLOUD -->|Universal Access| MCP
    MCP -->|Read/Execute| RES

    style ORCH fill:#1f6feb,stroke:#58a6ff,color:#ffffff
    style LOCAL fill:#8957e5,stroke:#a371f7,color:#ffffff
    style CLOUD fill:#da3633,stroke:#f85149,color:#ffffff
    style MCP fill:#238636,stroke:#2ea043,color:#ffffff
    style RES fill:#d29922,stroke:#e3b341,color:#0d1117
```

* **Orchestration Layer** manages agent logic, conversation state persistence, and strict type validation at the Python level.
* **Inference Layer** executes models locally or invokes cloud engines using compatible APIs (OpenAI/Anthropic Messages API).
* **Tools Layer (MCP)** gives models standardized access to external resources without the need for custom connectors.

---

## ⚡ QUICK START

As of **August 2026 (08.2026)**, you can deploy a local AI laboratory using two primary scenarios:

### Option A: Standard Stack (Ollama + Open WebUI) — Recommended for Beginners

The easiest path for laptops and home servers.

1. **Install Ollama:**
   ```bash
   curl -fsSL https://ollama.com/install.sh | sh
   ```
2. **Download a modern model from the Gemma 4, Qwen 3.6, or DeepSeek V4 family:**
   ```bash
   # Ultra-fast multimodal edge model for low-spec PCs (up to 8GB RAM):
   ollama pull gemma4:e4b

   # New flagship 12B model with native audio and no encoders (requires 16GB RAM):
   ollama pull gemma4:12b

   # Leader in coding accuracy and RAG (requires 16GB RAM / GPU with 12GB+ VRAM):
   ollama pull qwen3.6:14b

   # Fast reasoning with CoT (requires 16GB RAM / GPU with 8GB+ VRAM):
   ollama pull deepseek-v4:flash
   ```
3. **Run Open WebUI in one click via Docker:**
   ```bash
   docker run -d \
     --name open-webui \
     -p 3000:8080 \
     --add-host=host.docker.internal:host-gateway \
     -v open-webui:/app/backend/data \
     -e OLLAMA_BASE_URL=http://host.docker.internal:11434 \
     --restart always \
     ghcr.io/open-webui/open-webui:main
   ```
   Open `http://localhost:3000` — your local ChatGPT is ready! 🎉

---

### Option B: Professional Developer Stack (llama-server + OpenCode) — WS Configuration

This stack is deployed on our dedicated **WS workstation (IP: 100.68.179.109 / 192.168.2.24)** for maximum speed (MTP, Flash Attention, 128K context).

1. **Start the compute core (Llama.cpp Server):**
   Create a systemd service `/etc/systemd/system/llama-server.service` for automatic startup (configured for Xeon E5-2666 v3 + 11GB VRAM on RTX 2080 Ti using local reasoning model Qwen3.6-35B-A3B):
   ```bash
   # start_llama.sh
   /root/llama.cpp/build/bin/llama-server \
       -m /root/llama-models/Qwen3.6-35B-A3B-uncensored-heretic-Native-MTP-Preserved-Q4_K_M.gguf \
       -ngl 14 -t 10 -c 128000 -fa on -np 1 -b 512 -ub 512 \
       -ctk q8_0 -ctv q8_0 -fit off \
       --spec-type draft-mtp --spec-draft-n-max 2 \
       --chat-template-kwargs "{\"preserve_thinking\":true}" \
       --host 0.0.0.0 --port 8080
   ```
2. **Configure OpenCode client (`~/.config/opencode/opencode.jsonc`):**
   Bind the client to the local server with support for automatic fallback to the cloud and preserving thinking process:
   ```json
   {
     "model": "local-infrastructure/qwen3.6-35b-a3b",
     "provider": {
       "local-infrastructure": {
         "npm": "@ai-sdk/openai-compatible",
         "name": "Local Infrastructure (WS)",
         "options": {
           "baseURL": "http://127.0.0.1:8080/v1",
           "apiKey": "sk-llama-cpp-local-token"
         },
         "models": {
           "qwen3.6-35b-a3b": {
             "name": "Qwen3.6 35B A3B Local (MTP)",
             "limit": { "context": 128000, "output": 4096 }
           }
         }
       }
     },
     "lsp": false
   }
   ```
3. **Start the client:**
   ```bash
   opencode --model local-infrastructure/qwen3.6-35b-a3b
   ```

#### 📊 Session Monitoring
For convenient real-time monitoring of active OpenCode sessions, it is recommended to use the terminal utility [llmtop](https://github.com/weby-homelab/llmtop) (a professional monitoring tool for local LLM sessions and agents developed by Weby Homelab):
* Visual display of context window usage (`context_percent` and `context_window`) based on input and output tokens.
* Monitoring of active sessions, processes, and limits.

> [!IMPORTANT]
> On Linux, make sure you have `sqlite3` installed in your system (required to read the OpenCode session database).

> [!NOTE]
> Detailed instructions for each platform (Windows/macOS/Linux) can be found in the [docs/setup/](./docs/setup/) section.

---

## 💻 MINIMUM REQUIREMENTS

| Component | Minimum | Recommended | Premium |
|---|---|---|---|
| **CPU** | 4 cores (Intel i5/Ryzen 5) | 8 cores (Intel i7/Ryzen 7) | Apple M2 Pro+ |
| **RAM** | 8 GB | 16 GB | 32+ GB |
| **GPU** | — (CPU-only) | RTX 3060 12GB | RTX 4060 Ti 16GB / RTX 5060 |
| **Storage** | 50 GB SSD | 256 GB NVMe | 1 TB NVMe |
| **OS** | Ubuntu 22.04+ / macOS 13+ | Ubuntu 24.04 / macOS 14+ | Proxmox VE 8+ |
| **Power** | 220V outlet | UPS 600VA | EcoFlow + inverter |

> [!IMPORTANT]
> **Apple Silicon (M1/M2/M3/M4)** is the ideal choice for Ukrainian realities: high performance with minimal power consumption (15-30W under load). Runs from any power bank via USB-C.

---

## 🛠️ REPOSITORY STRUCTURE

📂 [**`ai/`**](https://github.com/weby-homelab/AI-HOMELAB/blob/main)<br>
├── 📁 [**`benchmarks/`**](./benchmarks/) — *Hardware benchmarks and energy efficiency*<br>
│&nbsp;&nbsp;&nbsp;├── ⚡ [**`hardware_efficiency.md`**](./benchmarks/hardware_efficiency.md) — *GPU vs Apple Silicon (t/s/W)*<br>
│&nbsp;&nbsp;&nbsp;└── 🚀 [**`large_moe_optimization.md`**](./benchmarks/large_moe_optimization.md) — *Large MoE models optimization on WS (RTX 2080 Ti)*<br>
│<br>
├── 📁 [**`configs/`**](./configs/) — *Ready-made Docker Compose configurations*<br>
│&nbsp;&nbsp;&nbsp;├── ✅ [**`ollama/`**](./configs/ollama/) — *One-click Ollama + Open WebUI*<br>
│&nbsp;&nbsp;&nbsp;├── 🔌 [**`production-agent-stack/`**](./configs/production-agent-stack/) — *Comprehensive Stack (Ollama, LiteLLM, Qdrant, n8n, Open WebUI)*<br>
│&nbsp;&nbsp;&nbsp;├── ⏳ **`vllm/`** — `(coming soon)` *vLLM for production-grade inference*<br>
│&nbsp;&nbsp;&nbsp;├── ⏳ **`dify/`** — `(coming soon)` *Dify AI — no-code orchestration & RAG platform*<br>
│&nbsp;&nbsp;&nbsp;├── ⏳ **`offline-knowledge/`** — `(coming soon)` *Offline Kiwix + Wikipedia stack*<br>
│&nbsp;&nbsp;&nbsp;├── ⏳ **`mcp-stack/`** — `(coming soon)` *Local MCP servers stack (Filesystem, SQLite, Fetch)*<br>
│&nbsp;&nbsp;&nbsp;└── ⏳ **`dashboard/`** — `(coming soon)` *Starter AI-HomeLab Dashboard*<br>
│<br>
├── 📁 [**`templates/`**](./templates/) — *Templates and code examples*<br>
│&nbsp;&nbsp;&nbsp;├── 🧠 [**`langgraph_rag_agent.py`**](./templates/langgraph_rag_agent.py) — *Corrective RAG Agent (LangGraph + Qdrant)*<br>
│&nbsp;&nbsp;&nbsp;├── 🤖 [**`agent-code-cli/`**](./templates/agent-code-cli/) — *Claude Code Style Agent CLI (Ollama + Claude)*<br>
│&nbsp;&nbsp;&nbsp;├── 💾 [**`agent_persistent_memory.py`**](./templates/agent_persistent_memory.py) — *Long-term agent memory (SQLite + Ollama)*<br>
│&nbsp;&nbsp;&nbsp;├── ⏳ **`local_deep_research_agent.py`** — `(coming soon)` *Autonomous deep research agent (SearXNG/DuckDuckGo)*<br>
│&nbsp;&nbsp;&nbsp;├── ⏳ **`offline_wikipedia_rag.py`** — `(coming soon)` *RAG search template for local Kiwix (.zim) databases*<br>
│&nbsp;&nbsp;&nbsp;└── 📦 [**`requirements.txt`**](./templates/requirements.txt) — *Shared dependencies for out-of-the-box template usage*<br>
│<br>
├── 📁 **`projects/`** — `(coming soon)` *Ideas and implementations of pet projects*<br>
│&nbsp;&nbsp;&nbsp;├── ⏳ **`local-osint/`** — `(coming soon)` *Local OSINT assistants*<br>
│&nbsp;&nbsp;&nbsp;├── ⏳ **`biz-automation/`** — `(coming soon)` *Business routine automation tools*<br>
│&nbsp;&nbsp;&nbsp;└── ⏳ **`rag-pipeline/`** — `(coming soon)` *RAG pipeline for custom documents*<br>
│<br>
├── 📁 [**`docs/`**](./docs/) — *Documentation and guides*<br>
│&nbsp;&nbsp;&nbsp;├── 📁 [**`research/`**](./docs/research/) — *AI landscape research*<br>
│&nbsp;&nbsp;&nbsp;│&nbsp;&nbsp;&nbsp;├── 🔬 [**`ai-landscape-july-2026.md`**](./docs/research/ai-landscape-july-2026.md) — *AI models and stack report*<br>
│&nbsp;&nbsp;&nbsp;│&nbsp;&nbsp;&nbsp;├── 🔬 [**`nomad-odysseus-analysis.md`**](./docs/research/nomad-odysseus-analysis.md) — *Comparative analysis of N.O.M.A.D. and Odysseus*<br>
│&nbsp;&nbsp;&nbsp;│&nbsp;&nbsp;&nbsp;└── 🚀 [**`free-ai-tools-lifehacks_ENG.md`**](./docs/research/free-ai-tools-lifehacks_ENG.md) — *Free AI Tools and Lifehacks*<br>
│&nbsp;&nbsp;&nbsp;├── 📁 [**`setup/`**](./docs/setup/) — *Step-by-step guides for each OS*<br>
│&nbsp;&nbsp;&nbsp;│&nbsp;&nbsp;&nbsp;├── ⏱️ [**`first-model-15-min.md`**](./docs/setup/first-model-15-min.md) — *Quick start of the first model*<br>
│&nbsp;&nbsp;&nbsp;│&nbsp;&nbsp;&nbsp;├── 🔋 [**`blackout-guide.md`**](./docs/setup/blackout-guide.md) — *Outage energy efficiency guide*<br>
│&nbsp;&nbsp;&nbsp;│&nbsp;&nbsp;&nbsp;├── 🏗️ [**`reference-architectures.md`**](./docs/setup/reference-architectures.md) — *Reference Architectures (Tier 1/2/3)*<br>
│&nbsp;&nbsp;&nbsp;│&nbsp;&nbsp;&nbsp;└── 📊 [**`ai-ops.md`**](./docs/setup/ai-ops.md) — *Metrics, Monitoring & Observability (AIOps)*<br>
│&nbsp;&nbsp;&nbsp;├── 📁 [**`security/`**](./docs/security/) — *Security policies, audits, and model isolation*<br>
│&nbsp;&nbsp;&nbsp;│&nbsp;&nbsp;&nbsp;├── 🛡️ [**`model_isolation.md`**](./docs/security/model_isolation.md) — *Runtime isolation & TEE*<br>
│&nbsp;&nbsp;&nbsp;│&nbsp;&nbsp;&nbsp;├── 🛡️ [**`advanced_hardening.md`**](./docs/security/advanced_hardening.md) — *Deep isolation (VLAN, nftables, Gitleaks)*<br>
│&nbsp;&nbsp;&nbsp;│&nbsp;&nbsp;&nbsp;├── 🛡️ [**`model-vetting.md`**](./docs/security/model-vetting.md) — *Model vetting criteria*<br>
│&nbsp;&nbsp;&nbsp;│&nbsp;&nbsp;&nbsp;└── 🛡️ [**`threat-modeling.md`**](./docs/security/threat-modeling.md) — *Autonomous Agent Threat Modeling*<br>
│&nbsp;&nbsp;&nbsp;├── 📄 [**`templates_ENG.md`**](./docs/templates_ENG.md) — *Code templates and examples guide*<br>
│&nbsp;&nbsp;&nbsp;└── ✅ [**`quantization.md`**](./docs/setup/quantization.md) — *Quantization guide (Q4/Q8/GGUF)*<br>
│<br>
├── 📄 [**`README.md`**](./README.md) — *Ukrainian version*<br>
├── 📄 [**`README_ENG.md`**](./README_ENG.md) — *This file (ENG)*<br>
├── 📄 [**`CONTRIBUTING.md`**](./CONTRIBUTING.md) — *Contributor guide*<br>
├── 📄 [**`SECURITY.md`**](./SECURITY.md) — *Security policy*<br>
├── 📄 [**`LICENSE`**](./LICENSE) — *MIT License*<br>
└── 📄 [**`ROADMAP.md`**](./ROADMAP.md) — *Project roadmap*

---

## 📚 MODULES AND NAVIGATION

For convenience, all learning and practical materials in the repository are divided into thematic sections:

### 🚀 1. Quick Start & Basic Infrastructure
| Module & Link | Description | Main Files | Status |
| :--- | :--- | :--- | :--- |
| ⏱️ [**15-Min Setup**](./docs/setup/first-model-15-min.md) | Quick step-by-step launch of Ollama, downloading your first model, and chatting via the Open WebUI Docker container. | [`first-model-15-min.md`](./docs/setup/first-model-15-min.md) | ✅ Done |
| 🐳 [**Ollama + Open WebUI**](./configs/ollama/) | Docker Compose configuration for launching services together (CPU/GPU profiles, secure port binding). | [`docker-compose.yml`](./configs/ollama/docker-compose.yml) | ✅ Done |
| 🏗️ [**Reference Architectures**](./docs/setup/reference-architectures.md) | Reference hardware configurations (Tier 1/2/3) for deploying home AI labs from $300 to $3000+. | [`reference-architectures.md`](./docs/setup/reference-architectures.md) | ✅ Done |
| 🔌 [**Production Agent Stack**](./configs/production-agent-stack/) | Configuration of the full infrastructure stack (Ollama, LiteLLM, Qdrant, n8n, Open WebUI) for multi-agent systems. | [`docker-compose.yml`](./configs/production-agent-stack/docker-compose.yml) | ✅ Done |
| 🚀 [**Free AI Tools & Hacks**](./docs/research/free-ai-tools-lifehacks_ENG.md) | List of free development tools and 7 practical lifehacks to improve model response quality. | [`free-ai-tools-lifehacks_ENG.md`](./docs/research/free-ai-tools-lifehacks_ENG.md) | ✅ Done |

### 🧠 2. Development, Templates & Agents
| Module & Link | Description | Main Files | Status |
| :--- | :--- | :--- | :--- |
| 🤖 [**Agent CLI**](./templates/agent-code-cli/) | Claude Code style console AI agent (secure working directory, bash execution with permission, interactive diff preview). | [`cli.py`](./templates/agent-code-cli/agent_code/cli.py) | ✅ Done |
| 🧠 [**CRAG Agent**](./templates/langgraph_rag_agent.py) | Corrective RAG (CRAG) agent built with LangGraph + Qdrant using a cyclic evaluation and query reformulation graph. | [`langgraph_rag_agent.py`](./templates/langgraph_rag_agent.py) | ✅ Done |
| 🧠 [**Agent Memory**](./templates/agent_persistent_memory.py) | Session-persistent long-term memory template (SQLite + Ollama nomic-embed-text) for saving facts and decisions between runs. | [`agent_persistent_memory.py`](./templates/agent_persistent_memory.py) | ✅ Done |
| 📄 [**Templates Guide**](./docs/templates_ENG.md) | Comprehensive step-by-step guide for setting up and running all repository code templates. | [`templates_ENG.md`](./docs/templates_ENG.md) | ✅ Done |

### ⚡ 3. Hardware & Energy Efficiency
| Module & Link | Description | Main Files | Status |
| :--- | :--- | :--- | :--- |
| 🔋 [**Blackout Guide**](./docs/setup/blackout-guide.md) | Configuring the lab to operate during power outages (Nvidia Power Limit, CPU thread limits, running from EcoFlow, Starlink 12V PoE, Tailscale, Offline RAG). | [`blackout-guide.md`](./docs/setup/blackout-guide.md) | ✅ Done |
| ⚡ [**Hardware Benchmarks**](./benchmarks/hardware_efficiency.md) | Comprehensive analysis of GPU vs Apple Silicon (tokens/second/Watt), cold start analysis, and VRAM contention. | [`hardware_efficiency.md`](./benchmarks/hardware_efficiency.md) | ✅ Done |
| 🚀 [**MoE Optimization**](./benchmarks/large_moe_optimization.md) | Optimization and comparative benchmarking of large MoE models (Gemma 4 26B, Qwen 3.6 35B, Ornith 1.0 35B) on WS. | [`large_moe_optimization.md`](./benchmarks/large_moe_optimization.md) | ✅ Done |
| 📊 [**AIOps & Observability**](./docs/setup/ai-ops.md) | Monitoring hardware (GPU Power Draw), inference metrics (Ollama/vLLM /metrics), and agent tracing via Langfuse. | [`ai-ops.md`](./docs/setup/ai-ops.md) | ✅ Done |
| 📦 [**Quantization Guide**](./docs/setup/quantization.md) | Guide to model quantization: format selection (Q4/Q8/GGUF), VRAM budgeting, quantizing with `llama.cpp`, and Ollama integration. | [`quantization.md`](./docs/setup/quantization.md) | ✅ Done |

### 🛡️ 4. Security, Hardening & Model Isolation
| Module & Link | Description | Main Files | Status |
| :--- | :--- | :--- | :--- |
| 🛡️ [**Advanced Hardening**](./docs/security/advanced_hardening.md) | VLAN isolation of the IoT segment, nftables firewall for Proxmox host, Docker daemon security, and Gitleaks pre-commit linter. | [`advanced_hardening.md`](./docs/security/advanced_hardening.md) | ✅ Done |
| 🛡️ [**Model Isolation**](./docs/security/model_isolation.md) | Model execution isolation using gVisor, Firecracker, WASM, Trusted Execution Environments (TEE), and Zero-Trust networks. | [`model_isolation.md`](./docs/security/model_isolation.md) | ✅ Done |
| 🛡️ [**Model Vetting**](./docs/security/model-vetting.md) | Model vetting criteria (model hygiene, inference privacy, safe formats GGUF/Safetensors, and licensing compliance). | [`model-vetting.md`](./docs/security/model-vetting.md) | ✅ Done |
| 🛡️ [**Threat Modeling**](./docs/security/threat-modeling.md) | Threat modeling for autonomous agents (Prompt Injection, Tool Poisoning, Agent Escape, Secrets Leakage). | [`threat-modeling.md`](./docs/security/threat-modeling.md) | ✅ Done |
| 🔐 [**Security Policy**](./SECURITY.md) | Overall project security policies, model hygiene, sensitive data isolation, and credential management. | [`SECURITY.md`](./SECURITY.md) | ✅ Done |

### 🔬 5. Strategy, Roadmap & Community
| Module & Link | Description | Main Files | Status |
| :--- | :--- | :--- | :--- |
| 🔬 [**AI Landscape 2026**](./docs/research/ai-landscape-july-2026.md) | AI market analysis as of July 2026: models, APIs, frameworks, RAG, MCP, stealth browsers, and assistants. | [`ai-landscape-july-2026.md`](./docs/research/ai-landscape-july-2026.md) | ✅ Done |
| 🗺️ [**Roadmap**](./ROADMAP.md) | Detailed project roadmap: Phase 1 (Foundation), Phase 2 (Practice), Phase 3 (Community). | [`ROADMAP.md`](./ROADMAP.md) | ✅ Done |
| 🤝 [**Contributing**](./CONTRIBUTING.md) | Contributor guide: creating Issues, working on feature branches, and submitting Pull Requests. | [`CONTRIBUTING.md`](./CONTRIBUTING.md) | ✅ Done |

---

## 🗺️ ROADMAP

> [!NOTE]
> As of **August 2026 (08.2026)**, Phase 1 (Foundation) has been fully completed ahead of schedule! The project is actively working on Phase 2. Hardware benchmarks have been successfully conducted on the WS workstation using Gemma 4 26B (MoE), Qwen 3.6 35B (MoE, MTP), and Ornith 1.0 35B (MoE, MTP) models.

### 🏁 Phase 1 — Foundation (Q3 2026) — 🎉 Completed ahead of schedule!

- [x] Memorandum and project philosophy
- [x] Docker Compose for Ollama + Open WebUI
- [x] Benchmarks of RTX 3060/4060/5060 with quantized models
- [x] Guide: "First model in 15 minutes"
- [x] LangGraph RAG pipeline template (CRAG Agent)
- [x] Deep isolation of home lab (Advanced Hardening)
- [x] Energy efficiency benchmarks (t/s/W)
- [x] Console AI coding agent (Claude Code style CLI)

### 🚀 Phase 2 — Practice (Q4 2026) — ⏳ In Progress

- [ ] **LangGraph / PydanticAI multi-agent template** for business automation (Stateful workflows with human-in-the-loop and durable checkpointing in PostgreSQL/SQLite)
- [x] Blackout guide: configuring the lab to run on EcoFlow, Starlink 12V PoE, Tailscale, Offline RAG
- [ ] **Local Deep Research agent on LangGraph / PydanticAI** with SearXNG/DuckDuckGo integration and automated generative report synthesis
- [ ] **Guide and compose configs for local MCP servers** (Filesystem, SQLite, Git, Fetch) and their native usage in Cursor/Windsurf/Claude Code
- [ ] **Universal local AI assistant (based on OpenClaw / LangGraph)** with direct secure tool access (Bash, Browser, Filesystem) and gVisor/Docker isolation
- [ ] **Hybrid Routing**: Smart load balancing between local SLMs (Gemma 4 12B/26B) for cheap/private steps and cloud APIs (Claude 4.x Sonnet, GPT-5) for complex logical reasoning, leveraging Prompt Caching
- [ ] **Observability & Tracing**: Templates for integrating local stacks with OpenTelemetry and tracing services (Pydantic Logfire, Langfuse)
- [ ] **Offline knowledge base and RAG**: Docker Compose stack for Kiwix + Wikipedia (.zim) with offline RAG embeddings configuration
- [ ] **Configuration of local IDE tools (Continue.dev, Aider)** using Gemma 4 (12B/26B MoE) models and MTP (Multi-Token Prediction) drafting to speed up code generation
- [x] Session memory integration (AgentMemory) into agent templates
- [x] Reference hardware architectures (Tier 1/2/3) for local AI
- [x] Comprehensive Docker Compose stack (Ollama, LiteLLM, Qdrant, n8n, Open WebUI) for multi-agent systems
- [x] Threat modeling for autonomous AI agents (Threat Modeling)
- [x] Hardware metrics gathering and request tracing configuration (AIOps & Observability)

### 🌟 Phase 3 — Community (Q1 2027) — 📅 Planned

- [ ] **Continuous Benchmarking CI/CD**: Automated pipelines for regular speed (t/s/W) and accuracy testing of local models during driver updates or new version releases
- [ ] **LLM-as-a-Judge**: Accuracy and compliance evaluation templates (validation pipelines) for local RAG systems without sending data to the cloud
- [ ] **Native voice assistant (Direct Speech-to-Speech)**: Integration and execution of the Gemma 4 12B (encoder-free native audio) model on local hardware without additional ASR (Whisper) / TTS layers
- [ ] **AI-HomeLab Portal**: Web dashboard for monitoring local server status, VRAM, active inferences, and agent logs
- [ ] **Practical guide on vLLM & llama.cpp**: PagedAttention tuning, KV-cache offloading, and Speculative Decoding (MTP drafters) configuration
- [ ] Partnerships with Ukrainian AI communities and publishing articles (DOU.ua, dev.to)
- [ ] Monthly digest of new local models and developer tools

---

## 🔐 SECURITY

We take security seriously. Before using any model in your lab:

1. **Verify origin** — the model must have a transparent license and known dataset sources
2. **Isolate environment** — run models in Docker containers or virtual machines
3. **Do not share sensitive data** — only send anonymized data to cloud APIs
4. **Update regularly** — track CVEs and security updates for tools

> Read more: [`SECURITY.md`](./SECURITY.md)

---

## 🤝 JOIN THE COMMUNITY

### 💬 Communication Channels

| Platform | Link | Purpose |
|---|---|---|
| **Telegram** | *Coming soon* | Discussion of hardware, architecture, GPU trade |
| **GitHub Discussions** | [Discussions](https://github.com/weby-homelab/AI-HOMELAB/discussions) | Questions, ideas, RFCs |
| **Issues** | [Issues](https://github.com/weby-homelab/AI-HOMELAB/issues) | Bug reports and feature requests |

### 🤲 How to Contribute

Found a cool model, optimized a config for EcoFlow, or wrote a useful local agent?

1. **Fork** this repository
2. Create an **Issue** describing your idea
3. Create a branch `feature/your-feature`
4. Make a **Pull Request** with a detailed description

> Read more: [`CONTRIBUTING.md`](./CONTRIBUTING.md)

---

## 📄 License

This project is licensed under the [MIT License](./LICENSE).

---

<p align="center">
  <strong>🇺🇦 Let's build Ukraine's AI future together!</strong>
</p>

<p align="center">
  <sub>Created with ❤️ for the Ukrainian tech community</sub>
</p>
