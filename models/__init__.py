# Importing each module here is what actually registers its model classes
# on Base.metadata. `import models` elsewhere (e.g. alembic/env.py) only
# triggers these — without them listed here, autogenerate sees an empty
# metadata object and produces empty migrations no matter what changed.
from . import complaint_model  # noqa: F401
from . import config_model  # noqa: F401
from . import notice_model  # noqa: F401
from . import user_model  # noqa: F401