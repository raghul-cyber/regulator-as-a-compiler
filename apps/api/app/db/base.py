# Import all the models, so that Base has them before being
# imported by Alembic
from app.models import Base
from app.models import *  # This will import everything listed in __all__ of app.models.__init__.py
