docker exec -i autopilot-template-backend-1 python3 -c "
from app.core.database import SessionLocal
from app.models.workbench import WorkbenchItem
db = SessionLocal()
db.query(WorkbenchItem).filter(WorkbenchItem.status == 'pending_approval').update({'status': 'approved'})
db.commit()
print('Workbench queue cleared and marked approved!')
db.close()
"




