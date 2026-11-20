"""Legacy compilation-unit artifact API over CryticCompile's real SourceUnits.

The frozen Slither source predates the artifact API move to SourceUnit. Delegate
rather than duplicating compiler output or substituting synthetic bytecode.
"""

def install(compilation_unit_class):
    def lookup(self, contract_name, method, *args, **kwargs):
        matches = [unit for unit in self.source_units.values()
                   if contract_name in unit.contracts_names]
        if not matches:
            raise KeyError(contract_name)
        if len(matches) != 1:
            raise ValueError('Ambiguous contract name: ' + contract_name)
        return getattr(matches[0], method)(contract_name, *args, **kwargs)

    def make_method(name):
        def artifact(self, contract_name, *args, **kwargs):
            return lookup(self, contract_name, name, *args, **kwargs)
        artifact.__name__ = name
        artifact.__doc__ = 'Delegate the legacy API to the unique real SourceUnit.'
        return artifact

    for name in ('bytecode_init', 'bytecode_runtime', 'srcmap_init', 'srcmap_runtime'):
        if hasattr(compilation_unit_class, name):
            raise RuntimeError('Unexpected CryticCompile API already provides ' + name)
        setattr(compilation_unit_class, name, make_method(name))
