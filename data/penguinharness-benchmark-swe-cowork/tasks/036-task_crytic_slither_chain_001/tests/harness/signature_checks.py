"""Exercise the actual declaration -> canonical signature -> printer chain."""
from types import SimpleNamespace


def function(name, types, unit=None, contract=None):
    from slither.core.declarations.function_contract import FunctionContract
    from slither.core.declarations.function import FunctionType
    from slither.core.variables.local_variable import LocalVariable
    f = FunctionContract(unit)
    f.name = name
    f.set_function_type(FunctionType.NORMAL)
    f.set_visibility('public')
    if contract is not None:
        f.set_contract(contract)
        f.set_contract_declarer(contract)
    for t in types:
        p = LocalVariable()
        p.set_type(t)
        p.set_function(f)
        f.add_parameters(p)
    return f


def printed(functions):
    from slither.printers.summary.function_ids import FunctionIds
    from slither.core.declarations.contract import Contract
    from slither.core.scope.scope import FileScope
    from crytic_compile.utils.naming import Filename
    unit = SimpleNamespace(core=SimpleNamespace(source_code={}, crytic_compile=None))
    contract = Contract(unit, FileScope(Filename('a.sol','a.sol','a.sol','a.sol')))
    contract.name = 'Example'
    for f in functions:
        f.set_contract(contract)
        f.set_contract_declarer(contract)
        contract.add_function(f)
    slither = SimpleNamespace(contracts=[contract], contracts_derived=[contract], filename='a.sol')
    result = FunctionIds(slither, None).output(None)
    return result.data['description']


def assert_selector(text, signature):
    from Crypto.Hash import keccak
    from slither.utils.function import get_function_id
    expected = keccak.new(digest_bits=256, data=signature.encode()).hexdigest()[:8]
    assert get_function_id(signature) == int(expected, 16)
    assert signature in text
    assert '0x' + expected in text


def check_arrays():
    from slither.core.solidity_types import ArrayType, ElementaryType
    scalar = ElementaryType('uint256')
    cases = [(scalar, 'uint256'), (ArrayType(scalar, None), 'uint256[]'),
             (ArrayType(scalar, 2), 'uint256[2]'),
             (ArrayType(ArrayType(scalar, 2), None), 'uint256[2][]'),
             (ArrayType(ArrayType(scalar, None), 3), 'uint256[][3]'),
             (ArrayType(ArrayType(scalar, 2), 3), 'uint256[2][3]')]
    functions = []
    for index, (t, spelling) in enumerate(cases):
        f = function(f'case{index}', [t])
        assert f.solidity_signature == f'case{index}({spelling})'
        functions.append(f)
    text = printed(functions)
    for f in functions:
        assert_selector(text, f.solidity_signature)


def check_visibility():
    from slither.core.declarations.function import FunctionType
    visible = function('visible', [])
    hidden = function('shadowed', [])
    hidden.is_shadowed = True
    ctor = function('ctorvars', [])
    ctor.set_function_type(FunctionType.CONSTRUCTOR_VARIABLES)
    internal = function('inside', [])
    internal.set_visibility('internal')
    text = printed([visible, hidden, ctor, internal])
    assert_selector(text, 'visible()')
    assert all(name not in text for name in ('shadowed', 'ctorvars', 'inside'))


def struct(name, fields):
    from slither.core.declarations.structure import Structure
    from slither.core.variables.structure_variable import StructureVariable
    from slither.core.solidity_types import UserDefinedType
    s = Structure(None)
    s.name = name
    for i, t in enumerate(fields):
        v = StructureVariable()
        v.name = str(i)
        v.set_type(t)
        s.elems[v.name] = v
        s.add_elem_in_order(v.name)
    return UserDefinedType(s)


def check_structs():
    from slither.core.solidity_types import ArrayType, ElementaryType
    from slither.core.variables.structure_variable import StructureVariable
    from slither.utils.type import convert_type_for_solidity_signature_to_string as convert
    leaf = struct('Leaf', [ElementaryType('uint256')])
    pair = struct('Pair', [leaf, leaf, ArrayType(leaf, 2)])
    expected = '((uint256),(uint256),(uint256)[2])'
    assert convert(pair) == expected
    f = function('pair', [pair])
    assert f.solidity_signature == 'pair(' + expected + ')'
    assert_selector(printed([f]), f.solidity_signature)
    recursive = struct('St', [])
    for name, t in [('a', ArrayType(recursive, None)), ('b', ElementaryType('uint256'))]:
        field = StructureVariable()
        field.name = name
        field.set_type(t)
        recursive.type.elems[name] = field
        recursive.type.add_elem_in_order(name)
    assert convert(recursive) == '(St[],uint256)'
    assert convert(ArrayType(recursive, 2)) == '(St[],uint256)[2]'
