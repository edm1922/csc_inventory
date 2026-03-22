from form_generator import generate_populated_report
import os

def test_printing():
    data = [
        ("2026-03-10", "BALLPEN", 1.0, "No", "UNTIL ITS DEFECTIVE"),
        ("2026-03-10", "INK/PEN REFILL", 1.0, "Yes", "2 WEEKS"),
        ("2026-03-10", "BROWN ENVELOPE", 10.0, "No", "")
    ]
    
    filename = generate_populated_report(
        "FLOREZ, RENNELLE",
        "Employee",
        "Unknown",
        "Shift 1",
        "John Doe",
        data
    )
    
    if os.path.exists(filename):
        print(f"PASS: {filename} generated successfully.")
    else:
        print("FAIL: Report not generated.")

if __name__ == "__main__":
    test_printing()
