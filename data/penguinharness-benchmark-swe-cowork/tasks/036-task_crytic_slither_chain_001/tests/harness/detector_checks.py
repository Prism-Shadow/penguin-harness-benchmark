from repair_checks import contract_fixture
from signature_checks import function


def local(name):
    from slither.core.variables.local_variable import LocalVariable
    v=LocalVariable();v.name=name;v.set_type('uint256');return v


def node(f, contract, kind, i, irs=()):
    from slither.core.cfg.node import Node
    from slither.core.expressions.literal import Literal
    n=Node(kind,i,f,contract.file_scope);n.set_function(f)
    n.set_offset('0:0:-1',contract.compilation_unit)
    for ir in irs:ir.set_node(n);n.irs.append(ir)
    n.add_expression(Literal(str(i),'uint256'))
    f.add_node(n)
    return n


def check_loops():
    from slither.core.cfg.node import NodeType
    from slither.core.variables.state_variable import StateVariable
    from slither.core.declarations import SolidityVariableComposed
    from slither.slithir.operations import LowLevelCall, Assignment
    from slither.slithir.variables import Constant
    from slither.detectors.statements.calls_in_loop import call_in_loop
    from slither.detectors.statements.costly_operations_in_loop import costly_operations_in_loop
    from slither.detectors.statements.delegatecall_in_loop import delegatecall_in_loop
    from slither.detectors.statements.msg_value_in_loop import msg_value_in_loop
    state=StateVariable();state.name='balance';state.set_type('uint256')
    operations=[LowLevelCall(local('target'),Constant('call'),0,None,''),
                Assignment(state,Constant('1'),None),
                LowLevelCall(local('target'),Constant('delegatecall'),0,None,''),
                Assignment(local('value'),SolidityVariableComposed('msg.value'),None)]
    for helper,operation in zip((call_in_loop,costly_operations_in_loop,delegatecall_in_loop,msg_value_in_loop),operations):
        findings=[];helper(None,0,[],findings);assert findings==[]
        contract,_=contract_fixture();f=function('f',[],contract.compilation_unit,contract)
        begin=node(f,contract,NodeType.STARTLOOP,0)
        body=node(f,contract,NodeType.EXPRESSION,1,[operation])
        end=node(f,contract,NodeType.ENDLOOP,2)
        begin.add_son(body);body.add_son(end)
        findings=[];helper(begin,0,[],findings);assert findings==[body]
        findings=[];helper(body,0,[],findings);assert findings==[]
        # Revisiting a real graph terminates without duplicate findings.
        end.add_son(begin);findings=[];helper(begin,0,[],findings);assert findings==[body]


def check_division():
    from slither.core.cfg.node import NodeType
    from slither.slithir.operations import Binary, BinaryType
    from slither.slithir.variables import Constant
    from slither.detectors.statements.divide_before_multiply import DivideBeforeMultiply
    from slither.core.slither_core import SlitherCore
    for operator, expected in ((BinaryType.MULTIPLICATION,True),(BinaryType.ADDITION,False)):
        contract,_=contract_fixture()
        unit=contract.compilation_unit;unit.core=SlitherCore();unit.core.triage_mode=False
        contract.set_offset('0:0:-1',unit)
        f=function('calculate',[],unit,contract);f.set_offset('0:0:-1',unit)
        x,y=local('quotient'),local('result')
        div=node(f,contract,NodeType.EXPRESSION,1,[Binary(x,Constant('10'),Constant('3'),BinaryType.DIVISION)])
        mul=node(f,contract,NodeType.EXPRESSION,2,[Binary(y,x,Constant('2'),operator)])
        div.add_son(mul);contract.add_function(f)
        detector=DivideBeforeMultiply(unit,unit.core,None)
        result=detector.detect()
        assert bool(result) is expected
        if expected:
            assert len(result)==1
            assert result[0]['description'].splitlines()==[
                'Sample.calculate() () performs a multiplication on the result of a division:',
                '\t- 1 ()', '\t- 2 ()']
            assert [element['type'] for element in result[0]['elements']]==['function','node','node']
            assert result[0]['check']=='divide-before-multiply'
