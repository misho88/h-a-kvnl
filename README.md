# Hierarchies/A/KVNL

Serialization for hierarchical data.

KVNL transmits data in one of these forms (newlines explicitly shown):

```
\n
key=value\n
key:size=value\n
```

Complete example:

```
my_string=hello world\n
```

A/KVNL adds optional annotations (simple metadata) to the key to indicate how
the value is to be interpreted, so the key takes on one of these forms:

```
key
key!annotation
```

Complete example:

```
my_int!I=7\n
```

H/A/KVNL adds an optional parent indicator to the annotation which specifies
that all subsequent keys until an empty line are its children. Characters after
this indicator specify a prefix that all children are expected to have (it can
be empty). The annotation thus takes on one of these forms:

```
annotation
annotations>
annotations>prefix
```

Complete example:

```
my_map!M>--=
--my_int!I=0
--my_list!L>--=
----!I=1
----!I=2
----!I=3

--my_float!F=4.0

```

Note that it is the empty line which indicates that there are no more children
and the prefix is only for readability in use cases where it matters. In
general, there is no issue with parent lines having values, but it doesn't
make much sense for maps and lists.
