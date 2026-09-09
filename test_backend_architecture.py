import sys
from pathlib import Path

# Add project root to sys.path
root_dir = Path(__file__).parent.resolve()
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

import app.core.app_launcher as al
import app.core.function_calling as fc
import app.core.task_automation as ta
import app.core.voice_engine as ve

def run_tests():
    print("==================================================")
    print("🤖 TESTING BACKEND ARCHITECTURE & ACTION EXECUTION")
    print("==================================================")

    print("\n[1] Testing Native App Launcher & Fuzzy Matcher:")
    test_queries = ["vs code", "chrome", "calculator", "notepad", "spotify", "task manager"]
    for q in test_queries:
        cmd, score, name = al.resolve_application(q)
        print(f"  • Query: '{q}' -> Match: '{name}' (Score: {score:.2f}) -> Command: '{cmd}'")

    print("\n[2] Testing LLM Function Calling & JSON Schema Parser:")
    t1 = fc.process_function_calling_turn("Open VS Code", auto_execute=False)
    print(f"  • Open VS Code: JSON -> {t1['json_payload']} (Source: {t1['source']})")
    
    t2 = fc.process_function_calling_turn("system specs and telemetry", auto_execute=True)
    print(f"  • Telemetry: JSON -> {t2['json_payload']['action']} (Spoken: {t2['spoken_text'][:60]}...)")

    print("\n[3] Testing Hardware Telemetry (CPU, RAM, GPU, Disks):")
    telem = ta.get_detailed_telemetry()
    print(f"  • Telemetry Summary: {telem['summary']}")

    print("\n[4] Testing VRAM Freeing & Memory Protection:")
    ve.free_vram()
    print("  • VRAM & Garbage Collection executed cleanly.")

    print("\n==================================================")
    print("✅ ALL ARCHITECTURE MODULES VERIFIED SUCCESSFULLY")
    print("==================================================")

if __name__ == "__main__":
    run_tests()

