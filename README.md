# 🤖 Daily AI/LLM Paper Briefing

AI/LLM 관련 논문을 매일 자동으로 검색하고 한국어로 깊이 있게 분석합니다.

## 🎯 트랙 구조

| Track | 이름 | 범위 |
|-------|------|------|
| 1 | ML Systems | training/serving systems, scheduling, parallelism, goodput, runtime |
| 2 | LLM Post-training | instruction tuning, RLHF, DPO/GRPO, reward modeling, alignment |
| 3 | RL for LLMs / Reasoning | reasoning RL, process reward, CoT efficiency, adaptive compute |
| 4 | Agents | tool use, multi-agent, planning, browser/computer-use, evaluation |
| 5 | Efficient LLM / Inference / Long Context | speculative decoding, KV cache, quantization, long context, sparsity |
| 6 | Diffusion Language Models | discrete/continuous diffusion LM, non-autoregressive generation, efficient dLLMs |

## 🏢 모니터링 기관 (Fresh 논문 필터)

OpenAI, Anthropic, Meta, NVIDIA, Together AI, Google DeepMind, Apple, ByteDance, Microsoft, DeepSeek, Alibaba, Tencent, UC Berkeley, Stanford, MIT, CMU

## ⚙️ 운영 방식

- **매일 3편**: Fresh 2편 (주요 기관 논문 우선) + Track Pool 1편 (round-robin)
- **분석 형식**: Problem / Background / Methodology / Evaluation / Key Intuition
- **Slack 전송**: KST 08:00 자동 전송 (채널 또는 DM)
- **중복 방지**: 2-layer dedup (fresh_db + archive_db)
- **Track Pool**: 20개 Awesome repo + DBLP 컨퍼런스(MLSys/ASPLOS/MICRO)에서 자동 크롤링
- **Fresh 소스**: HuggingFace Daily Papers (기관 매칭 → Claude 트랙 분류) + arXiv 키워드 검색 (보조)
- **분석 소스**: arXiv HTML 본문 전체 + Figure 1 이미지 추출

---

## 🚀 설치 및 설정

### 1. 레포 클론

```bash
git clone https://github.com/minseo25/daily-ai-llm-papers.git
cd daily-ai-llm-papers
```

### 2. uv 환경 설정

[uv](https://docs.astral.sh/uv/)를 사용하는 경우:

```bash
# uv 설치 (없는 경우)
curl -LsSf https://astral.sh/uv/install.sh | sh

# 가상환경 생성 + 의존성 설치
uv venv
source .venv/bin/activate
uv pip install -r requirements.txt
```

기존 pip을 사용하는 경우:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 3. Slack Bot 연결

1. https://api.slack.com/apps 접속 → **Create New App** → **From scratch**
2. App 이름 지정 (예: `Daily Papers Bot`), Workspace 선택
3. **OAuth & Permissions** 메뉴로 이동
4. **Bot Token Scopes**에 아래 권한 추가:
   - `chat:write` — 메시지 전송
   - `files:write` — Figure 이미지 업로드
5. 상단 **Install to Workspace** 클릭 → **Bot User OAuth Token** 복사 (`xoxb-...`)
6. 전송할 Slack **채널 ID** 확인:
   - 채널 링크의 `/archives/C...` 부분 (예: `C0ANP5PD95X`)

### 4. Claude 분석 모드 선택

논문 분석에 Claude를 사용합니다. **두 가지 모드** 중 하나를 선택하세요:

| 모드 | 대상 | 설정 방법 | 비용 |
|------|------|-----------|------|
| **Claude Code CLI** | Pro / Pro Max 구독자 | `ANTHROPIC_API_KEY`를 비워두기 | 월정액에 포함 |
| **Anthropic API** | API 사용자 | `ANTHROPIC_API_KEY` 설정 | 토큰당 과금 (~$0.03/일) |

- **Pro Max 구독자**: `ANTHROPIC_API_KEY`를 비워두면 자동으로 `claude` CLI를 사용합니다. Claude Code가 설치되어 있어야 합니다.
- **API 사용자**: https://console.anthropic.com 에서 API key를 발급받아 설정하세요.

### 5. 환경 변수 설정

```bash
cp .env.example .env
```

`.env` 파일을 열고 아래 값을 채워주세요:

```env
SLACK_BOT_TOKEN=xoxb-여기에-봇-토큰-붙여넣기
SLACK_CHANNEL=C여기에-채널-ID
ANTHROPIC_API_KEY=                       # 비워두면 Claude CLI 사용 (Pro Max)
GITHUB_TOKEN=ghp_여기에-깃헙-토큰       # 선택사항 (rate limit 완화)
```

| 변수 | 필수 | 설명 |
|------|------|------|
| `SLACK_BOT_TOKEN` | O | Slack Bot OAuth Token |
| `SLACK_CHANNEL` | O | 채널 ID (`C...`) → 채널 전송, 본인 Member ID (`U...`) → DM 전송 |
| `ANTHROPIC_API_KEY` | △ | Anthropic API Key. 비워두면 Claude CLI 사용 (Pro/Pro Max 구독 필요) |
| `GITHUB_TOKEN` | X | GitHub Personal Access Token (크롤링 rate limit 완화) |

### 6. 첫 실행

```bash
source .venv/bin/activate

# 1) Track Pool 구축 (Awesome repo 크롤링) + 테스트 실행
set -a && source .env && set +a && python3 daily_briefing.py --crawl --dry-run

# 2) 결과 확인 후 실제 실행 (Slack 전송 + Git push)
set -a && source .env && set +a && python3 daily_briefing.py
```

| 플래그 | 설명 |
|--------|------|
| `--crawl` | Awesome repo 강제 크롤링 (보통 7일마다 자동 실행) |
| `--dry-run` | Slack 전송 / Git push 없이 분석 결과만 stdout 출력 |
| `--no-git` | Slack 전송 + 파일 저장만 하고 git commit/push 건너뛰기 |
| (없음) | 정상 실행 |

### 7. Crontab 등록 (자동 실행)

매일 **KST 08:00**에 자동 실행 (서버 타임존이 KST인 경우):

```bash
crontab -e
```

아래 줄 추가 (경로를 본인 환경에 맞게 수정):

```cron
0 8 * * * cd /home/minseokim/daily-ai-llm-papers && bash run.sh
```

<!-- AUTO-GENERATED BELOW -->

## 📊 최근 논문 (트랙별)

### ML Systems

| 날짜 | 제목 | 링크 |
|------|------|------|
| 2026-04-18 | [Pool] 2502.21231 | [arXiv](https://arxiv.org/abs/2502.21231) |
| 2026-04-12 | [Pool] 2502.19811 | [arXiv](https://arxiv.org/abs/2502.19811) |
| 2026-04-11 | [Pool] 2412.19437 | [arXiv](https://arxiv.org/abs/2412.19437) |
| 2026-04-06 | [Pool] 2411.14458 | [arXiv](https://arxiv.org/abs/2411.14458) |
| 2026-03-31 | Hydraulis: Balancing Large Transformer Model Training via Co-designing Parallel Strategies and Data Assignment | [arXiv](https://arxiv.org/abs/2412.07894) |
| 2026-03-30 | [Pool] 2410.21680 | [arXiv](https://arxiv.org/abs/2410.21680) |
| 2026-03-29 | [Pool] 2407.21783 | [arXiv](https://arxiv.org/abs/2407.21783) |
| 2026-03-25 | Enhancing Large-Scale AI Training Efficiency: The C4 Solution for Real-Time Anomaly Detection and Communication Optimization | [arXiv](https://arxiv.org/abs/2406.04594) |

### LLM Post-training

| 날짜 | 제목 | 링크 |
|------|------|------|
| 2026-04-19 | [Pool] 2409.18169 | [arXiv](https://arxiv.org/abs/2409.18169) |
| 2026-04-13 | [Pool] 2501.09686 | [arXiv](https://arxiv.org/abs/2501.09686) |
| 2026-04-07 | [Pool] 2502.15652 | [arXiv](https://arxiv.org/abs/2502.15652) |
| 2026-04-01 | From System 1 to System 2: A Survey of Reasoning Large Language Models | [arXiv](https://arxiv.org/abs/2502.17419) |
| 2026-03-30 | [Pool] 2503.06072 | [arXiv](https://arxiv.org/abs/2503.06072) |
| 2026-03-26 | [Pool] 2502.21321 | [arXiv](https://arxiv.org/abs/2502.21321) |

### RL for LLMs / Reasoning

| 날짜 | 제목 | 링크 |
|------|------|------|
| 2026-04-20 | [Pool] 2508.06471 | [arXiv](https://arxiv.org/abs/2508.06471) |
| 2026-04-14 | [Pool] 2508.15763 | [arXiv](https://arxiv.org/abs/2508.15763) |
| 2026-04-08 | [Pool] 2504.16084 | [arXiv](https://arxiv.org/abs/2504.16084) |
| 2026-04-02 | [Pool] 2508.10874 | [arXiv](https://arxiv.org/abs/2508.10874) |
| 2026-03-27 | A Survey of Reinforcement Learning for Large Reasoning Models | [arXiv](https://arxiv.org/abs/2509.08827) |

### Agents

| 날짜 | 제목 | 링크 |
|------|------|------|
| 2026-04-15 | [Pool] 2602.01797 | [arXiv](https://arxiv.org/abs/2602.01797) |
| 2026-04-09 | [Pool] 2602.01848 | [arXiv](https://arxiv.org/abs/2602.01848) |
| 2026-04-03 | Gender Dynamics and Homophily in a Social Network of LLM Agents | [arXiv](https://arxiv.org/abs/2602.02606) |
| 2026-03-28 | AgenticPay: A Multi-Agent LLM Negotiation System for Buyer-Seller Transactions | [arXiv](https://arxiv.org/abs/2602.06008) |
| 2026-03-24 | DyTopo: Dynamic Topology Routing for Multi-Agent Reasoning via Semantic Matching | [arXiv](https://arxiv.org/abs/2602.06039) |
| 2026-03-24 | RuleSmith: Multi-Agent LLMs for Automated Game Balancing | [arXiv](https://arxiv.org/abs/2602.06232) |
| 2026-03-24 | CommCP: Efficient Multi-Agent Coordination via LLM-Based Communication with Conformal Prediction | [arXiv](https://arxiv.org/abs/2602.06038) |

### Efficient LLM / Inference / Long Context

| 날짜 | 제목 | 링크 |
|------|------|------|
| 2026-04-16 | [Pool] 2502.07864 | [arXiv](https://arxiv.org/abs/2502.07864) |
| 2026-04-10 | [Pool] 2502.14837 | [arXiv](https://arxiv.org/abs/2502.14837) |
| 2026-04-04 | Native Sparse Attention: Hardware-Aligned and Natively Trainable Sparse Attention | [arXiv](https://arxiv.org/abs/2502.11089) |
| 2026-03-29 | [Pool] 2501.12948 | [arXiv](https://arxiv.org/abs/2501.12948) |

### Diffusion Language Models

| 날짜 | 제목 | 링크 |
|------|------|------|
| 2026-04-17 | [Pool] 2509.26328 | [arXiv](https://arxiv.org/abs/2509.26328) |
| 2026-04-11 | [Pool] 2509.24007 | [arXiv](https://arxiv.org/abs/2509.24007) |
| 2026-04-05 | Dream 7B: Diffusion Large Language Models | [arXiv](https://arxiv.org/abs/2508.15487) |

## 📚 브리핑 아카이브

- [2026-04-20](./src/2026/04/2026-04-20.md)
- [2026-04-19](./src/2026/04/2026-04-19.md)
- [2026-04-18](./src/2026/04/2026-04-18.md)
- [2026-04-17](./src/2026/04/2026-04-17.md)
- [2026-04-16](./src/2026/04/2026-04-16.md)
- [2026-04-15](./src/2026/04/2026-04-15.md)
- [2026-04-14](./src/2026/04/2026-04-14.md)
- [2026-04-13](./src/2026/04/2026-04-13.md)
- [2026-04-12](./src/2026/04/2026-04-12.md)
- [2026-04-11](./src/2026/04/2026-04-11.md)
- [2026-04-10](./src/2026/04/2026-04-10.md)
- [2026-04-09](./src/2026/04/2026-04-09.md)
- [2026-04-08](./src/2026/04/2026-04-08.md)
- [2026-04-07](./src/2026/04/2026-04-07.md)
- [2026-04-06](./src/2026/04/2026-04-06.md)
- [2026-04-05](./src/2026/04/2026-04-05.md)
- [2026-04-04](./src/2026/04/2026-04-04.md)
- [2026-04-03](./src/2026/04/2026-04-03.md)
- [2026-04-02](./src/2026/04/2026-04-02.md)
- [2026-04-01](./src/2026/04/2026-04-01.md)
- [2026-03-31](./src/2026/03/2026-03-31.md)
- [2026-03-30](./src/2026/03/2026-03-30.md)
- [2026-03-29](./src/2026/03/2026-03-29.md)
- [2026-03-28](./src/2026/03/2026-03-28.md)
- [2026-03-27](./src/2026/03/2026-03-27.md)
- [2026-03-26](./src/2026/03/2026-03-26.md)
- [2026-03-25](./src/2026/03/2026-03-25.md)
- [2026-03-24](./src/2026/03/2026-03-24.md)
