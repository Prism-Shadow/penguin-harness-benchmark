#!/usr/bin/env python3
"""Stateful JJ protocol fixture. Unsupported syntax is a fixture error, not empty success."""
import hashlib
import json
import os
import re
import sys
from pathlib import Path


DEFAULT_STATE = {
    "recent": [["recent001", "recent change"], ["recent002", "another change"]],
    "head": [["head000", "current change"], ["head001", "parent change"], ["head002", "older change"]],
    "next": [["next001", "child change"], ["next002", "newer change"]],
    "tags": [["v-test", "tagged release"]],
    "operations": [["op0001", "initialize repo"], ["op0002", "fetch origin"]],
    "files": {"@": ["README.md", "src/main.go"], "left": ["left.txt", "nested/left.go"], "right": ["right.txt"], "empty": []},
    "diffs": {"@|@-": [["M", "src/main.go"], ["A", "docs/new.md"]], "left|left-": [["M", "left.txt"]], "right|right-": [["A", "right.txt"]], "left|right": [["M", "range.txt"]], "@|right": [["M", "to-only.txt"]], "left|@": [["D", "from-only.txt"]], "empty|empty-": []},
    "interdiffs": {"left|right": [["M", "range.txt"]], "@|right": [["M", "to-only.txt"]], "left|@": [["D", "from-only.txt"]]},
    "changes": {"@": [["M", "src/main.go"], ["A", "docs/new.md"]], "left": [["M", "left.txt"]], "right": [["A", "right.txt"]], "empty": []},
    "parents": {"@": ["@-"], "@-": [], "left": ["left-"], "left-": [], "right": ["right-"], "right-": [], "empty": []},
    "immutable_heads": [],
    "branches": {"main": {"description": "abc1234 main branch", "remotes": {"origin": "aaa1111 ooo1111 origin main"}}, "feature": {"description": "def5678 feature branch", "remotes": {"origin": "ghi9012 xxx0001 remote branch", "upstream": "ghi9013 xxx0002 upstream feature"}}, "other": {"description": "fff2222 other branch", "remotes": {"upstream": "hhh3333 xxx0003 other upstream"}}},
    "remotes": {"origin": "https://example.invalid/origin", "upstream": "https://example.invalid/upstream"},
    "workspaces": {"default": "qzzmpvmx current workspace", "review": "oxtpukyp review workspace"},
    "conflicts": {"@": {"conflict.txt": "2-sided conflict"}, "left": {"left-conflict.txt": "2-sided conflict"}, "right": {}, "empty": {}},
    "config": {"user.name": "Example User", "ui.editor": "vim"},
    "defaults": {"colors.commit_id": "blue"},
}


def options(arguments):
    aliases = {"-r": "--revisions", "--revision": "--revisions", "-T": "--template", "-n": "--limit", "-s": "--summary"}
    valued = {"--revisions", "--template", "--limit", "--from", "--to", "--remote", "--color", "--repository", "-R", "--config-toml"}
    flags, positional = {}, []
    index = 0
    while index < len(arguments):
        token = arguments[index]
        if token == "--":
            positional.extend(arguments[index + 1:])
            break
        attached = None
        if token.startswith("--") and "=" in token:
            token, attached = token.split("=", 1)
        elif len(token) > 2 and token[:2] in ("-r", "-T", "-n"):
            token, attached = token[:2], token[2:]
        token = aliases.get(token, token)
        if token in valued:
            if attached is None:
                index += 1
                attached = arguments[index]
            flags.setdefault(token, []).append(attached)
        elif token.startswith("-"):
            flags[token] = [True]
        else:
            positional.append(token)
        index += 1
    return flags, positional


def split_expression(text, separator):
    parts, start, depth, quoted, escaped = [], 0, 0, False, False
    index = 0
    while index < len(text):
        char = text[index]
        if quoted:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                quoted = False
        elif char == '"':
            quoted = True
        elif char == '(':
            depth += 1
        elif char == ')':
            depth -= 1
        elif depth == 0 and text.startswith(separator, index):
            parts.append(text[start:index].strip())
            index += len(separator)
            start = index
            continue
        index += 1
    parts.append(text[start:].strip())
    return parts


def template(expression, record):
    from jj_template import render as render_template
    return render_template(expression, record)


def enclosed(expression):
    """Return the inside of one (...) group spanning the whole expression."""
    if not expression.startswith('(') or not expression.endswith(')'):
        return None
    depth, quoted = 0, False
    for char in expression[1:-1]:
        if char == '"':
            quoted = not quoted
        elif not quoted:
            depth += {'(': 1, ')': -1}.get(char, 0)
            if depth < 0:
                return None
    return expression[1:-1] if depth == 0 else None


def split_operators(text, operators):
    """Split at top-level binary operators, keeping the operators."""
    parts, start, depth, quoted = [], 0, 0, False
    for index, char in enumerate(text):
        if char == '"':
            quoted = not quoted
        elif quoted:
            continue
        elif char == '(':
            depth += 1
        elif char == ')':
            depth -= 1
        elif depth == 0 and char in operators:
            parts += [text[start:index].strip(), char]
            start = index + 1
    return parts + [text[start:].strip()]


def revision_set(expression, state):
    expression = expression.strip()
    # JJ 0.11 precedence: | binds loosest, then & and ~ (left associative),
    # then the range operators, then postfix -/+ and primaries.
    unions = split_expression(expression, '|')
    if len(unions) > 1:
        return set().union(*(revision_set(part, state) for part in unions))
    operands = split_operators(expression, '&~')
    if len(operands) > 1:
        # An empty operand before ~ is prefix negation: ~x is all() ~ x.
        result, pending, index = None, '&', 0
        while index < len(operands):
            negated = False
            while not operands[index] and index + 2 < len(operands) and operands[index + 1] == '~':
                negated, index = not negated, index + 2
            if not operands[index]:
                raise ValueError('incomplete revset operator: ' + expression)
            selected = revision_set(operands[index], state)
            if negated:
                selected = revision_set('all()', state) - selected
            result = selected if result is None else (result & selected if pending == '&' else result - selected)
            if index + 1 < len(operands):
                pending = operands[index + 1]
            index += 2
        return result
    inner = enclosed(expression)
    if inner is not None:
        return revision_set(inner, state)
    if expression == 'immutable_heads()':
        return set(state['immutable_heads'])
    if expression == 'none()':
        return set()
    if expression == 'root()':
        # The virtual root commit is not part of the fixture graph and has no
        # changes, so it never contributes a revision or a summary.
        return set()
    if expression == 'all()':
        return set(state['parents'])
    ranges = split_expression(expression, '..')
    if len(ranges) == 2:
        return revision_set('ancestors(' + (ranges[1] or '@') + ')', state) - revision_set('ancestors(' + (ranges[0] or '@') + ')', state)
    dag = split_expression(expression, '::')
    if len(dag) == 2:
        if not dag[0] and not dag[1]:
            return revision_set('all()', state)
        if not dag[0]:
            return revision_set('ancestors(' + dag[1] + ')', state)
        if not dag[1]:
            return revision_set('descendants(' + dag[0] + ')', state)
        return revision_set('descendants(' + dag[0] + ')', state) & revision_set('ancestors(' + dag[1] + ')', state)
    function = re.fullmatch(r'(ancestors|descendants|heads|parents|children)(\(.*\))', expression)
    if function and enclosed(function[2]) is not None:
        arguments = split_expression(enclosed(function[2]), ',')
        selected = revision_set(arguments[0], state)
        if function[1] in ('parents', 'children'):
            if len(arguments) != 1:
                raise ValueError('parent/child revset requires one argument')
            if function[1] == 'parents':
                return {parent for item in selected for parent in state['parents'][item]}
            return {item for item, parents in state['parents'].items() if selected.intersection(parents)}
        if function[1] == 'heads':
            ancestors = set().union(*(revision_set('ancestors(' + parent + ')', state) for item in selected for parent in state['parents'][item]))
            return selected - ancestors
        pending = set(selected)
        result = set()
        remaining = int(arguments[1]) if len(arguments) > 1 else len(state['parents']) + 1
        while pending and remaining > 0:
            result.update(pending)
            if function[1] == 'descendants':
                pending = {item for item, parents in state['parents'].items() if pending.intersection(parents)} - result
            else:
                pending = {parent for item in pending for parent in state['parents'][item]} - result
            remaining -= 1
        return result
    if expression in state.get('revision_aliases', {}):
        return {state['revision_aliases'][expression]}
    if expression in state['parents']:
        return {expression}
    # Summary states name parent commits literally (e.g. "@-"); other
    # postfix navigation is the JJ parents/children operator.
    if expression[-1:] in ('-', '+') and len(expression) > 1:
        return revision_set(('parents(' if expression[-1] == '-' else 'children(') + expression[:-1] + ')', state)
    raise ValueError('unsupported summary revset: ' + expression)


def log_graph(state):
    """Build one parent graph for log traversal, separate from diff summaries.

    Legacy head/next lists describe a linear history around @. A test can
    supply log_graph={current, records, parents} to describe branches/merges.
    Records set the stable tie order between unrelated commits. Every result
    uses reverse topological order; --reversed reverses that order.
    """
    explicit = state.get('log_graph')
    if explicit is not None:
        rows = explicit['records']
        current = explicit['current']
        parents = explicit['parents']
    else:
        head, following = state['head'], state['next']
        rows = list(reversed(following)) + list(head)
        current = head[0][0] if head else '@'
        parents = {identifier: [] for identifier, _ in rows}
        parents.setdefault(current, [])
        for child, parent in zip(head, head[1:]):
            parents[child[0]] = [parent[0]]
        parent = current
        for child, _ in following:
            parents[child] = [parent]
            parent = child
    identifiers = [identifier for identifier, _ in rows]
    if len(set(identifiers)) != len(identifiers):
        raise ValueError('duplicate log graph record')
    allowed = set(identifiers) | ({'@'} if explicit is None and not state['head'] else set())
    if (set(parents) != allowed or current not in allowed
            or any(not set(edges) <= allowed for edges in parents.values())):
        raise ValueError('log graph records and edges disagree')
    order, pending = [], list(identifiers)
    if current not in pending:
        pending.append(current)
    while pending:
        referenced = {parent for child in pending for parent in parents[child]}
        ready = [item for item in pending if item not in referenced]
        if not ready:
            raise ValueError('cyclic log graph')
        order.extend(ready)
        pending = [item for item in pending if item not in ready]
    records = dict(rows)
    graph = {'parents': parents, 'immutable_heads': [], 'revision_aliases': {'@': current}}
    return graph, [(item, records[item]) for item in order if item in records]


def graph_log_rows(expression, state, reversed_order=False):
    graph, ordered = log_graph(state)
    aliases = {'::@': 'ancestors(@)', '@-::': 'descendants(parents(@))'}
    if expression in ('(@::) ~ @', '@:: ~ @'):
        selected = revision_set('descendants(@)', graph) - revision_set('@', graph)
    else:
        selected = revision_set(aliases.get(expression, expression), graph)
    rows = [row for row in ordered if row[0] in selected]
    return list(reversed(rows)) if reversed_order else rows


def tag_rows(state):
    """A tag is a named reference to a commit, not a commit identifier."""
    targets = state.get('tag_targets', {})
    return [(targets.get(name, hashlib.sha1(('fixture tag target:' + name).encode()).hexdigest()),
             name, description) for name, description in state['tags']]


def log_records(state):
    """Expose the same state through list commands and typed log templates."""
    graph, ordered = log_graph(state)
    records = {}
    tag_commits = [(identifier, description) for identifier, _, description in tag_rows(state)]
    for identifier, description in ordered + state['recent'] + tag_commits:
        records.setdefault(identifier, dict(commit_id=identifier, change_id=identifier, id=identifier,
                                             description=description, parents=[], tags=[], branches=[], remote_branches=[], working_copies='',
                                             current_working_copy=identifier == graph['revision_aliases']['@']))
    for child, parents in graph['parents'].items():
        if child in records:
            records[child]['parents'] = [records[parent] for parent in parents if parent in records]
    local, remote = [], []
    for name, branch in state['branches'].items():
        variants = [(None, branch['description'])] + list(branch['remotes'].items())
        for origin, text in variants:
            # branch list prints change-id, then (on remotes) commit-id, then description.
            fields = text.split(' ', 2 if origin else 1)
            expected = 3 if origin else 2
            if len(fields) != expected:
                raise ValueError('malformed branch fixture record')
            identifier, description = fields[-2:]
            record = records.setdefault(identifier, dict(commit_id=identifier, change_id=fields[0],
                id=identifier, description=description, parents=[], tags=[], branches=[], remote_branches=[],
                working_copies='', current_working_copy=identifier == graph['revision_aliases']['@']))
            ref = dict(_kind='ref', name=name, remote=origin or '')
            field = 'remote_branches' if origin else 'branches'
            record[field].append(ref)
            (remote if origin else local).append(identifier)
    # JJ 0.11 working_copies is a String keyword: "name@" for each workspace
    # whose working-copy commit is this one, space separated, and empty when
    # the repository has a single workspace. The default workspace is at @;
    # other workspace records start with their working-copy commit id.
    workspaces = state['workspaces']
    for name, text in sorted(workspaces.items()):
        target = graph['revision_aliases']['@'] if name == 'default' else text.split(' ', 1)[0]
        if len(workspaces) > 1 and target in records:
            record = records[target]
            record['working_copies'] = ' '.join(filter(None, [record.get('working_copies', ''), name + '@']))
    for identifier, name, description in tag_rows(state):
        # Like branch references, JJ 0.11 tags are RefName values. Their
        # display is the name, and .name() is also a valid typed accessor.
        records[identifier]['tags'].append(dict(_kind='ref', name=name, remote=''))
    return records, list(dict.fromkeys(local)), list(dict.fromkeys(remote))


def render(arguments, state):
    flags, command = options(arguments)
    revision = flags.get('--revisions', ['@'])[-1]
    command = ['operation' if part == 'op' else part for part in command]
    if command[:2] == ['git', 'remote'] and command[2:] == ['list']:
        return ''.join(f'{name} {url}\n' for name, url in state['remotes'].items())
    if command == ['workspace', 'list']:
        return ''.join(f'{name}: {description}\n' for name, description in state['workspaces'].items())
    if command == ['files']:
        return ''.join(path + '\n' for path in state['files'][revision])
    if command == ['resolve'] and '--list' in flags:
        return ''.join(f'{path}    {description}\n' for path, description in state['conflicts'][revision].items())
    if command[:2] == ['config', 'list'] and len(command) <= 3:
        values = dict(state['defaults']) if '--include-defaults' in flags else {}
        values.update(state['config'])
        if len(command) == 3:
            # JJ 0.11 lists the named table/key; an absent name is a warning
            # on stderr with empty output and a zero exit status.
            name = command[2]
            values = {key: value for key, value in values.items() if key == name or key.startswith(name + '.')}
            if not values:
                print('No matching config key for ' + name, file=sys.stderr)
        return ''.join(f'{key}={value}\n' for key, value in values.items())
    if command == ['util', 'config-schema']:
        # The schema is compiled into the JJ binary and independent of
        # repository state; this is the verbatim JJ 0.11.0 output.
        return Path(__file__).with_name('jj_config_schema.json').read_text()
    if command == ['branch', 'list']:
        return ''.join(name + ': ' + branch['description'] + '\n' + (''.join(f'  @{remote}: {description}\n' for remote, description in branch['remotes'].items()) if '--all' in flags else '') for name, branch in state['branches'].items())
    if command == ['diff'] and '--types' in flags:
        # A root-to-revision diff describes every existing target file. The
        # source type is absent (-); JJ 0.11 uses F for files and C for conflicts.
        if flags.get('--from') != ['root()'] or '--revisions' in flags:
            raise ValueError('unsupported type-summary range')
        target = flags.get('--to', ['@'])[-1]
        paths = set(state['files'][target]) | set(state['conflicts'][target])
        return ''.join('-' + ('C' if path in state['conflicts'][target] else 'F') + ' ' + path + '\n'
                       for path in sorted(paths))
    if command == ['interdiff'] and '--summary' in flags:
        if '--from' not in flags and '--to' not in flags:
            raise ValueError('interdiff requires --from or --to')
        endpoints = [flags.get('--from', ['@'])[-1], flags.get('--to', ['@'])[-1]]
        # Interdiff compares changes after rebasing, not the endpoint trees.
        # Keep its authored state separate from ordinary diff summaries.
        pairs = [] if endpoints[0] == endpoints[1] else state['interdiffs'].get('|'.join(endpoints))
        if pairs is None:
            raise ValueError('unknown interdiff range: ' + repr(endpoints))
        return ''.join(f'{status} {path}\n' for status, path in pairs)
    if command == ['diff'] and '--summary' in flags:
        if '--revisions' in flags:
            endpoints = [revision, revision + '-']
        else:
            endpoints = [flags.get('--from', ['@'])[-1], flags.get('--to', ['@' if '--from' in flags else '@-'])[-1]]
        pairs = [] if endpoints[0] == endpoints[1] else state['diffs'].get('|'.join(endpoints))
        if pairs is None:
            pairs = state['diffs'].get('|'.join(reversed(endpoints)))
        if pairs is None:
            raise ValueError('unknown diff range: ' + repr(endpoints))
        return ''.join(f'{status} {path}\n' for status, path in pairs)
    if command == ['log'] and '--summary' in flags:
        revisions = set().union(*(revision_set(selected, state) for selected in flags.get('--revisions', ['@'])))
        pairs = [pair for revision in sorted(revisions) for pair in state['changes'].get(revision, [])]
        return ''.join(f'{status} {path}\n' for status, path in pairs)
    if command in (['log'], ['operation', 'log']):
        if command == ['operation', 'log']:
            rows = state['operations']
        elif revision in ('branches()', 'remote_branches()'):
            records, local, remote = log_records(state)
            identifiers = remote if revision == 'remote_branches()' else local
            rows = [(identifier, records[identifier]['description']) for identifier in identifiers]
        elif revision == 'tags()':
            records, _, _ = log_records(state)
            identifiers = dict.fromkeys(identifier for identifier, _, _ in tag_rows(state))
            rows = [(identifier, records[identifier]['description']) for identifier in identifiers]
        elif revision == 'all()' and state.get('log_graph') is None:
            # The legacy recent/tag/reference catalogs describe visible
            # commits too. Dropping them from all() contradicts those same
            # fixture records and rejects valid alternatives to default log.
            records, _, _ = log_records(state)
            rows = [(identifier, record['description']) for identifier, record in records.items()]
            if '--reversed' in flags:
                rows.reverse()
        elif state.get('log_graph') is not None:
            rows = graph_log_rows(revision, state, '--reversed' in flags)
        elif revision in ('::@', 'ancestors(@)'):
            rows = state['head']
        elif revision in ('@-::', '(@::) ~ @', '@:: ~ @'):
            rows = list(reversed(state['next']))
            if revision == '@-::':
                rows += state['head'][:2]
            if '--reversed' in flags:
                rows.reverse()
        elif revision == '@':
            rows = state['recent']
        else:
            rows = graph_log_rows(revision, state, '--reversed' in flags)
        rows = rows[:int(flags.get('--limit', [len(rows)])[-1])]
        expression = flags.get('--template', ['commit_id ++ "\\t" ++ description ++ "\\n"'])[-1]
        records, _, _ = log_records(state)
        return ''.join(template(expression, records.get(identifier, dict(commit_id=identifier,
            change_id=identifier, id=identifier, description=description, tags=[], parents=[],
            branches=[], remote_branches=[], working_copies=''))) for identifier, description in rows)
    raise ValueError('unsupported JJ command: ' + repr(arguments))


def main():
    state = json.loads(Path(os.environ['JJ_FIXTURE_STATE']).read_text())
    try:
        if state.get('error'):
            print('repository query failed', file=sys.stderr)
            return 1
        sys.stdout.write(render(sys.argv[1:], state))
        return 0
    except (ValueError, KeyError, IndexError) as error:
        message = 'fixture protocol unsupported: ' + str(error)
        print(message, file=sys.stderr)
        with open(os.environ['JJ_FIXTURE_ERRORS'], 'a') as stream:
            stream.write(message + '\n')
        return 78


if __name__ == '__main__':
    raise SystemExit(main())
