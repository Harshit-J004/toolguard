"""
toolguard.cli.dashboard
~~~~~~~~~~~~~~~~~~~~~~~

Real-time Textual (TUI) Dashboard for ToolGuard.
Provides a live, dark-mode terminal control center for observing agent tests.
"""

from __future__ import annotations

import sys
import os
import time
from typing import Callable, Any

from textual.app import App, ComposeResult
from textual.containers import Vertical, Horizontal, Container
from textual.widgets import Header, Footer, RichLog, Label, Digits, Rule
from textual import work

from toolguard.core.report import ChainTestReport, ChainRun
from toolguard.core.chain import test_chain

# Minimalist, high-contrast Dark Mode (mariya.fyi inspired)
CSS = """
Screen {
    background: #0D0D12;
    color: #A0A5B5;
}

Header {
    dock: top;
    height: 3;
    content-align: center middle;
    background: #0D0D12;
    color: #E67E22;
    text-style: bold;
    border-bottom: solid #1A1A24;
}

Footer {
    background: #0D0D12;
    color: #A0A5B5;
    border-top: solid #1A1A24;
}

#sidebar {
    width: 35;
    border-right: solid #1A1A24;
    padding: 1 2;
}

#main_metrics {
    height: auto;
    margin-bottom: 1;
    border-bottom: solid #1A1A24;
    padding-bottom: 1;
}

.stat-box {
    margin-top: 1;
}

.stat-label {
    color: #6272A4;
}

.stat-val-green {
    color: #50FA7B;
    text-style: bold;
}

.stat-val-red {
    color: #FF5555;
    text-style: bold;
}

.stat-val-orange {
    color: #FFB86C;
    text-style: bold;
}

#logs {
    width: 1fr;
    height: 1fr;
    border: none;
    background: #0D0D12;
}

.hacker-text {
    color: #50FA7B;
}

.error-text {
    color: #FF5555;
}

.alert-text {
    color: #FFB86C;
}
"""

class ToolGuardDashboard(App):
    """The main ToolGuard Terminal Control Center."""

    CSS = CSS
    TITLE = "~ / toolguard / session"
    BINDINGS = [
        ("q", "quit", "Quit"),
        ("ctrl+c", "quit", "Force Quit")
    ]

    def __init__(self, target_script: str, chain: list[Callable]):
        super().__init__()
        self.target_script = target_script
        self.chain = chain
        self.total_runs = 0
        self.passed_runs = 0
        self.failed_runs = 0

    def compose(self) -> ComposeResult:
        """Create child widgets for the app."""
        yield Header(show_clock=True)
        
        with Horizontal():
            # LEFT SIDEBAR: Metrics & Status
            with Vertical(id="sidebar"):
                yield Label(f"$ target: [white]{os.path.basename(self.target_script)}[/white]\n")
                
                with Vertical(id="main_metrics"):
                    yield Label("[bold white]SESSION STATUS[/bold white]")
                    yield Label("● RUNNING", id="status_indicator", classes="stat-val-orange")
                
                with Vertical(classes="stat-box"):
                    yield Label("ITERATIONS", classes="stat-label")
                    yield Digits("0", id="stat_iters")
                
                with Vertical(classes="stat-box"):
                    yield Label("PASSED", classes="stat-label")
                    yield Digits("0", id="stat_pass", classes="stat-val-green")
                    
                with Vertical(classes="stat-box"):
                    yield Label("FAILED", classes="stat-label")
                    yield Digits("0", id="stat_fail", classes="stat-val-red")
                    
                yield Rule()
                yield Label("\n[bold white]TOOLS DETECTED[/bold white]")
                for t in self.chain:
                    yield Label(f" - {getattr(t, '__name__', str(t))}", classes="stat-label")

            # MAIN WINDOW: Live RichLogs
            yield RichLog(id="logs", highlight=True)

        yield Footer()

    def on_mount(self) -> None:
        """Start the background fuzzing thread immediately upon mount."""
        log_widget = self.query_one("#logs", RichLog)
        log_widget.write(f"[ #E67E22 ] ToolGuard Core Engine v1.0.0 init")
        log_widget.write(f"[ #E67E22 ] Fuzzing {len(self.chain)} tools from {self.target_script}...")
        log_widget.write("-" * 60)
        
        self.run_fuzzing_engine()

    @work(thread=True)
    def run_fuzzing_engine(self) -> None:
        """Run `test_chain` inside a background thread so the UI stays responsive."""
        
        def handle_progress(current: int, total: int, run: ChainRun) -> None:
            """Callback injected into test_chain. Fired from the background thread."""
            # Use call_from_thread to safely update the UI widgets
            self.call_from_thread(self.update_progress, current, total, run)

        try:
            # We must use arbitrary high iterations to show off the visual streaming properly.
            # In a real run, `run_cmd` handles the default settings, but for the dashboard
            # we'll do 15 interactions so it streams beautifully.
            report = test_chain(
                self.chain,
                iterations=15, 
                on_progress=handle_progress,
                assert_reliability=0.0 # Don't raise assertion inside the UI thread
            )
            self.call_from_thread(self.finalize_run, report)
        except Exception as e:
            self.call_from_thread(self.panic_run, str(e))

    def update_progress(self, current: int, total: int, run: ChainRun) -> None:
        """Update metrics and logs safely on the main thread."""
        self.total_runs += 1
        if run.success:
            self.passed_runs += 1
            marker = "[ #50FA7B ] [ OK ]"
            color = "#50FA7B"
        else:
            self.failed_runs += 1
            marker = "[ #FF5555 ] [FAIL]"
            color = "#FF5555"

        # Update Digits
        self.query_one("#stat_iters", Digits).update(str(self.total_runs))
        self.query_one("#stat_pass", Digits).update(str(self.passed_runs))
        self.query_one("#stat_fail", Digits).update(str(self.failed_runs))

        # Write to log
        log_w = self.query_one("#logs", RichLog)
        log_w.write(f"{marker} Iteration {current}/{total} | Type: {run.test_case_type:<15}")
        
        # If failure, print exactly what failed
        if not run.success:
            for step in run.steps:
                if not step.success:
                    log_w.write(f"           CRASH in `{step.tool_name}`: {step.error_type}")
                    log_w.write(f"           Payload: {step.input_data}")

    def finalize_run(self, report: ChainTestReport) -> None:
        """Called when test_chain perfectly finishes."""
        status = self.query_one("#status_indicator", Label)
        status.update("● COMPLETED")
        status.remove_class("stat-val-orange")
        
        log_w = self.query_one("#logs", RichLog)
        log_w.write("-" * 60)
        
        score = report.reliability
        if score > 0.90:
            status.add_class("stat-val-green")
            log_w.write(f"[ #50FA7B ] SESSION COMPLETE. Score: {score:.1%} (PASSED)")
        else:
            status.add_class("stat-val-red")
            log_w.write(f"[ #FF5555 ] SESSION COMPLETE. Score: {score:.1%} (BLOCKED)")
            
        log_w.write("\n[ #6272A4 ] Press 'q' to exit the dashboard and return to terminal.")

    def panic_run(self, error_msg: str) -> None:
        """Called if the background thread throws a fatal python error."""
        status = self.query_one("#status_indicator", Label)
        status.update("● FATAL ERROR")
        status.remove_class("stat-val-orange")
        status.add_class("stat-val-red")
        
        log_w = self.query_one("#logs", RichLog)
        log_w.write(f"\n[ #FF5555 ] FATAL ENGINE CRASH: {error_msg}")
