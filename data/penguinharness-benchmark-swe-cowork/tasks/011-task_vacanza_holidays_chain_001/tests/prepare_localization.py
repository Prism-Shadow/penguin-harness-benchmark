from concurrent.futures import ProcessPoolExecutor
from functools import partial
import importlib


for module in ("polib", "pytest", "pytest_cov", "coverage", "xdist", "numpy", "pygments"):
    importlib.import_module(module)

from scripts.l10n import generate_mo_files

generate_mo_files.ProcessPoolExecutor = partial(ProcessPoolExecutor, max_workers=2)
generate_mo_files.MOGenerator.run()
print("Production MOGenerator completed with at most two workers")
