# SPDX-License-Identifier: GPL-3.0-or-later
"""C07 result staging; snapshots are limited to the active private text object."""
from contextlib import contextmanager
from copy import deepcopy
from functools import wraps

import formula
from .events import TeachingOperationBatch

TEXT_EVENTS = ('text.changed', 'text.edit_finished', 'formula.inserted',
               'formula.cursor_moved', 'symbols.opened', 'text.formatted')


@contextmanager
def text_action(panel):
    active = getattr(panel, '_teaching_document_batch', None)
    if active is not None:
        yield active
        return
    bus = getattr(panel, 'teaching_events', None)
    if bus is None:
        yield None
        return
    batch = TeachingOperationBatch(bus, TEXT_EVENTS)
    panel._teaching_document_batch = batch
    try:
        yield batch
        batch.flush()
    finally:
        panel._teaching_document_batch = None
        batch.close()


def _has_content(nodes):
    return any(node['k'] != 't' or str(node.get('v', '')).strip() for node in nodes)


def _counts(nodes):
    characters = structures = 0
    complete = True
    for node in nodes:
        kind = node['k']
        if kind == 't':
            characters += len(node.get('v', ''))
            continue
        structures += 1
        for key in formula.SLOTS[kind]:
            child = node[key]
            chars, count, filled = _counts(child)
            characters += chars
            structures += count
            complete = complete and _has_content(child) and filled
    return characters, structures, complete


def same_original(canvas, item_id):
    original = getattr(canvas.panel, '_teaching_text_original_id', None)
    return original is None or str(original) == str(item_id)


def structure_signature(nodes):
    from collections import Counter
    counts = Counter()
    def visit(items):
        for node in items:
            if node['k'] != 't':
                counts[node['k']] += 1
                for slot in formula.SLOTS[node['k']]:
                    visit(node[slot])
    visit(nodes or [])
    return ','.join(kind+':'+str(counts[kind]) for kind in sorted(counts))


def symbols_retained(canvas):
    symbol_id = getattr(canvas.panel, '_teaching_symbol_original_id', None)
    if symbol_id is None:
        return True
    item = next((item for item in canvas.text_items if str(item['id']) == symbol_id), None)
    return item is not None and all(symbol in str(item.get('text', '')) for symbol in ('α', '±', '∈', '∫'))


def content_counts(item):
    tree = item.get('formula')
    return _counts(tree) if tree is not None else (len(str(item.get('text', ''))), 0, True)


def text_snapshot(canvas):
    item = canvas.editing_text_item()
    if item is None:
        return None
    limit = canvas.caret_limit(item)
    path = tuple(canvas.editing_slot or ())
    tree = item.get('formula')
    parent = 'plain' if tree is None else 'root'
    slot = parent
    if path and tree is not None:
        nodes = tree
        for index, key in zip(path[::2], path[1::2]):
            node = nodes[index]
            parent, slot = node['k'], key
            nodes = node[key]
    characters, structures, complete = content_counts(item)
    return {'id': item['id'], 'text': str(item.get('text', '')),
            'formula': deepcopy(tree), 'path': path, 'parent_kind': parent,
            'slot': slot, 'depth': len(path) // 2, 'offset': canvas.caret_offset,
            'limit': limit, 'reedit_prefix': getattr(canvas.panel, '_teaching_reedit_prefix', None),
            'characters': characters,
            'structures': structures, 'complete': complete}


def emit_change(batch, canvas, before, action):
    operation = batch.operation('text.changed') if batch is not None else None
    if operation is None or before is None:
        return
    item = canvas.editing_text_item()
    if (item is None or item['id'] != before['id'] or
            (item.get('text', '') == before['text'] and item.get('formula') == before['formula'])):
        return
    characters, structures, complete = content_counts(item)
    delta = characters - before['characters']
    if action == 'input':
        old, new = before['text'], str(item.get('text', ''))
        if delta > 0:
            offset = before['offset']
            inserted_only = new[:offset] == old[:offset] and new[offset+delta:] == old[offset:]
            action = ('newline' if new.count('\n') > old.count('\n') else 'insert') if inserted_only else 'replace'
        elif delta < 0:
            action = 'backspace' if canvas.caret_offset < before['offset'] else 'delete'
        else:
            action = 'replace'
    elif action == 'insert' and item.get('formula') is None:
        if str(item.get('text', '')).count('\n') > before['text'].count('\n'):
            action = 'newline'
    batch.emit_result(operation, 'text.changed', 'success', {
        'action': action, 'characters': characters, 'inserted': max(0, delta),
        'removed': max(0, -delta), 'at_end': before['offset'] >= before['limit'],
        'slot': before['slot'], 'parent_kind': before['parent_kind'],
        'offset': before['offset'], 'middle': 0 < before['offset'] < before['limit'],
        'appended_only': (before['offset'] == before['limit']
                          and before['reedit_prefix'] is not None
                          and str(item.get('text','')).startswith(before['reedit_prefix'])
                          and str(item.get('text','')).startswith(before['text'])
                          and len(str(item.get('text',''))) > len(before['text'])),
        'depth': before['depth'], 'structures': structures,
        'complete': complete, 'item_id': str(item['id']),
        'same_original': same_original(canvas, item['id']),
        'nonempty': not canvas.text_item_is_empty(item),
        'slot_filled': (_has_content(formula.get_slot(item['formula'], before['path']) or [])
                        if item.get('formula') is not None else bool(str(item.get('text', '')).strip())),
        'symbol': getattr(canvas.panel, '_teaching_symbol_entry', None)})


def teaching_text_change(action):
    def decorate(function):
        @wraps(function)
        def wrapped(canvas, *args, **kwargs):
            if getattr(canvas.panel, 'teaching_events', None) is None:
                return function(canvas, *args, **kwargs)
            with text_action(canvas.panel) as batch:
                before = text_snapshot(canvas) if batch.operation('text.changed') is not None else None
                result = function(canvas, *args, **kwargs)
                if result:
                    emit_change(batch, canvas, before, action)
                return result
        return wrapped
    return decorate


def teaching_input_change(function):
    @wraps(function)
    def wrapped(editor, *args, **kwargs):
        canvas = editor._canvas()
        if canvas is None or getattr(canvas.panel, 'teaching_events', None) is None:
            return function(editor, *args, **kwargs)
        with text_action(canvas.panel) as batch:
            before = text_snapshot(canvas) if batch.operation('text.changed') is not None else None
            result = function(editor, *args, **kwargs)
            emit_change(batch, canvas, before, 'input')
            return result
    return wrapped


def teaching_text_input_action(function):
    @wraps(function)
    def wrapped(editor, *args, **kwargs):
        canvas = editor._canvas()
        panel = canvas.panel if canvas is not None else None
        if getattr(panel, 'teaching_events', None) is None:
            return function(editor, *args, **kwargs)
        with text_action(panel):
            previous = getattr(panel, '_teaching_text_navigation', None)
            if panel is not None:
                from PyQt6.QtCore import Qt
                event = args[0] if args else None
                panel._teaching_text_navigation = ('end' if event is not None
                    and hasattr(event, 'key') and event.key() == Qt.Key.Key_End else None)
            try:
                return function(editor, *args, **kwargs)
            finally:
                if panel is not None:
                    panel._teaching_text_navigation = previous
    return wrapped


def teaching_text_panel_action(function):
    # Qt decides whether clicked(bool) supplies its argument from the callable's
    # real arity. Keep zero-argument slots zero-argument after decoration.
    if function.__code__.co_argcount == 1:
        @wraps(function)
        def wrapped(panel):
            with text_action(panel):
                return function(panel)
    else:
        @wraps(function)
        def wrapped(panel, value):
            with text_action(panel):
                return function(panel, value)
    return wrapped


def teaching_text_finish(function):
    @wraps(function)
    def wrapped(canvas, *args, **kwargs):
        if getattr(canvas.panel, 'teaching_events', None) is None:
            return function(canvas, *args, **kwargs)
        with text_action(canvas.panel) as batch:
            operation = batch.operation('text.edit_finished')
            before = text_snapshot(canvas) if operation is not None else None
            result = function(canvas, *args, **kwargs)
            if before is not None and canvas.editing_text_id is None:
                item = next((item for item in canvas.text_items if item['id'] == before['id']), None)
                retained = item is not None and not canvas.text_item_is_empty(item)
                counts = content_counts(item) if item is not None else (0, 0, False)
                batch.emit_result(operation, 'text.edit_finished', 'success', {
                    'retained': retained, 'characters': counts[0], 'structures': counts[1],
                    'complete': counts[2], 'item_id': str(before['id']),
                    'same_original': same_original(canvas, before['id']),
                    'structure_signature': structure_signature(item.get('formula')) if item is not None else '',
                    'symbols_retained': symbols_retained(canvas)})
            return result
    return wrapped


def teaching_formula_insert(function):
    @wraps(function)
    def wrapped(canvas, kind):
        if getattr(canvas.panel, 'teaching_events', None) is None:
            return function(canvas, kind)
        with text_action(canvas.panel) as batch:
            operation = batch.operation('formula.inserted')
            before = text_snapshot(canvas) if operation is not None else None
            result = function(canvas, kind)
            item = canvas.editing_text_item()
            if (result and before is not None and item is not None and item['id'] == before['id']
                    and kind in formula.SLOTS and kind != 't'
                    and content_counts(item)[1] == before['structures'] + 1):
                batch.emit_result(operation, 'formula.inserted', 'success', {
                    'kind': kind, 'parent_kind': before['parent_kind'], 'slot': before['slot'],
                    'depth': before['depth'], 'structures': before['structures'] + 1,
                    'item_id': str(item['id'])})
            return result
    return wrapped


def teaching_cursor_move(function):
    @wraps(function)
    def wrapped(canvas, *args, **kwargs):
        if getattr(canvas.panel, 'teaching_events', None) is None:
            return function(canvas, *args, **kwargs)
        with text_action(canvas.panel) as batch:
            operation = batch.operation('formula.cursor_moved')
            before = text_snapshot(canvas) if operation is not None else None
            result = function(canvas, *args, **kwargs)
            if result and before is not None and canvas.caret_offset != before['offset']:
                batch.emit_result(operation, 'formula.cursor_moved', 'success', {
                    'slot': before['slot'], 'parent_kind': before['parent_kind'],
                    'at_end': canvas.caret_offset == canvas.caret_limit(canvas.editing_text_item()),
                    'offset': canvas.caret_offset, 'depth': before['depth'],
                    'navigation': getattr(canvas.panel, '_teaching_text_navigation', None),
                    'item_id': str(before['id'])})
            return result
    return wrapped


def teaching_symbol_group(function):
    @wraps(function)
    def wrapped(panel, key):
        with text_action(panel) as batch:
            operation = batch.operation('symbols.opened') if batch is not None else None
            before = panel._open_symbol_group
            result = function(panel, key)
            if operation is not None and before != key and panel._open_symbol_group == key:
                batch.emit_result(operation, 'symbols.opened', 'success', {'group': key})
            return result
    return wrapped


def teaching_text_format(action):
    def decorate(function):
        @wraps(function)
        def wrapped(canvas, *args, **kwargs):
            if getattr(canvas.panel, 'teaching_events', None) is None:
                return function(canvas, *args, **kwargs)
            with text_action(canvas.panel) as batch:
                operation = batch.operation('text.formatted')
                before = {item['id']: (item['color'].name(), item['size'], item['width'])
                          for item in canvas.text_items if item['id'] in canvas.selected_ids} if operation is not None else {}
                result = function(canvas, *args, **kwargs)
                changed = [item for item in canvas.text_items if item['id'] in before and
                           (item['color'].name(), item['size'], item['width']) != before[item['id']]]
                if changed:
                    item = changed[0]
                    batch.emit_result(operation, 'text.formatted', 'success', {
                        'action': action, 'count': len(changed), 'size': item['size'],
                        'width': item['width'], 'item_id': str(item['id'])})
                return result
        return wrapped
    return decorate


def teaching_symbol_action(function):
    @wraps(function)
    def wrapped(panel, entry):
        with text_action(panel):
            previous = getattr(panel, '_teaching_symbol_entry', None)
            panel._teaching_symbol_entry = entry if isinstance(entry, str) and any(
                entry in formula.group_entries(key) for key in formula.group_keys()) else None
            try:
                return function(panel, entry)
            finally:
                panel._teaching_symbol_entry = previous
    return wrapped
