"""Install the local API bridge into the pinned dependency, never Slither."""
import importlib.metadata,inspect,pathlib,hashlib
from crytic_compile.compilation_unit import CompilationUnit
assert importlib.metadata.version('crytic-compile') == '0.3.11'
p=pathlib.Path(inspect.getfile(CompilationUnit))
assert hashlib.sha256(p.read_bytes()).hexdigest() == '6da0cbdb6e04aed1f8856d0ab264d9596035f6d797dd5a6196314e49aff80727'
text=p.read_text()
assert 'row036 legacy artifact API' not in text
assert not hasattr(CompilationUnit,'bytecode_init')
p.write_text(text+'\n# row036 legacy artifact API, delegated to the real compiler source unit\nfrom crytic_legacy_api import install as _install_legacy_artifacts\n_install_legacy_artifacts(CompilationUnit)\n')
p.chmod(0o644)
print('Installed legacy artifact API for pinned CryticCompile 0.3.11:',p)
