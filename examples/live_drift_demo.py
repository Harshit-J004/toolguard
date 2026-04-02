"""
Live Drift Detection Demo
~~~~~~~~~~~~~~~~~~~~~~~~~

This script proves that `toolguard check-drift` works perfectly against
real, live LLM APIs. We simulate a scenario where an LLM provider "silently"
changes their output schema.

1. Baseline: We ask Gemini for a standard weather JSON.
2. Freeze: We fingerprint the baseline.
3. Drift: We ask Gemini for weather again, but simulate an update where
   it returns a radically different JSON structure.
4. Detect: ToolGuard catches the drift and reports it.
"""

import json
import os
import sys
import time
import urllib.request
import urllib.error

# Ensure toolguard is in the path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from toolguard.core.drift import create_fingerprint, detect_drift
from toolguard.cli.commands.drift_cmd import _print_drift_report
from rich.console import Console

console = Console()

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

def call_gemini(prompt: str) -> dict:
    if not GEMINI_API_KEY:
        console.print("[bold red]❌ GEMINI_API_KEY is missing![/]")
        console.print("[yellow]Please run: $env:GEMINI_API_KEY='your_key' before executing.[/]")
        sys.exit(1)

    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={GEMINI_API_KEY}"
    
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "responseMimeType": "application/json"
        }
    }
    
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST"
    )
    
    try:
        response = urllib.request.urlopen(req)
        data = json.loads(response.read().decode("utf-8"))
        text_response = data["candidates"][0]["content"]["parts"][0]["text"]
        return json.loads(text_response)
    except Exception as e:
        console.print(f"[bold red]Live API Call Failed: {e}[/]")
        sys.exit(1)


def main():
    console.print("\n[bold cyan]🌍 Starting Live LLM Drift Detection Demo...[/]\n")
    
    # ──────────────────────────────────────────────────────────
    #  PHASE 1: THE BASELINE (Working Production System)
    # ──────────────────────────────────────────────────────────
    console.print("[bold yellow]1. Fetching Baseline Output...[/]")
    baseline_prompt = """
    Return the current weather in New York.
    You MUST return JSON with EXACTLY these keys:
    - city (string)
    - temperature (number)
    - unit (string, default "F")
    - conditions (string)
    """
    
    baseline_output = call_gemini(baseline_prompt)
    console.print("   [dim]Received Baseline:[/]")
    console.print(json.dumps(baseline_output, indent=2))
    
    # Freeze it!
    console.print("\n[bold yellow]2. Freezing Schema Fingerprint...[/]")
    fingerprint = create_fingerprint(
        tool_name="live_weather_tool",
        prompt=baseline_prompt,
        model="gemini-2.5-flash",
        output=baseline_output
    )
    console.print(f"   ✅ Fingerprint Baseline Checksum: [cyan]{fingerprint.checksum}[/]\n")


    # ──────────────────────────────────────────────────────────
    #  PHASE 2: THE DRIFT (Simulating a provider update)
    # ──────────────────────────────────────────────────────────
    console.print("[bold yellow]3. Simulating LLM Provider Update (Drifted Output)...[/]")
    # We alter the prompt to force the LLM to hallucinate a different structure, 
    # simulating what happens when an LLM is updated and ignores its strict system prompt.
    drift_prompt = """
    Return the current weather in New York.
    Return JSON. Use these keys:
    - location_name (string, instead of city)
    - temperature (string, formatted like "72F")
    - conditions (string)
    - humidity (number)
    """
    
    drifted_output = call_gemini(drift_prompt)
    console.print("   [dim]Received Drifted Output:[/]")
    console.print(json.dumps(drifted_output, indent=2))
    
    
    # ──────────────────────────────────────────────────────────
    #  PHASE 3: DETECTION
    # ──────────────────────────────────────────────────────────
    console.print("\n[bold yellow]4. Running Drift Check...[/]")
    
    report = detect_drift(fingerprint, drifted_output)
    
    # Print the exact same rich report the CLI prints
    _print_drift_report(report)
    
    if report.has_drift:
        console.print("[bold green]✅ SUCCESS: ToolGuard caught the live LLM schema drift![/]\n")
    else:
        console.print("[bold red]❌ FAILED: Drift was not detected![/]\n")


if __name__ == "__main__":
    main()
