class DecodingError(Exception):
    pass


class HierarchicalValue:
    def __init__(self, annotation, value, children):
        self.annotation, self.value, self.children = annotation, value, children

    def __iter__(self):
        yield self.annotation
        yield self.value
        yield self.children

    def __repr__(self):
        return f'{type(self).__name__}({repr(self.annotation)}, {repr(self.value)}, {repr(self.children)})'


class HierarchicalValueTuple(HierarchicalValue):
    def __init__(self, annotation, value, children):
        super().__init__(annotation, value, tuple(children))


def raise_decoding_error(annotation, value, stream):
    raise DecodingError(f'unrecognized annotation: {annotation}')


def ensure_empty_key(key, value):
    if key:
        raise DecodingError(f'{key=} is supposed to be empty')
    return value


def decode_map(value, stream):
    if value:
        raise DecodingError(f'{value=} is supposed to be empty')
    return dict(stream)


def decode_list(value, stream):
    if value:
        raise DecodingError(f'{value=} is supposed to be empty')
    return list(ensure_empty_key(key, value) for key, value in stream)


def encode_map(value, children):
    if value:
        raise DecodingError(f'{value=} is supposed to be empty')
    for key, value in children.items():
        if not isinstance(key, str):
            raise ValueError(f'{key=} is supposed to be a str, not {type(key)}')
        yield key, value


def encode_list(value, children):
    if value:
        raise DecodingError(f'{value=} is supposed to be empty')
    for value in children:
        yield '', value


DECODERS = { ('Map', 'M'): decode_map, ('List', 'L'): decode_list }
ENCODERS = { ('Map', 'M'): encode_map, ('List', 'L'): encode_list }
TYPES = { dict: 'M', list: 'L' }


def read_single(stream, decoders=DECODERS, default=raise_decoding_error, prefix=''):
    r''' read a single line and its children


    Expected behavior:

    No hierarchy:
    >>> next(read_single([ ('key', ('annotation', b'value')) ]))
    ('key', ('annotation', b'value'))
    >>> next(read_single([ ('key', b'value') ]))
    ('key', b'value')

    Unknown hierarchy:
    >>> next(read_single([ ('key', ('annotation>', b'value')), ('k1', b'v1'), '\n' ], default=None))
    ('key', HierarchicalValueTuple('annotation', b'value', (('k1', b'v1'),)))

    Map:
    >>> next(read_single([ ('key', ('Map>', b'')), ('k1', b'v1'), ('k2', b'v2'), '\n' ]))
    ('key', {'k1': b'v1', 'k2': b'v2'})
    >>> next(read_single([ ('key', ('M>', b'')), ('k1', b'v1'), ('k2', b'v2'), '\n' ]))
    ('key', {'k1': b'v1', 'k2': b'v2'})

    List:
    >>> next(read_single([ ('key', ('List>', b'')), ('', b'v1'), ('', b'v2'), '\n' ]))
    ('key', [b'v1', b'v2'])
    >>> next(read_single([ ('key', ('L>', b'')), ('', b'v1'), ('', b'v2'), '\n' ]))
    ('key', [b'v1', b'v2'])
    '''
    stream = iter(stream)

    for line in stream:
        if line is None:
            yield
            continue

        if line == '\n':
            yield line
            return

        key, value = line

        if not key.startswith(prefix):
            raise DecodingError(f'key {repr(key)} is supposed to start with {repr(prefix)}')
        key = key.removeprefix(prefix)

        orig_value = value
        if isinstance(value, tuple):
            annotation, value = value
        else:
            annotation = getattr(value, 'annotation', None)
            value = getattr(value, 'value', value)

        if annotation is None or '>' not in annotation:
            yield key, orig_value
            return

        annotation, next_prefix = annotation.split('>', maxsplit=1)

        children = read(stream, decoders, default, prefix + next_prefix)
        if decoders is None:
            yield key, HierarchicalValue(annotation, value, children)
            return

        for annotations, decode in decoders.items():
            if annotation in annotations:
                yield key, decode(value, children)
                return

        if default is None:
            default = HierarchicalValueTuple

        yield key, default(annotation, value, children)
        return
    raise EOFError


def read(stream, decoders=DECODERS, default=raise_decoding_error, prefix=''):
    while True:
        for line in read_single(stream, decoders, default, prefix):
            if line == '\n':
                return
            yield line
    raise EOFError


def write_single(key_and_value, encoders=ENCODERS, default=None, types=TYPES, prefix='', prefixes=()):
    r"""write a single line (and all of its children)

    key_and_value: None, '\n' or a key-value tuple
    encoders: dictionary of encoders (see ENCODERS for structure)

    Expected behavior:

    No hierarchy (does more or less nothing):
    >>> next(write_single(('key', ('annotation', b'value'))))
    ('key', ('annotation>', b'value'))
    >>> next(write_single(('key', b'value')))
    ('key', b'value')

    Unknown hierarchy:
    >>> list(write_single(('key', HierarchicalValueTuple('annotation', b'value', (('k1', b'v1'),)))))
    [('key', ('annotation>', b'value')), ('k1', b'v1'), '\n']

    Map:
    >>> list(write_single(('key', {'k1': b'v1', 'k2': b'v2'})))
    [('key', ('M>', b'')), ('k1', b'v1'), ('k2', b'v2'), '\n']

    List:
    >>> list(write_single(('key', [b'v1', b'v2'])))
    [('key', ('L>', b'')), ('', b'v1'), ('', b'v2'), '\n']
    """
    if encoders is None:
        encoders = {}

    if types is None:
        types = {}

    if key_and_value in (None, '\n'):
        yield key_and_value
        return

    key, value = key_and_value

    if isinstance(value, HierarchicalValue):
        annotation, value, children = value
    elif isinstance(value, tuple):
        try:
            annotation, value, children = value
        except ValueError:
            annotation, value = value
            children = None
    else:
        annotation = getattr(value, 'annotation', None)
        children = getattr(value, 'children', None)
        value = getattr(value, 'value', value)

    key = f'{"".join(prefixes)}{key}'

    if annotation is None:
        for t, a in types.items():
            if isinstance(value, t):
                annotation, value, children = a, b'', value
                break

    if annotation is None:
        if children is not None:
            raise DecodingError(f'cannot have children without annotation')
        yield key, value
        return

    full_annotation = f'{annotation}>{prefix}'

    yield key, (full_annotation, value)

    for annotations, encode in encoders.items():
        if annotation in annotations:
            yield from write(encode(value, children), encoders, default, types, prefix, prefixes + (prefix,))
            return

    if default is None:
        yield from write(children, encoders, default, types, prefix, prefixes + (prefix,))
        return

    yield from write(default(value, children), encoders, default, types, prefix, prefixes + (prefix,))


def write(lines, encoders=ENCODERS, default=None, types=TYPES, prefix='', prefixes=()):
    for line in lines:
        yield from write_single(line, encoders, default, types, prefix, prefixes)
    yield '\n'


if __name__ == '__main__':
    from doctest import testmod
    testmod()
