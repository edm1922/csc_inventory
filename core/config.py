import json
import os

SETTINGS_FILE = "inventory_settings.json"

def get_thresholds():
    if os.path.exists(SETTINGS_FILE):
        try:
            with open(SETTINGS_FILE, "r") as f:
                return json.load(f)
        except Exception:
            pass
    return {"pcs_threshold": 50.0, "box_threshold": 10.0}

def save_thresholds(pcs, box):
    data = {"pcs_threshold": float(pcs), "box_threshold": float(box)}
    with open(SETTINGS_FILE, "w") as f:
        json.dump(data, f)

def get_effective_threshold(unit, custom_threshold=0.0):
    """Returns (threshold_value, is_custom)"""
    if custom_threshold and custom_threshold > 0:
        return custom_threshold, True
        
    t = get_thresholds()
    unit = (unit or "").strip().upper()
    if unit in ["PCS", "PC", "PIECES"]:
        return t.get("pcs_threshold", 50.0), False
    else:
        # User wants this to apply to the rest of the unit except for PCS
        return t.get("box_threshold", 10.0), False

def evaluate_stock_status(unit, qty, custom_threshold=0.0):
    threshold, is_custom = get_effective_threshold(unit, custom_threshold)
    
    if qty <= 0:
        return "Needs Restock"
        
    if threshold > 0 and qty < threshold:
        unit = (unit or "").strip().upper()
        if is_custom:
            # Custom thresholds default to "Low Stock" warning
            return "Low Stock"
        else:
            if unit in ["PCS", "PC", "PIECES"]:
                return "Needs Restock"
            return "Low Stock"
            
    return "Healthy Stock"
