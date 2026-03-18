from database import SessionLocal, Employee, SupplyRequest, Department
from sqlalchemy.orm import joinedload

employees_to_check = [
    "PARCON, MERZEL", "DELA CRUZ, JOSHUA", "FLOREZ, RENNELLE", "HORTILANO, CLAIRE", "SABALOSA, ANNELYN",
    "CANLIAN, JOHARLIE", "LABELLA, JAKE", "JACKOSALEM, ESMINA", "BRACE, ARLENE", "BERÑIL, JOY ANN",
    "BARON, CHRISTHOPER", "PLANTIG, JOSHUA", "OLID PERIGREIN", "PANERIO, MARVIN", "LABELLA GERELLE VIC", "ESCRIBANO MARIS",
    "FAILAN, RODELYN", "ANTOLAN, JUPHET", "PLAZOS, RICA", "QUIJANO, NELSON", "ABATOL, JOVELY",
    "COARTE, RAVELO GIAN CARLO", "MAKASPE, ANDRES", "MAKASPE, SADAM", "PACARDO, DAILYN",
    "CORNEJO, MELVIN"
]

with SessionLocal() as session:
    print(f"{'Employee Name':<30} | {'Role':<25} | {'Area':<20} | {'Supervisor':<20}")
    print("-" * 100)
    for name in employees_to_check:
        emp = session.query(Employee).filter(Employee.name == name).first()
        if emp:
            # Get latest request to find area/supervisor
            latest_req = session.query(SupplyRequest).filter(SupplyRequest.employee_id == emp.id).order_by(SupplyRequest.request_date.desc()).first()
            area = "N/A"
            supervisor = "N/A"
            if latest_req:
                dept = session.query(Department).get(latest_req.department_id)
                if dept:
                    area = dept.area_name
                    supervisor = dept.supervisor
            print(f"{emp.name:<30} | {str(emp.role):<25} | {str(area):<20} | {str(supervisor):<20}")
        else:
            print(f"{name:<30} | {'NOT FOUND':<25} | {'N/A':<20} | {'N/A':<20}")
