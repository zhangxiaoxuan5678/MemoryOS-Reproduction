# MemoryOS Reproduction

## Individual reproduction study on LoCoMo conv-26

This repository contains my completed MemoryOS reproduction and a comparison of mid-term retrieval capacities. Memory was built from the complete `conv-26` conversation: **19 sessions, 419 utterances and 215 memory pages**. Evaluation used 25 fixed questions, three capacity settings and three independent answer-generation runs per setting, producing **225 answers**.

The model was DeepSeek's official `deepseek-flash`, with thinking disabled. All runs loaded separate copies of the same frozen memory snapshot. Only `queue_capacity` changed between groups. The original retrieval algorithm, duplicate pages and simplified F1 scorer were retained.

### Results

| queue_capacity | Mean simplified F1 | Sample SD across three run means | Mean retrieved pages | Mean unique pages |
|---|---:|---:|---:|---:|
| 5 | 0.41735 | 0.02452 | 5.00 | 4.40 |
| 10 (original entry-point baseline) | 0.45233 | 0.00566 | 8.96 | 8.04 |
| 20 | 0.47478 | 0.01142 | 13.00 | 11.40 |

Capacity 20 had the highest overall mean on this question set, but capacity 5 performed best on open-domain questions. No significance test was conducted. **F1 is a word-set overlap score, not answer accuracy or the official LoCoMo metric.** The model substitution, single conversation, selected questions and shared code corrections prevent direct comparison with the paper's full benchmark.

The fixed questions were selected before evaluation: the first six in each of categories 1–3 and the first seven in category 4, then sorted by their original QA indices. Reference answers and evidence were kept out of generation inputs. Evaluation questions and generated answers were not written back to memory.

Evaluation used 450 requests, including 225 keyword-extraction calls and 225 answer-generation calls. There were no evaluation failures, truncated responses or automatic retries. The conservative estimate was CNY 4.549964 using the recorded peak, uncached rates; this is **not the verified account charge**.

See [EVALUATION_RESULTS.md](EVALUATION_RESULTS.md), [REPRODUCTION.md](REPRODUCTION.md) and [DIFFERENCES.md](DIFFERENCES.md) for the detailed records. The evaluation results, differences, running instructions and evidence guide are available in English. Historical progress records in REPRODUCTION.md and the original build guides retain their Chinese text.

### Verify the existing results without an API key

Run from the repository root. Python 3.11 and its standard library are sufficient. No `.env`, embedding downloads or third-party packages are needed for this check.

```sh
python3 -B eval/verify_submission.py

# Optional: save the recomputed scores to a new file. Existing files are not overwritten.
python3 -B eval/verify_submission.py --output runs/offline-recomputed-scores.json
```

The verifier disables networking, checks evidence hashes and the fixed question selection, validates the snapshot, reads the 225 saved valid answers and recomputes the original F1 statistics. It compares them with the archived scores. **It does not generate new answers or make paid API calls.**

[Evidence](evidence/README.md) includes the fixed questions, separate scoring references, frozen snapshot, original request logs, per-question answers and hash manifests. Key files are `evidence/scores.json`, `evidence/verification.json`, `evidence/evaluation-raw.zip` and `evidence/snapshot.zip`.

### Installation and local checks

The experiment ran on **macOS Apple Silicon arm64 with Python 3.11.9**. `requirements-macos.txt` records the installed direct dependencies. A clean installation from an empty environment has not been verified. The upstream subprojects retain their original requirements.

```sh
python3.11 -m venv ../.venv
../.venv/bin/python -m pip install -r requirements-macos.txt
HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 ../.venv/bin/python -B eval/checks/offline_check.py
HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 ../.venv/bin/python -B eval/checks/check_study_data.py
HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 ../.venv/bin/python -B eval/checks/check_build_runtime.py
```

Installing dependencies requires internet access. The listed checks use mock components and do not call paid models.

To restore the archived files into the original working layout on a fresh copy:

```sh
python3 -B eval/restore_evidence.py
python3 -B eval/restore_evidence.py --restore
python3 -B eval/score_evaluation.py --run-dir runs/eval-results-conv26-v1
```

The first command previews restoration. The second restores the verified evidence under the ignored `runs/` directory and refuses to overwrite existing destinations. The scoring command recomputes scores from saved answers without making model requests. None of these commands reruns the experiment.

### Configuration for any future generation runs

Review [RUNNING.md](RUNNING.md) before using the generation entry points. The completed results can be inspected without running them again. The historical build and evaluation guides record the original execution and budgets; they do not authorize further spending.

If a new generation run is separately planned, create `.env` from `.env.example` at the repository root only if it does not already exist. Set `OPENAI_API_KEY`, `OPENAI_BASE_URL` and `OPENAI_MODEL` locally. The recorded experiment used DeepSeek's official `deepseek-flash` consistently across stages. Keep credentials out of Git, terminal commands and logs. Do not run the upstream `main_loco_parse.py` full-dataset entry point to inspect the saved results.

Future generation also needs the pinned local embedding resources and the official offline tokenizer described in `RUNNING.md`. Default build and evaluation entry points provide previews; real requests require their explicit paid-execution flag. Models and prices can change, so historical rates are not a guarantee for a future run.

### Shared corrections and remaining limits

The reproduction unified client configuration, cached the original embedding model and corrected dialogue pairing to preserve all utterances. Construction stopped after three truncated outputs. The metadata limit changed from 100 to 300 tokens, and the profile-merge limit from 2,000 to 4,000 and then 16,000. The corresponding merge prompts and algorithm were unchanged. All capacity groups used the same final snapshot. Higher limits allowed completion but did not solve redundant or growing profiles.

### Source, versions and publication history

The original project is [BAI-LAB/MemoryOS](https://github.com/BAI-LAB/MemoryOS), based here on commit `587ed7755c7aed179965792830ff1b5ad9a6fa92`. The Apache-2.0 [LICENSE](LICENSE) is retained. The actual evaluation runtime was `fc48ea6fee9f013fe2476666611edfdb78786023`; the initial safe publication was `43241d859e66e78c66c8e21bc8279aa5f5044661`.

The public copy starts with a clean publication history because suspected hard-coded credentials were found in upstream examples and old history. The original local research history is retained. Historical runtime commits identify provenance but may not be checkable in this public copy. Later documentation commits do not reconstruct the original development history. Do not push the old research history or use `git push --mirror`. See [GITHUB_SUBMISSION.md](GITHUB_SUBMISSION.md) for the original publication procedure.

---

## Original upstream project documentation

The material below is retained from the original MemoryOS README for attribution and reference. Its benchmark claims, demonstrations and installation instructions describe the upstream project, not additional experiments completed in this reproduction. Use the reproduction-specific commands above to verify this submission.


<div align="center">
  <img src="https://github.com/user-attachments/assets/eb3b167b-1ace-476e-89dc-1a7891356e0b" alt="logo" width="400"/>
</div>
<p align="center">
    <a href="readme_cn.md" target="_blank">
    <img src="https://img.shields.io/badge/Readme-中文-blue" alt="Readme:中文">
  </a>
  <a href="https://arxiv.org/abs/2506.06326">
    <img src="https://img.shields.io/badge/Arxiv-paper-red" alt="Mem0 Discord">
  </a>
  <a href="#contact-us">
    <img src="https://img.shields.io/badge/Wechat-群二维码-green" alt="Mem0 PyPI - Downloads">
  </a>
  <a href="https://www.youtube.com/watch?v=WHQu8fpEOaU" target="blank">
    <img src="https://img.shields.io/badge/Youtube-Video-red" alt="Npm package">
  </a>
  <a href="https://discord.gg/SqVj7QvZ" target="_blank">
    <img src="https://img.shields.io/badge/Discord-Join_us-yellow" alt="Discord">
  </a>
  <a href="https://www.apache.org/licenses/LICENSE-2.0" target="_blank">
    <img src="https://img.shields.io/badge/License-Apache_2.0-blue" alt="License: Apache 2.0">
  </a>
</p>

<h5 align="center"> 🎉 If you like our project, please give us a star ⭐ on GitHub for the latest update.</h5>

**MemoryOS** is designed to provide a memory operating system for personalized AI agents, enabling more coherent, personalized, and context-aware interactions. Drawing inspiration from memory management principles in operating systems, it adopts a hierarchical storage architecture with four core modules: Storage, Updating, Retrieval, and Generation, to achieve comprehensive and efficient memory management. On the LoCoMo benchmark, the model achieved average improvements of **49.11%** and **46.18%** in F1 and BLEU-1 scores.

- **Paper**: <a href="https://arxiv.org/abs/2506.06326" target="_blank">https://arxiv.org/abs/2506.06326</a>
- **Website**: <a href="https://baijia.online/memoryos/" target="_blank">https://baijia.online/memoryos/</a>
- **Documentation**: <a href="https://bai-lab.github.io/MemoryOS/docs" target="_blank">https://bai-lab.github.io/MemoryOS/docs</a>
- **YouTube Video**: **MemoryOS MCP + RAG Agent That Can Remember Anything**
- <a href="https://www.youtube.com/watch?v=WHQu8fpEOaU ">https://www.youtube.com/watch?v=WHQu8fpEOaU </a>


<span id='features'/>

## ✨Key Features

* 🏆 **TOP Performance** in Memory Management
</br> The SOTA results in long-term memory benchmarks, boosting F1 scores by 49.11% and BLEU-1 by 46.18% on the LoCoMo benchmark.

* 🧠 **Plug-and-Play** Memory Management Architecture
</br>  Enables seamless integration of pluggable memory modules—including storage engines, update strategies, and retrieval algorithms.

* ✨ **Agent Workflow Create with Ease** (**MemoryOS-MCP**)
</br> Inject long-term memory capabilities into various AI applications by calling modular tools provided by the MCP Server.

* 🌐 **Universal LLM Support**
</br> MemoryOS seamlessly integrates with a wide range of LLMs (e.g., OpenAI, Deepseek, Qwen ...)




<span id='news'/>

## 🧠 Memory Family 

Welcome to our **Memory Family**, a research line dedicated to exploring AI Memory.

> [**Survey on AI Memory: Theories, Taxonomies, Evaluations, and Emerging Trends**](http://github.com/BAI-LAB/Survey-on-AI-Memory/blob/main/Survey%20on%20AI%20Memory.pdf)  
> **TL;DR:** Provides a unified theoretical framework for AI Memory, introducing a comprehensive taxonomy and systematically analyzing memory mechanisms, applications, and evaluation methods.  
> 📄 Paper: http://github.com/BAI-LAB/Survey-on-AI-Memory/blob/main/Survey%20on%20AI%20Memory.pdf

> [**LightSearcher: Efficient DeepSearch via Experiential Memory**](https://arxiv.org/abs/2512.06653)  
> **TL;DR:** Introduces experiential memory into deep search systems, enabling models to learn from successful reasoning trajectories and improve search efficiency.  
> 📄 Paper: https://arxiv.org/abs/2512.06653

> [**Memory OS of AI Agent**](https://arxiv.org/abs/2506.06326)  
> **TL;DR:** Proposes a memory operating system for AI agents that manages short-term, mid-term, and long-term personal memory through hierarchical storage, dynamic updating, retrieval, and generation, improving coherence and personalization in long conversations.  
> 📄 Paper: https://arxiv.org/abs/2506.06326

## 📣 Latest News
*   *<mark>[new]</mark>* 🔥🔥🔥  **[2026-01-15]**: **✨Released** [Survey on AI Memory: Theories, Taxonomies, Evaluations, and Emerging Trends](https://github.com/BAI-LAB/Survey-on-AI-Memory)!
*   *<mark>[new]</mark>* 🔥🔥  **[2025-09-11]**: **🚀Open-sourced** the [Playground platform](#playground-getting-started)!
*   *<mark>[new]</mark>* 🔥🔥  **[2025-08-21]**: **🎉Accepted**  by EMNLP 2025 main conference!
*   *<mark>[new]</mark>* 🔥 **[2025-07-15]**: **🔌 Support** for Vector Database [Chromadb](#memoryos_chromadb-getting-started)
*   *<mark>[new]</mark>* 🔥 **[2025-07-15]**: **🔌 Integrate** [Docker](#docker-getting-started) into deployment
*   *<mark>[new]</mark>*   **[2025-07-14]**: **⚡ Acceleration** of MCP parallelization 
*   *<mark>[new]</mark>*   **[2025-07-14]**: **🔌 Support** for BGE-M3 & Qwen3 embeddings on PyPI and MCP.
*   *<mark>[new]</mark>*   **[2025-07-09]**: **📊 Evaluation** of the MemoryOS on LoCoMo Dataset: Publicly Available [👉Reproduce](#reproduce).
*   *<mark>[new]</mark>*  **[2025-07-08]**: **🏆 New Config Parameter**
*   New parameter configuration: **similarity_threshold**. For configuration file, see 📖 [Documentation](https://bai-lab.github.io/MemoryOS/docs) page.
*   *<mark>[new]</mark>*   **[2025-07-07]**: **🚀5 Times Faster**
*   The MemoryOS (PYPI) implementation has been upgraded: **5 times faster** (reduction in latency) through parallelization optimizations.
*   *<mark>[new]</mark>*  **[2025-07-07]**: **✨R1 models Support Now**
*   MemoryOS supports configuring and using inference models such as **Deepseek-r1 and Qwen3..**
*   *<mark>[new]</mark>*  **[2025-07-07]**: **✨MemoryOS Playground Launched**
*   The Playground of **MemoryOS Platform** has been launched! [👉MemoryOS Platform](https://baijia.online/memoryos/). If you need an **Invitation Code**, please feel free to reach [Contact US](#community).
*   *<mark>[new]</mark>*   **[2025-06-15]**:🛠️ Open-sourced **MemoryOS-MCP** released! Now configurable on agent clients for seamless integration and customization. [👉 MemoryOS-MCP](#memoryos-mcp-getting-started).
*   **[2025-05-30]**: 📄 Paper-**Memory OS of AI Agent** is available on arXiv: https://arxiv.org/abs/2506.06326.
*   **[2025-05-30]**: Initial version of **MemoryOS** launched! Featuring short-term, mid-term, and long-term persona Memory with automated user profile and knowledge updating.

  

<span id='list'/>

## 🔥 MemoryOS Support List
<table>
  <thead>
    <tr>
      <th>Type</th>
      <th>Name</th>
      <th>Open&nbsp;Source</th>
      <th>Support</th>
      <th>Configuration</th>
      <th>Description</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <td rowspan="3">Agent Client</td>
      <td><strong>Claude Desktop</strong></td>
      <td>❌</td>
      <td>✅</td>
      <td>claude_desktop_config.json</td>
      <td>Anthropic official client</td>
    </tr>
    <tr>
      <td><strong>Cline</strong></td>
      <td>✅</td>
      <td>✅</td>
      <td>VS Code settings</td>
      <td>VS Code extension</td>
    </tr>
    <tr>
      <td><strong>Cursor</strong></td>
      <td>❌</td>
      <td>✅</td>
      <td>Settings panel</td>
      <td>AI code editor</td>
    </tr>
    <tr>
      <td rowspan="6">Model Provider</td>
      <td><strong>OpenAI</strong></td>
      <td>❌</td>
      <td>✅</td>
      <td>OPENAI_API_KEY</td>
      <td>GPT-4, GPT-3.5, etc.</td>
    </tr>
    <tr>
      <td><strong>Anthropic</strong></td>
      <td>❌</td>
      <td>✅</td>
      <td>ANTHROPIC_API_KEY</td>
      <td>Claude series</td>
    </tr>
    <tr>
      <td><strong>Deepseek-R1</strong></td>
      <td>✅</td>
      <td>✅</td>
      <td>DEEPSEEK_API_KEY</td>
      <td>Chinese large model</td>
    </tr>
    <tr>
      <td><strong>Qwen/Qwen3</strong></td>
      <td>✅</td>
      <td>✅</td>
      <td>QWEN_API_KEY</td>
      <td>Alibaba Qwen</td>
    </tr>
    <tr>
      <td><strong>vLLM</strong></td>
      <td>✅</td>
      <td>✅</td>
      <td>Local deployment</td>
      <td>Local model inference</td>
    </tr>
    <tr>
      <td><strong>Llama_factory</strong></td>
      <td>✅</td>
      <td>✅</td>
      <td>Local deployment</td>
      <td>Local fine-tuning deployment</td>
    </tr>
  </tbody>
</table>
All model calls use the OpenAI API interface; you need to supply the API key and base URL.



## 📑 Table of Contents

* <a href='#features'>✨ Features</a>
* <a href='#news'>🔥 News</a>
* <a href='#list'>🔍Support Lists </a>
* <a href='#structure'> 📁Project Structure</a>
* <a href='#pypi-mode'>🎯 Quick Start</a>
  * <a href='pypi-mode'>PYPI Install MemoryOS</a>
  * <a href='#MCP-mode'>MemoryOS-MCP</a>
  * <a href='#memoryos_chromadb-getting-started'>MemoryOS-chromadb</a>
  * <a href='#docker-getting-started'>Docker</a>
  * <a href='#playground-getting-started'>Playground</a>
* <a href='#todo'>☑️ Todo List</a>
* <a href='#reproduce'>🔬 How to Reproduce the Results in the Paper </a>
* <a href='#doc'>📖 Documentation </a>
* <a href='#cite'>🌟 Cite</a>
* <a href='#community'>🤝 Join the Community</a>

<span id='vedio'/>

<!--## Demo-->
<!--[![Watch the video](https://img.youtube.com/vi/y9Igs0FnX_M/maxresdefault.jpg)](https://youtu.be/y9Igs0FnX_M)-->


<span id='structure'/>

## 🏗️	System Architecture
<img src="https://github.com/user-attachments/assets/09200494-03a9-4b7d-9ffa-ef646d9d51f0" width="80%" alt="image">

## 🏗️ Project Structure

```
memoryos/
├── __init__.py            # Initializes the MemoryOS package
├── __pycache__/           # Python cache directory (auto-generated)
├── long_term.py           # Manages long-term persona memory (user profile, knowledge)
├── memoryos.py            # Main class for MemoryOS, orchestrating all components
├── mid_term.py            # Manages mid-term memory, consolidating short-term interactions
├── prompts.py             # Contains prompts used for LLM interactions (e.g., summarization, analysis)
├── retriever.py           # Retrieves relevant information from all memory layers
├── short_term.py          # Manages short-term memory for recent interactions
├── updater.py             # Processes memory updates, including promoting information between layers
└── utils.py               # Utility functions used across the library
```


<!--
## 📖 How It Works

1.  **Initialization:** `Memoryos` is initialized with user and assistant IDs, API keys, data storage paths, and various capacity/threshold settings. It sets up dedicated storage for each user and assistant.
2.  **Adding Memories:** User inputs and agent responses are added as QA pairs. These are initially stored in short-term memory.
3.  **Short-Term to Mid-Term Processing:** When short-term memory is full, the `Updater` module processes these interactions, consolidating them into meaningful segments and storing them in mid-term memory.
4.  **Mid-Term Analysis & LPM Updates:** Mid-term memory segments accumulate "heat" based on factors like visit frequency and interaction length. When a segment's heat exceeds a threshold, its content is analyzed:
    *   User profile insights are extracted and used to update the long-term user profile.
    *   Specific user facts are added to the user's long-term knowledge.
    *   Relevant information for the assistant is added to the assistant's long-term knowledge base.
5.  **Response Generation:** When a user query is received:
    *   The `Retriever` module fetches relevant context from short-term history, mid-term memory segments, the user's profile & knowledge, and the assistant's knowledge base.
    *   This comprehensive context is then used, along with the user's query, to generate a coherent and informed response via an LLM.
-->    

<span id='pypi-mode'/>

## 📖MemoryOS_PyPi Getting Started



### Prerequisites

*   Python >= 3.10
*   conda create -n MemoryOS python=3.10
*   conda activate MemoryOS

### Installation

#### Download from PyPi
```bash
pip install memoryos-pro -i https://pypi.org/simple
```
#### Download from GitHub (latest version)

```bash
git clone https://github.com/BAI-LAB/MemoryOS.git
cd MemoryOS/memoryos-pypi
pip install -r requirements.txt
```



### Basic Usage

```python

import os
from memoryos import Memoryos

# --- Basic Configuration ---
USER_ID = "demo_user"
ASSISTANT_ID = "demo_assistant"
API_KEY = "YOUR_OPENAI_API_KEY"  # Replace with your key
BASE_URL = ""  # Optional: if using a custom OpenAI endpoint
DATA_STORAGE_PATH = "./simple_demo_data"
LLM_MODEL = "gpt-4o-mini"

def simple_demo():
    print("MemoryOS Simple Demo")
    
    # 1. Initialize MemoryOS
    print("Initializing MemoryOS...")
    try:
        memo = Memoryos(
            user_id=USER_ID,
            openai_api_key=API_KEY,
            openai_base_url=BASE_URL,
            data_storage_path=DATA_STORAGE_PATH,
            llm_model=LLM_MODEL,
            assistant_id=ASSISTANT_ID,
            short_term_capacity=7,  
            mid_term_heat_threshold=5,  
            retrieval_queue_capacity=7,
            long_term_knowledge_capacity=100,
            #Support Qwen/Qwen3-Embedding-0.6B, BAAI/bge-m3, all-MiniLM-L6-v2
            embedding_model_name="BAAI/bge-m3"
        )
        print("MemoryOS initialized successfully!\n")
    except Exception as e:
        print(f"Error: {e}")
        return

    # 2. Add some basic memories
    print("Adding some memories...")
    
    memo.add_memory(
        user_input="Hi! I'm Tom, I work as a data scientist in San Francisco.",
        agent_response="Hello Tom! Nice to meet you. Data science is such an exciting field. What kind of data do you work with?"
    )
     
    test_query = "What do you remember about my job?"
    print(f"User: {test_query}")
    
    response = memo.get_response(
        query=test_query,
    )
    
    print(f"Assistant: {response}")

if __name__ == "__main__":
    simple_demo()
```
<span id='MCP-mode'/>

## 📖 MemoryOS-MCP Getting Started
### 🔧 Core Tools

#### 1. `add_memory`
Saves the content of the conversation between the user and the AI assistant into the memory system, for the purpose of building a persistent dialogue history and contextual record.

#### 2. `retrieve_memory`
Retrieves related historical dialogues, user preferences, and knowledge information from the memory system based on a query, helping the AI assistant understand the user’s needs and background.

#### 3. `get_user_profile`
Obtains a user profile generated from the analysis of historical dialogues, including the user’s personality traits, interest preferences, and relevant knowledge background.


### 1. Install dependencies
```bash
cd memoryos-mcp
pip install -r requirements.txt
```
### 2. configuration

Edit `config.json`：
```json
{
  "user_id": "user ID",
  "openai_api_key": "OpenAI API key",
  "openai_base_url": "https://api.openai.com/v1",
  "data_storage_path": "./memoryos_data",
  "assistant_id": "assistant_id",
  "llm_model": "gpt-4o-mini"
  "embedding_model_name":"BAAI/bge-m3"
}
```
### 3. Start the server
```bash
python server_new.py --config config.json
```
### 4. Test
```bash
python test_comprehensive.py
```
### 5. Configure it on Cline and other clients
Copy the mcp.json file over, and make sure the file path is correct.
```bash
command": "/root/miniconda3/envs/memos/bin/python"
#This should be changed to the Python interpreter of your virtual environment
```
## 📖MemoryOS_Chromadb Getting Started

### 1. Install dependencies
```bash
cd memoryos-chromadb
pip install -r requirements.txt
```
### 2. Test
```bash
The edit information is in comprehensive_test.py
    memoryos = Memoryos(
        user_id='travel_user_test',
        openai_api_key='',
        openai_base_url='',
        data_storage_path='./comprehensive_test_data',
        assistant_id='travel_assistant',
        embedding_model_name='BAAI/bge-m3',
        mid_term_capacity=1000,
        mid_term_heat_threshold=13.0,
        mid_term_similarity_threshold=0.7,
        short_term_capacity=2
    )
python3 comprehensive_test.py
# Make sure to use a different data storage path when switching embedding models.
```
## 📖Docker Getting Started
You can run MemoryOS using Docker in two ways: by pulling the official image or by building your own image from the Dockerfile. Both methods are suitable for quick setup, testing, and production deployment.
### Option 1: Pull the Official Image
```bash
# Pull the latest official image
docker pull ghcr.io/bai-lab/memoryos:latest

docker run -it --gpus=all ghcr.io/bai-lab/memoryos /bin/bash
```
### Option 2: Build from Dockerfile
```bash
# Clone the repository
git clone https://github.com/BAI-LAB/MemoryOS.git
          
cd MemoryOS

# Build the Docker image (make sure Dockerfile is present)
docker build -t memoryos .

docker run -it --gpus=all memoryos /bin/bash
```

## 📖Playground Getting Started

```bash
cd MemoryOS/memoryos-playground/memdemo/

python3 app.py
```
After launching the main interface, fill in the corresponding User ID, OpenAI API Key, Model, and API Base URL.
<img width="645" height="645" alt="image" src="https://github.com/user-attachments/assets/b88f965a-cae5-4ba5-8d29-b82f90e2dac9" />

After entering the system, you can use the Help button to view the functions of each button. 

The user's memory is stored under MemoryOS-main/memoryos-playground/memdemo/data

<img width="645" height="645" alt="image" src="https://github.com/user-attachments/assets/770857d7-5ea2-46b3-8f5c-8150c32d942a" />

## 🎯Reproduce
```bash
cd eval
Configure API keys and other settings in the code
python3 main_loco_parse.py
python3 evalution_loco.py
```


<span id='todo'/>

## ☑️ Todo List

MemoryOS is continuously evolving! Here's what's coming:

- **Ongoing🚀**: **Integrated Benchmarks**: Standardized benchmark suite with a cross-model comparison for Mem0, Zep, and OpenAI
- 🏗️ Enabling seamless Memory exchange and integration across diverse systems.

  

Have ideas or suggestions? Contributions are welcome! Please feel free to submit issues or pull requests! 🚀

<span id='doc'/>

## 📖 Documentation

A more detailed documentation is coming soon 🚀, and we will update in the [Documentation](https://bai-lab.github.io/MemoryOS/docs) page.

<span id='cite'/>

## 📣 Citation
**If you find this project useful, please consider citing our paper:**

```bibtex
@misc{kang2025memoryosaiagent,
      title={Memory OS of AI Agent}, 
      author={Jiazheng Kang and Mingming Ji and Zhe Zhao and Ting Bai},
      year={2025},
      eprint={2506.06326},
      archivePrefix={arXiv},
      primaryClass={cs.AI},
      url={https://arxiv.org/abs/2506.06326}, 
}
```

<span id='related'/>

<!--## 🔍 Related Projects -->
<!--on going-->

<span id='community'/>

## 🎯 Contact us
BaiJia AI is a research team guided by Associate Professor Bai Ting from Beijing University of Posts and Telecommunications, dedicated to creating emotionally rich and super-memory brains for AI agents. 

🤝 Cooperation and Suggestions: baiting@bupt.edu.cn 

📣Follow our **WeChat official account**, join the **WeChat group** or  <img src="https://img.shields.io/badge/Discord-yellow" alt="Discord"> https://discord.gg/SqVj7QvZ to get the latest updates.

<div style="display: flex; justify-content: center; gap: 20px;">
  <img src="https://github.com/user-attachments/assets/42651f49-f1f7-444d-9455-718e13ed75e9" alt="百家Agent公众号" width="250"/> 
  <img src="https://github.com/user-attachments/assets/a28d33b8-c999-4f96-969e-37d2ef4d6781" alt="微信群二维码" width="250"/>

</div>

## 🌟 Star History

[![Star History Chart](https://api.star-history.com/svg?repos=BAI-LAB/MemoryOS&type=Timeline)](https://www.star-history.com/#BAI-LAB/MemoryOS&Timeline)

## Disclaimer
This project, MemoryOS (Memory Operation System), is developed by the BaiJia AI team and has no affiliation with memoryOS (https://memoryos.com). The use of the name "MemoryOS" herein is solely for academic discussion purposes.


