# 🤖 Daily AI/LLM Paper Briefing

Automatically searches for AI/LLM papers daily and provides in-depth English analysis.

## 🎯 Track Structure

| Track | Name | Scope |
|-------|------|-------|
| 1 | ML Systems | training/serving systems, scheduling, parallelism, goodput, runtime |
| 2 | LLM Post-training | instruction tuning, RLHF, DPO/GRPO, reward modeling, alignment |
| 3 | RL for LLMs / Reasoning | reasoning RL, process reward, CoT efficiency, adaptive compute |
| 4 | Agents | tool use, multi-agent, planning, browser/computer-use, evaluation |
| 5 | Efficient LLM / Inference / Long Context | speculative decoding, KV cache, quantization, long context, sparsity |
| 6 | Diffusion Language Models | discrete/continuous diffusion LM, non-autoregressive generation, efficient dLLMs |

## 🏢 Monitored Institutions (Fresh Paper Filter)

OpenAI, Anthropic, Meta, NVIDIA, Together AI, Google DeepMind, Apple, ByteDance, Microsoft, DeepSeek, Alibaba, Tencent, UC Berkeley, Stanford, MIT, CMU

## ⚙️ How It Works

- **3 papers per day**: 2 Fresh (prioritizing papers from major institutions) + 1 from Track Pool (round-robin)
- **Analysis format**: Problem / Background / Methodology / Evaluation / Key Intuition
- **Slack delivery**: Automatically sent at 08:00 KST (channel or DM)
- **Deduplication**: 2-layer dedup (fresh_db + archive_db)
- **Track Pool**: Auto-crawled from 20+ Awesome repos + DBLP conferences (MLSys/ASPLOS/MICRO)
- **Fresh source**: HuggingFace Daily Papers (institution matching → Claude track classification) + arXiv keyword search (supplementary)
- **Analysis source**: Full arXiv HTML body + Figure 1 image extraction

---

## 🚀 Installation & Setup

### 1. Clone the repo

```bash
git clone https://github.com/minseo25/daily-ai-llm-papers.git
cd daily-ai-llm-papers
```

### 2. Set up uv environment

If using [uv](https://docs.astral.sh/uv/):

```bash
# Install uv (if not already installed)
curl -LsSf https://astral.sh/uv/install.sh | sh

# Create virtual environment + install dependencies
uv venv
source .venv/bin/activate
uv pip install -r requirements.txt
```

Using standard pip:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 3. Connect Slack Bot

1. Go to https://api.slack.com/apps → **Create New App** → **From scratch**
2. Name the app (e.g., `Daily Papers Bot`), select your Workspace
3. Navigate to **OAuth & Permissions**
4. Add the following **Bot Token Scopes**:
   - `chat:write` — send messages
   - `files:write` — upload Figure images
5. Click **Install to Workspace** at the top → copy the **Bot User OAuth Token** (`xoxb-...`)
6. Get your Slack **channel ID**:
   - The `/archives/C...` part of the channel link (e.g., `C0ANP5PD95X`)

### 4. Choose Claude Analysis Mode

Claude is used for paper analysis. Choose one of **two modes**:

| Mode | For | Configuration | Cost |
|------|-----|---------------|------|
| **Claude Code CLI** | Pro / Pro Max subscribers | Leave `ANTHROPIC_API_KEY` empty | Included in subscription |
| **Anthropic API** | API users | Set `ANTHROPIC_API_KEY` | Pay-per-token (~$0.03/day) |

- **Pro Max subscribers**: Leave `ANTHROPIC_API_KEY` empty and the system will automatically use the `claude` CLI. Claude Code must be installed.
- **API users**: Get an API key from https://console.anthropic.com and set it in your environment.

### 5. Set environment variables

```bash
cp .env.example .env
```

Open the `.env` file and fill in the following values:

```env
SLACK_BOT_TOKEN=xoxb-paste-your-bot-token-here
SLACK_CHANNEL=Cpaste-your-channel-id-here
ANTHROPIC_API_KEY=                       # Leave empty to use Claude CLI (Pro Max)
GITHUB_TOKEN=ghp-paste-your-github-token # Optional (reduces rate limit)
```

| Variable | Required | Description |
|----------|----------|-------------|
| `SLACK_BOT_TOKEN` | Yes | Slack Bot OAuth Token |
| `SLACK_CHANNEL` | Yes | Channel ID (`C...`) for channel delivery, Member ID (`U...`) for DM |
| `ANTHROPIC_API_KEY` | Optional | Anthropic API Key. Leave empty to use Claude CLI (requires Pro/Pro Max subscription) |
| `GITHUB_TOKEN` | No | GitHub Personal Access Token (reduces crawling rate limits) |

### 6. First run

```bash
source .venv/bin/activate

# 1) Build Track Pool (crawl Awesome repos) + test run
set -a && source .env && set +a && python3 daily_briefing.py --crawl --dry-run

# 2) After reviewing results, run for real (Slack delivery + Git push)
set -a && source .env && set +a && python3 daily_briefing.py
```

| Flag | Description |
|------|-------------|
| `--crawl` | Force crawl Awesome repos (normally auto-runs every 7 days) |
| `--dry-run` | Print analysis results to stdout only, no Slack delivery or Git push |
| `--no-git` | Send to Slack + save files, but skip git commit/push |
| (none) | Normal run |

### 7. Register crontab (automatic scheduling)

Auto-run daily at **08:00 KST** (when server timezone is KST):

```bash
crontab -e
```

Add the following line (adjust path to match your environment):

```cron
0 8 * * * cd /home/minseokim/daily-ai-llm-papers && bash run.sh
```

<!-- AUTO-GENERATED BELOW -->

## 📊 Recent Papers (by Track)

### Agents

| Date | Title | Link |
|------|-------|------|
| 2026-03-24 | DyTopo: Dynamic Topology Routing for Multi-Agent Reasoning via Semantic Matching | [arXiv](https://arxiv.org/abs/2602.06039) |
| 2026-03-24 | RuleSmith: Multi-Agent LLMs for Automated Game Balancing | [arXiv](https://arxiv.org/abs/2602.06232) |
| 2026-03-24 | CommCP: Efficient Multi-Agent Coordination via LLM-Based Communication with Conformal Prediction | [arXiv](https://arxiv.org/abs/2602.06038) |

## 📚 Briefing Archive

- [2026-03-24](./src/2026/03/2026-03-24.md)
