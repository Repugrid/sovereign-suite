#!/usr/bin/env python3
"""
Project Sovereign — Worker Spawner
Manages the lifecycle of worker containers: spawn, monitor, cleanup.
Called by the CEO orchestrator when it needs to delegate work.
"""

import json
import subprocess
import uuid
from datetime import datetime, timezone
from pathlib import Path

SHARED_DIR = Path("/root/sovereign/shared")
TASKS_DIR = SHARED_DIR / "tasks"
RESULTS_DIR = SHARED_DIR / "results"
LOG_DIR = Path("/root/sovereign/logs")

VALID_ROLES = {"coder", "marketer", "researcher"}

# Worker Docker image (built once, reused for all workers)
WORKER_IMAGE = "sovereign-worker"


def build_worker_image():
    """Build the worker Docker image if it doesn't exist."""
    result = subprocess.run(
        ["docker", "images", "-q", WORKER_IMAGE],
        capture_output=True, text=True,
    )
    if not result.stdout.strip():
        print(f"[Spawner] Building worker image: {WORKER_IMAGE}")
        subprocess.run(
            ["docker", "build", "-f", "workers/Dockerfile.worker", "-t", WORKER_IMAGE, "."],
            cwd="/root/sovereign",
            check=True,
        )
    return True


def create_task(task_id: str, role: str, instruction: str, context: dict | None = None) -> Path:
    """
    Write a task file to the shared/tasks/ directory.
    Returns the path to the created task file.
    """
    TASKS_DIR.mkdir(parents=True, exist_ok=True)

    task = {
        "task_id": task_id,
        "role": role,
        "instruction": instruction,
        "context": context or {},
        "created_at": datetime.now(timezone.utc).isoformat(),
        "status": "pending",
    }

    task_path = TASKS_DIR / f"{task_id}.json"
    task_path.write_text(json.dumps(task, indent=2))
    return task_path


def spawn_worker(role: str, task_id: str, instruction: str, context: dict | None = None) -> dict:
    """
    Spawn a single worker container for a specific task.

    Args:
        role: Worker type (coder, marketer, researcher)
        task_id: Unique task identifier (or auto-generated)
        instruction: What the worker should do
        context: Additional context dict passed to the worker

    Returns:
        dict with worker_id, container_id, task_id, status
    """
    if role not in VALID_ROLES:
        return {"error": f"Invalid role: {role}. Must be one of {VALID_ROLES}"}

    # Generate IDs
    if not task_id:
        task_id = f"task_{role}_{uuid.uuid4().hex[:8]}"
    worker_id = f"worker_{role}_{uuid.uuid4().hex[:6]}"
    container_name = f"sovereign-{worker_id}"

    # Build image if needed
    build_worker_image()

    # Create task file
    task_file = f"{task_id}.json"
    create_task(task_id, role, instruction, context)

    # Spawn container
    cmd = [
        "docker", "run", "-d",
        "--name", container_name,
        "--network", "sovereign_sovereign-net",
        "--env-file", "/root/sovereign/.env",
        "-e", f"WORKER_ID={worker_id}",
        "-e", f"WORKER_ROLE={role}",
        "-e", f"TASK_FILE={task_file}",
        "-v", f"{SHARED_DIR}:/root/sovereign/shared",
        "-v", f"{LOG_DIR}:/root/sovereign/logs",
        "--memory", "1g",
        "--rm",  # Auto-remove when done
        WORKER_IMAGE,
    ]

    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.returncode != 0:
        return {
            "error": f"Failed to spawn worker: {result.stderr.strip()}",
            "worker_id": worker_id,
            "task_id": task_id,
        }

    container_id = result.stdout.strip()[:12]

    log_event("worker_spawned", {
        "worker_id": worker_id,
        "role": role,
        "task_id": task_id,
        "container": container_id,
    })

    return {
        "worker_id": worker_id,
        "container_name": container_name,
        "container_id": container_id,
        "task_id": task_id,
        "role": role,
        "status": "running",
    }


def spawn_batch(role: str, tasks: list[dict]) -> list[dict]:
    """
    Spawn multiple workers of the same role.

    Args:
        role: Worker type
        tasks: List of dicts with 'task_id', 'instruction', optional 'context'

    Returns:
        List of spawn results
    """
    results = []
    for task in tasks:
        result = spawn_worker(
            role=role,
            task_id=task.get("task_id", ""),
            instruction=task["instruction"],
            context=task.get("context"),
        )
        results.append(result)
    return results


def check_worker(container_name: str) -> dict:
    """Check if a worker container is still running."""
    result = subprocess.run(
        ["docker", "inspect", "--format", "{{.State.Status}}", container_name],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        return {"container": container_name, "status": "removed"}

    return {"container": container_name, "status": result.stdout.strip()}


def check_task_result(task_id: str) -> dict | None:
    """Check if a task result file exists and return its contents."""
    result_path = RESULTS_DIR / f"{task_id}.json"
    if result_path.exists():
        return json.loads(result_path.read_text())
    return None


def list_active_workers() -> list[dict]:
    """List all running sovereign worker containers."""
    result = subprocess.run(
        ["docker", "ps", "--filter", "name=sovereign-worker", "--format",
         '{"container":"{{.Names}}","status":"{{.Status}}","created":"{{.CreatedAt}}"}'],
        capture_output=True, text=True,
    )
    workers = []
    for line in result.stdout.strip().split("\n"):
        if line:
            try:
                workers.append(json.loads(line))
            except json.JSONDecodeError:
                pass
    return workers


def kill_worker(container_name: str) -> str:
    """Force stop a worker container."""
    result = subprocess.run(
        ["docker", "rm", "-f", container_name],
        capture_output=True, text=True,
    )
    return "killed" if result.returncode == 0 else f"error: {result.stderr.strip()}"


def log_event(event_type: str, data: dict):
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    log_file = LOG_DIR / f"{datetime.now(timezone.utc).strftime('%Y-%m-%d')}.jsonl"
    entry = {"ts": datetime.now(timezone.utc).isoformat(), "type": event_type, **data}
    with open(log_file, "a") as f:
        f.write(json.dumps(entry) + "\n")
