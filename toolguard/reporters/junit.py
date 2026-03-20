"""
toolguard.reporters.junit
~~~~~~~~~~~~~~~~~~~~~~~~~
Generates JUnit XML format reports for legacy enterprise CI/CD systems 
(Jenkins, GitLab CI, CircleCI).
"""
import xml.etree.ElementTree as ET
from pathlib import Path
from toolguard.core.report import ChainTestReport

def generate_junit_xml(report: ChainTestReport, output_path: str) -> str:
    """Generate a JUnit XML report for the test chain."""
    total_tests = len(report.runs)
    failures = len([r for r in report.runs if not r.success])
    total_latency_ms = sum(r.total_latency_ms for r in report.runs)
    
    testsuites = ET.Element("testsuites", 
                            name="ToolGuard Reliability Suite", 
                            tests=str(total_tests), 
                            failures=str(failures))
    
    suite = ET.SubElement(testsuites, "testsuite", 
                          name=report.chain_name, 
                          tests=str(total_tests), 
                          failures=str(failures), 
                          time=str(total_latency_ms / 1000.0))
    
    for idx, run in enumerate(report.runs):
        testcase = ET.SubElement(suite, "testcase", 
                                 name=f"{run.test_case_type} - {run.correlation_id}", 
                                 classname=f"toolguard.test_cases.{run.test_case_type}", 
                                 time=str(run.total_latency_ms / 1000.0))
        if not run.success:
            failure_step = next((s for s in run.steps if not s.success), None)
            
            message = f"{failure_step.tool_name} failed" if failure_step else "Chain initialization failed"
            failure = ET.SubElement(testcase, "failure", 
                                    message=message, 
                                    type="ToolGuardHallucinationFailure")
                                    
            if failure_step and failure_step.error:
                failure.text = f"Tool: {failure_step.tool_name}\nError: {failure_step.error}"
            else:
                failure.text = "Unknown execution failure."
                
    tree = ET.ElementTree(testsuites)
    
    xml_str = ET.tostring(testsuites, encoding="utf-8", xml_declaration=True).decode("utf-8")
    
    out_file = Path(output_path)
    out_file.parent.mkdir(parents=True, exist_ok=True)
    out_file.write_text(xml_str, encoding="utf-8")
    
    return str(out_file.resolve())
