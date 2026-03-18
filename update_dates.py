import sqlite3

def update_legacy_dates():
    conn = sqlite3.connect('supply_system.db')
    c = conn.cursor()
    
    # The 'MONITORING ' sheet had a date of 2026-10-03 assigned to the Sanitation team
    c.execute("""
        UPDATE supply_requests 
        SET request_date='2026-10-03 00:00:00.000000' 
        WHERE department_id IN (SELECT id FROM departments WHERE area_name='SANITATION MP')
    """)
    
    # The 'alejandro' sheet (Production) missed a date entirely in the Excel file, 
    # but based on the system state, we can assign it to March 1st as a placeholder for the legacy data 
    # so it differentiates from 'Today' (March 17th)
    c.execute("""
        UPDATE supply_requests 
        SET request_date='2026-03-01 00:00:00.000000' 
        WHERE department_id IN (SELECT id FROM departments WHERE area_name='PRODUCTION ')
    """)
    
    conn.commit()
    print(f"Updated {conn.total_changes} legacy records with historical dates.")
    conn.close()

if __name__ == "__main__":
    update_legacy_dates()
