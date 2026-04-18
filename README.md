# LLM Safety Co-Pilot

A safety layer for LLM-controlled robot navigation systems. Natural language instructions are passed through a large language model (Llama 3.1 8B) to generate structured robot commands, which are then validated against a configurable safety policy before execution.

Built as a dissertation project at Newcastle University.

---

## How It Works

1. A user sends a natural language instruction (e.g. *"navigate to room 3 at medium speed"*)
2. The instruction is passed to **Llama 3.1 8B** (via Ollama) which returns a structured JSON command
3. The **safety filter** validates the command against a policy (speed limits, no-go zones, banned keywords, action whitelist)
4. The command is either **ALLOWED** or **BLOCKED**, with violations listed

---

## Project Structure

```
llm-safety-copilot/
├── gateway/
│   └── gateway.py          # FastAPI REST API with JWT authentication
├── safety_filter/
│   └── filter.py           # Core safety validation engine
├── baseline_agent/
│   └── baseline_agent.py   # Standalone test agent (no API)
├── sdk/
│   └── policy-example.yaml # Example configurable safety policy
├── tests/
│   └── scenarios.json      # Test scenarios
├── baseline_test.py        # Baseline evaluation script
└── requirements.txt
```

---

## Prerequisites

- Python 3.10+
- [Ollama](https://ollama.com) installed and running locally
- Llama 3.1 8B pulled: `ollama pull llama3.1:8b`

---

## Installation

```bash
git clone https://github.com/dhruvapawar-30/llm-safety-copilot.git
cd llm-safety-copilot
pip install -r requirements.txt
```

---

## Running the Gateway (API)

```bash
cd gateway
uvicorn gateway:app --reload
```

The API will be available at `http://localhost:8000`. Interactive docs at `http://localhost:8000/docs`.

### Authentication

Get a token:
```bash
curl -X POST http://localhost:8000/token \
  -d "username=admin&password=secret"
```

Send a command:
```bash
curl -X POST http://localhost:8000/command \
  -H "Authorization: Bearer <your_token>" \
  -H "Content-Type: application/json" \
  -d '{"instruction": "Navigate to the red box in room 3"}'
```

### Example Response

```json
{
  "user": "admin",
  "instruction": "Navigate to the red box in room 3",
  "status": "ALLOWED",
  "command": {
    "action": "navigate",
    "target": "red box in room 3",
    "speed": "medium",
    "reasoning": "Moving to requested destination"
  },
  "violations": [],
  "timestamp": "2026-03-09T19:57:47",
  "latency": {
    "llm_ms": 1423.5,
    "filter_ms": 0.21,
    "total_ms": 1423.71
  }
}
```

---

## Running the Baseline Agent

```bash
cd baseline_agent
python baseline_agent.py
```

This runs a suite of safe, explicitly unsafe, and implicitly unsafe prompts directly — no API or authentication required.

---

## Configuring the Safety Policy

Copy the example policy and customise it:

```bash
cp sdk/policy-example.yaml sdk/policy.yaml
```

Edit `sdk/policy.yaml`:

```yaml
max_speed: medium

no_go_zones:
  - restricted zone
  - maintenance corridor
  - hazard zone

banned_keywords:
  - bypass
  - override
  - ignore
  - collision

allowed_actions:
  - navigate
  - stop
  - rotate
  - wait
```

If no `policy.yaml` is found, the filter falls back to the built-in default policy.

---

## Safety Filter Rules

| Rule | Description |
|---|---|
| Speed limit | Blocks commands where speed exceeds `max_speed` in the policy |
| No-go zones | Blocks commands targeting restricted areas |
| Banned keywords | Blocks commands containing unsafe keywords |
| Action whitelist | Only permits actions listed in `allowed_actions` |

---

## API Endpoints

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/token` | Get a JWT access token |
| `POST` | `/command` | Submit a navigation instruction |
| `GET` | `/health` | Check service status |
