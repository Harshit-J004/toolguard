import sys
import json
import time

from toolguard import create_tool, test_chain

class MockDDGS:
    def text(self, keywords, max_results, backend):
        if not isinstance(max_results, int):
            raise TypeError(f"max_results must be an int, got {type(max_results)}")
        if max_results < 1:
            raise ValueError(f"max_results must be > 0, got {max_results}")
        return [{"title": "AutoGPT Result", "href": "http://example.com", "body": "Mock response"}]
        
DDGS = MockDDGS

# =========================================================================
# EXACT EXTRACT FROM AutoGPT's classic/forge/forge/components/web/search.py
# =========================================================================
class MockConfig:
    duckduckgo_max_attempts = 3
    duckduckgo_backend = "auto"

class WebSearchComponentExtract:
    def __init__(self):
        self.config = MockConfig()
        
    def safe_google_results(self, results: str | list) -> str:
        if isinstance(results, list):
            safe_message = json.dumps(
                [result.encode("utf-8", "ignore").decode("utf-8") for result in results]
            )
        else:
            safe_message = results.encode("utf-8", "ignore").decode("utf-8")
        return safe_message

    # AUTOGPT'S EXACT LOGIC:
    def web_search(self, query: str, num_results: int = 8) -> str:
        """Return the results of a Google search

        Args:
            query (str): The search query.
            num_results (int): The number of results to return.

        Returns:
            str: The results of the search.
        """
        search_results = []
        attempts = 0

        while attempts < self.config.duckduckgo_max_attempts:
            if not query:
                return json.dumps(search_results)

            # NOTE: If ToolGuard fuzzes num_results=0 or null, what happens here?
            search_results = DDGS().text(
                query, max_results=num_results, backend=self.config.duckduckgo_backend
            )

            if search_results:
                break

            time.sleep(1)
            attempts += 1

        search_results = [
            {
                "title": r["title"],
                "url": r["href"],
                **({"exerpt": r["body"]} if r.get("body") else {}),
            }
            for r in search_results
        ]

        results = ("## Search results\n") + "\n\n".join(
            f"### \"{r['title']}\"\n"
            f"**URL:** {r['url']}  \n"
            "**Excerpt:** " + (f'"{exerpt}"' if (exerpt := r.get("exerpt")) else "N/A")
            for r in search_results
        )
        return self.safe_google_results(results)


# =========================================================================
# TOOLGUARD FUZZING SCRIPT
# =========================================================================

def test_autogpt_web_search():
    print("Initializing AutoGPT WebSearchComponent...")
    comp = WebSearchComponentExtract()
    
    # We use ToolGuard to wrap it for fuzzing
    @create_tool(schema="auto")
    def autogpt_web_search(query: str, num_results: int = 8) -> str:
        return comp.web_search(query=query, num_results=num_results)
        
    print("Running ToolGuard Reliability Test on AutoGPT's duckduckgo search...")
    report = test_chain(
        [autogpt_web_search],
        test_cases=["happy_path", "null_handling", "malformed_data", "type_mismatch", "large_payload"],
        iterations=15,
        assert_reliability=0.0
    )
    
    print("\n" + "="*50)
    print("                TEST COMPLETE                ")
    print("="*50)
    print(f"Reliability Score: {report.reliability * 100:.1f}%")
    print(f"Total Tests: {report.total_tests}, Passed: {report.passed}, Failed: {report.failed}")
    
    if report.top_failures:
        print("\n🚨 VULNERABILITIES DETECTED IN AUTOGPT's CODE 🚨")
        for fail in report.top_failures:
            print(f"- [{fail['count']}x] crashed with {fail['error_type']}")
            print(f"  Root cause: {fail['root_cause']}")
            print(f"  Suggestion: {fail['suggestion']}")
            print()
            
    with open("autogpt_fuzz_report.json", "w") as f:
        f.write(report.to_json(indent=2))

if __name__ == "__main__":
    test_autogpt_web_search()
