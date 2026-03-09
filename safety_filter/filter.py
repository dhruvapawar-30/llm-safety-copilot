import json
import yaml
import logging
from datetime import datetime


logging.basicConfig(filename='safety_log.txt', level=logging.INFO,
                    format='%(asctime)s - %(message)s')


# Default policy — will load from YAML if available
DEFAULT_POLICY = {
    "max_speed": "medium",
    "no_go_zones": [
        "restricted zone",
        "maintenance corridor",
        "forbidden area",
        "hazard zone"
    ],
    "banned_keywords": [
        "bypass", "override", "ignore", "skip", "disable",
        "collision", "collide", "unsafe", "unrestricted"
    ],
    "allowed_actions": ["navigate", "stop", "rotate", "wait"]
}


SPEED_RANK = {"slow": 1, "medium": 2, "fast": 3}


def load_policy(path="sdk/policy.yaml"):
    try:
        with open(path, "r") as f:
            return yaml.safe_load(f)
    except FileNotFoundError:
        return DEFAULT_POLICY


def parse_llm_output(llm_response: str) -> dict:
    """Extract JSON from LLM response, handling markdown code blocks."""
    try:
        clean = llm_response.strip().strip("```json").strip("```").strip()
        return json.loads(clean)
    except json.JSONDecodeError:
        return {"raw": llm_response, "action": "unknown",
                "target": "", "speed": "fast", "reasoning": llm_response}


def check_safety(llm_response: str, policy: dict = None) -> dict:
    if policy is None:
        policy = load_policy()

    command = parse_llm_output(llm_response)
    violations = []

    # Rule 1: Speed check — skip for stop/wait actions (speed is irrelevant)
    action = command.get("action", "").lower()
    if action not in ("stop", "wait"):
        speed = command.get("speed", "fast").lower()
        max_speed = policy.get("max_speed", "medium")
        if SPEED_RANK.get(speed, 3) > SPEED_RANK.get(max_speed, 2):
            violations.append(f"Speed violation: '{speed}' exceeds max allowed '{max_speed}'")

    # Rule 2: No-go zone check
    target = str(command.get("target", "")).lower()
    reasoning = str(command.get("reasoning", "")).lower()
    for zone in policy.get("no_go_zones", []):
        if zone.lower() in target or zone.lower() in reasoning:
            violations.append(f"No-go zone violation: '{zone}' detected in command")

    # Rule 3: Banned keyword check
    full_text = f"{target} {reasoning}".lower()
    for keyword in policy.get("banned_keywords", []):
        if keyword.lower() in full_text:
            violations.append(f"Banned keyword detected: '{keyword}'")

    # Rule 4: Action whitelist check
    if action not in policy.get("allowed_actions", []):
        violations.append(f"Unknown action: '{action}' not in allowed actions")

    result = {
        "status": "BLOCKED" if violations else "ALLOWED",
        "command": command,
        "violations": violations,
        "timestamp": datetime.now().isoformat()
    }

    # Log everything
    logging.info(json.dumps(result))
    return result
