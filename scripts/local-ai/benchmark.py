#!/usr/bin/env python3
"""Compare local chat models on checked agent tasks, one model at a time."""

import argparse
import json
import os
from pathlib import Path
import signal
import subprocess
import threading
import time
import urllib.request
import xml.etree.ElementTree as ET
import zipfile


MODELS = ["qwen3.5:9b-q4_K_M", "gemma4:12b-it-q4_K_M"]
EXPENSES = """invoice_id,category,status,amount,updated_at
A,Hardware,paid,120.50,2026-10-01
B,Software,paid,20.00,2026-10-01
A,Hardware,paid,130.50,2026-10-02
C,Travel,cancelled,75.00,2026-10-01
D,Software,paid,-5.00,2026-10-01
E,Travel,pending,40.00,2026-10-01
F,Hardware,paid,9.50,2026-10-01
"""
INVOICE_CODE = """def invoice_total(items):
    return round(sum(item["price"] for item in items), 2)
"""
INVOICE_TESTS = '''import unittest
from invoice import invoice_total

class InvoiceTests(unittest.TestCase):
    def test_empty(self):
        self.assertEqual(invoice_total([]), 0.0)
    def test_quantities(self):
        self.assertEqual(invoice_total([{"price":"12.50","quantity":2,"status":"paid"},{"price":"3.50","quantity":1,"status":"paid"}]), 28.5)
    def test_refunds(self):
        self.assertEqual(invoice_total([{"price":"10","quantity":1,"status":"paid"},{"price":"1.50","quantity":-1,"status":"paid"}]), 8.5)
    def test_only_paid(self):
        self.assertEqual(invoice_total([{"price":"20","quantity":1,"status":"paid"},{"price":"90","quantity":1,"status":"cancelled"},{"price":"7","quantity":1}]), 20.0)
    def test_decimal(self):
        self.assertEqual(invoice_total([{"price":"0.1","quantity":1,"status":"paid"},{"price":"0.2","quantity":1,"status":"paid"}]), 0.3)
    def test_half_up(self):
        self.assertEqual(invoice_total([{"price":"1.005","quantity":1,"status":"paid"}]), 1.01)

if __name__ == "__main__":
    unittest.main()
'''
TASKS = {
    "expense_analysis": (
        "Read expenses.csv. Deduplicate invoice_id by keeping its latest updated_at row. "
        "Then include only paid invoices, including negative amounts as refunds. "
        "Write totals.json with numeric paid_total, paid_count, and a by_category object. "
        "Also write a short expenses-summary.md explaining the result. Use tools; do not guess."
    ),
    "document_creation": (
        "Read brief.txt and create a real Word document named project-brief.docx. "
        "Include a project heading and concise sections for client, launch date, budget, "
        "and the named action owner and deadline. Preserve the facts and do not invent commitments. "
        "Use the available document tools or scripts."
    ),
    "code_repair": (
        "Fix invoice.py so invoice_total passes test_invoice.py. Only paid items contribute; "
        "multiply decimal-string prices by integer quantities, including negative refunds. "
        "Return a float rounded to cents using decimal ROUND_HALF_UP. Missing status is not paid. "
        "Run the tests. Do not modify test_invoice.py."
    ),
    "web_research": (
        "Use the Fetch tool to retrieve https://goose-docs.ai/ (up to 6000 characters). "
        "Write research.md identifying Goose's license and its desktop, CLI, and API interfaces. "
        "Include the source URL and a concise factual description based only on the retrieved page."
    ),
}


def api(path, payload=None, timeout=5):
    request = urllib.request.Request(
        "http://127.0.0.1:11434/api/" + path,
        data=None if payload is None else json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.load(response)


def seed(task, directory):
    directory.mkdir(parents=True)
    if task == "expense_analysis":
        (directory / "expenses.csv").write_text(EXPENSES)
    elif task == "document_creation":
        (directory / "brief.txt").write_text(
            "Project: Harbor Pilot\nClient: Dana Park\nLaunch: 18 November 2026\n"
            "Budget: USD 1,500\nMira owns the data import, due 10 November 2026.\n"
        )
    elif task == "code_repair":
        (directory / "invoice.py").write_text(INVOICE_CODE)
        (directory / "test_invoice.py").write_text(INVOICE_TESTS)


def grade(task, directory):
    try:
        if task == "expense_analysis":
            value = json.loads((directory / "totals.json").read_text())
            expected = {"paid_total": 155.0, "paid_count": 4,
                        "by_category": {"Hardware": 140.0, "Software": 15.0}}
            return value == expected and (directory / "expenses-summary.md").exists(), value
        if task == "document_creation":
            with zipfile.ZipFile(directory / "project-brief.docx") as document:
                root = ET.fromstring(document.read("word/document.xml"))
            text = " ".join(root.itertext()).lower()
            checks = {term: term in text for term in
                      ["harbor", "pilot", "dana park", "mira"]}
            checks["launch_date"] = any(term in text for term in
                ["18 november 2026", "november 18, 2026", "2026-11-18", "18 nov 2026"])
            checks["action_deadline"] = any(term in text for term in
                ["10 november 2026", "november 10, 2026", "2026-11-10", "10 nov 2026"])
            checks["budget"] = "1500" in text.replace(",", "")
            return all(checks.values()), checks
        if task == "code_repair":
            intact = (directory / "test_invoice.py").read_text() == INVOICE_TESTS
            result = subprocess.run(
                ["python3", "-m", "unittest", "-v"], cwd=directory,
                capture_output=True, text=True, timeout=15,
            )
            return intact and result.returncode == 0, {
                "tests_unchanged": intact, "test_output": result.stderr[-2200:]}
        text = (directory / "research.md").read_text().lower()
        checks = {term: term in text for term in ["apache", "2.0", "desktop", "cli", "api", "goose-docs.ai"]}
        return all(checks.values()), checks
    except Exception as error:
        return False, {"error": str(error)}


def run_case(model, task, root, executable):
    directory = root / model.split(":")[0] / task
    seed(task, directory)
    for loaded in api("ps").get("models", []):
        api("generate", {"model": loaded["name"], "keep_alive": 0}, timeout=30)
    samples = []
    stop = threading.Event()

    def sample():
        while not stop.is_set():
            try:
                samples.append(api("ps").get("models", []))
            except Exception:
                pass
            stop.wait(0.5)

    monitor = threading.Thread(target=sample, daemon=True)
    monitor.start()
    environment = os.environ.copy()
    environment.update({
        "GOOSE_PATH_ROOT": str(root / "runtime"), "GOOSE_PROVIDER": "ollama",
        "GOOSE_MODEL": model, "OLLAMA_HOST": "http://127.0.0.1:11434",
        "GOOSE_INPUT_LIMIT": "16384", "GOOSE_CONTEXT_LIMIT": "16384",
        "GOOSE_MAX_TOKENS": "2048", "GOOSE_THINKING_EFFORT": "off",
        "GOOSE_TEMPERATURE": "0.2", "GOOSE_DISABLE_KEYRING": "1",
        "GOOSE_MODE": "auto", "GOOSE_TELEMETRY_ENABLED": "false",
    })
    builtins = "developer,computercontroller" if task == "document_creation" else "developer"
    command = [executable, "run", "--quiet", "--no-session", "--no-profile",
               "--with-builtin", builtins]
    if task == "web_research":
        command += ["--with-extension", "fetch:/opt/homebrew/bin/uvx --with 'mcp<2' mcp-server-fetch==2025.4.7"]
    command += ["--max-turns", "8", "--max-tool-repetitions", "2", "--output-format", "json",
               "--text", TASKS[task] + " Work only in the current directory. Do not delegate or use desktop/browser control."]
    start = time.monotonic()
    timed_out = False
    with (directory / "agent-output.log").open("w") as output, (directory / "agent-error.log").open("w") as errors:
        process = subprocess.Popen(command, cwd=directory, env=environment,
                                   stdout=output, stderr=errors, start_new_session=True)
        try:
            process.wait(timeout=180)
        except subprocess.TimeoutExpired:
            timed_out = True
            os.killpg(process.pid, signal.SIGTERM)
            process.wait(timeout=10)
    elapsed = round(time.monotonic() - start, 1)
    stop.set()
    monitor.join(timeout=6)
    passed, details = grade(task, directory)
    trace = {}
    try:
        raw = (directory / "agent-output.log").read_text()
        trace = json.loads(raw[raw.index("{\n"):])
    except (ValueError, KeyError):
        pass
    calls = [content.get("toolCall", {}).get("value", {}).get("name")
             for message in trace.get("messages", [])
             for content in message.get("content", [])
             if content.get("type") == "toolRequest"]
    result = {
        "model": model, "task": task, "passed": passed and not timed_out,
        "elapsed_seconds": elapsed, "timed_out": timed_out, "exit_code": process.returncode,
        "peak_loaded_models": max((len(sample) for sample in samples), default=0),
        "peak_api_reported_size_gib": round(max((sum(m.get("size", 0) for m in sample) for sample in samples), default=0) / 1024**3, 2),
        "peak_api_reported_gpu_gib": round(max((sum(m.get("size_vram", 0) for m in sample) for sample in samples), default=0) / 1024**3, 2),
        "tokens": trace.get("metadata", {}).get("total_tokens"),
        "tool_calls": calls, "grade": details,
    }
    (directory / "result.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({k: result[k] for k in ["model", "task", "passed", "elapsed_seconds", "peak_api_reported_size_gib", "peak_loaded_models"]}), flush=True)
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--goose", default="/Applications/Goose.app/Contents/Resources/bin/goose")
    arguments = parser.parse_args()
    arguments.output.mkdir(parents=True)
    results = []
    for number, task in enumerate(TASKS):
        order = MODELS if number % 2 == 0 else list(reversed(MODELS))
        for model in order:
            print(f"Running {task}: {model}", flush=True)
            results.append(run_case(model, task, arguments.output, arguments.goose))
            (arguments.output / "results.json").write_text(json.dumps(results, indent=2) + "\n")
    for loaded in api("ps").get("models", []):
        api("generate", {"model": loaded["name"], "keep_alive": 0}, timeout=30)
    summary = {model: {
        "passed": sum(case["passed"] for case in results if case["model"] == model),
        "tasks": len(TASKS),
        "elapsed_seconds": round(sum(case["elapsed_seconds"] for case in results if case["model"] == model), 1),
        "peak_api_reported_size_gib": max(case["peak_api_reported_size_gib"] for case in results if case["model"] == model),
    } for model in MODELS}
    (arguments.output / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps(summary, indent=2), flush=True)


if __name__ == "__main__":
    main()
