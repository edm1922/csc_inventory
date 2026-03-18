from database import SessionLocal, Employee

def fix_name():
    with SessionLocal() as session:
        emp = session.query(Employee).filter(Employee.name.like('RATUNIL%')).first()
        if emp:
            emp.name = 'RATUNIL, NEÑO'
            session.commit()
            print("Fixed name for RATUNIL, NEÑO")
        else:
            print("Employee RATUNIL not found")

if __name__ == "__main__":
    fix_name()
