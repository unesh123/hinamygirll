"""Phase 01 - Stream Integrity & Duplication Verification Suite."""
import requests
import json
import time
import sys
from typing import Any

URL = "http://127.0.0.1:8000/api/v1/conversations/turns:stream"

TEST_PROMPTS = [
    {
        "name": "Short Greeting",
        "text": "Hi Hina! Give me a quick one-sentence hello.",
    },
    {
        "name": "Emoji & Emoticon Ending",
        "text": "Tell me what you love doing most in 2 sentences, and end with a heart emoji.",
    },
    {
        "name": "Markdown & Python Code Block",
        "text": "Write a 3-line Python function that reverses a list with a short Markdown explanation.",
    },
    {
        "name": "Multi-paragraph Structured Query",
        "text": "Explain the difference between SQLite and PostgreSQL in 2 distinct bullet points.",
    }
]

def run_stream_test(name: str, prompt_text: str) -> dict[str, Any]:
    print(f"\n[STREAM TEST] Running: {name}")
    payload = {
        "sessionId": f"verify-stream-{int(time.time()*1000)}",
        "text": prompt_text,
        "providerMode": "xkiro"
    }
    
    t0 = time.time()
    ttfb = None
    deltas: list[str] = []
    events: list[dict[str, Any]] = []
    
    try:
        with requests.post(URL, json=payload, stream=True, timeout=75) as r:
            if r.status_code != 200:
                return {
                    "name": name,
                    "status": "FAIL",
                    "http_status": r.status_code,
                    "error": f"HTTP {r.status_code}"
                }
            for line in r.iter_lines():
                if line:
                    decoded = line.decode("utf-8", errors="replace")
                    try:
                        data = json.loads(decoded)
                        ev_type = data.get("type")
                        events.append(data)
                        if ev_type == "text.delta":
                            if ttfb is None:
                                ttfb = time.time() - t0
                            deltas.append(data.get("delta", ""))
                    except Exception:
                        pass
        total_time = time.time() - t0
        full_text = "".join(deltas)
        
        # Duplication check: Split into paragraphs and check if any paragraph (>30 chars) appears twice
        paragraphs = [p.strip() for p in full_text.split("\n\n") if len(p.strip()) > 30]
        duplicates = []
        seen = set()
        for p in paragraphs:
            # Normalize whitespace
            norm = " ".join(p.split())
            if norm in seen:
                duplicates.append(norm[:50] + "...")
            seen.add(norm)
            
        run_completed_count = sum(1 for e in events if e.get("type") == "run.completed")
        plan_completed_count = sum(1 for e in events if e.get("type") == "planning.completed")
        
        passed = (
            len(duplicates) == 0
            and len(full_text.strip()) > 0
            and run_completed_count == 1
            and plan_completed_count == 1
        )
        
        print(f" -> Result: {'PASSED' if passed else 'FAILED'}")
        print(f" -> TTFB: {ttfb:.2f}s | Total: {total_time:.2f}s | Length: {len(full_text)} chars")
        if duplicates:
            print(f" -> DUPLICATE PARAGRAPHS DETECTED: {duplicates}")
            
        return {
            "name": name,
            "status": "PASS" if passed else "FAIL",
            "ttfb_s": round(ttfb or 0, 3),
            "total_time_s": round(total_time, 2),
            "chars_streamed": len(full_text),
            "paragraphs_count": len(paragraphs),
            "duplicates_detected": duplicates,
            "run_completed_events": run_completed_count,
            "sample_snippet": full_text[:120].replace("\n", " "),
        }
    except Exception as e:
        print(f" -> Exception: {e}")
        return {
            "name": name,
            "status": "ERROR",
            "error": str(e)
        }

if __name__ == "__main__":
    results = []
    for test in TEST_PROMPTS:
        res = run_stream_test(test["name"], test["text"])
        results.append(res)
        time.sleep(1)
        
    summary_path = "docs/evolution/stream_integrity_results.json"
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)
    print(f"\nAll results saved to {summary_path}")
    all_passed = all(r.get("status") == "PASS" for r in results)
    sys.exit(0 if all_passed else 1)
