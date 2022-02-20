formality
=========

The package itself.

Contains the following functionality:

query
-----

The ``query`` module publishes ``loads(qs: str, ...)`` and
``dumps(data: dict, ...)`` for converting string nested data representations to dictionaries, and vice versa::

    >>> from formality import query
    >>> query.loads("a[][item]=4&a[][item]=5&a[][item]=true")
    {'a': [{'item': 4}, {'item': 5}, {'item': 6}]}
    >>> query.dumps({'a': [{'item': 4}, {'item': 5}, {'item': True}]})
    'a%5B0%5D%5Bitem%5D=4&a%5B1%5D%5Bitem%5D=5&a%5B2%5D%5Bitem%5D=6'

It supports traversing **N** levels of depth (``5`` by default) and **N** maximum fields (*including* those created via nesting, ``1000`` by default)

It automatically coerces values to JSON compatible versions when using ``dumps``, and converts those values back to their native Python equivalent on ``loads``

You can opt-out of that using ``coerce=False`` as a keyword-argument.

Test cases for this functionality are in ``tests/test_query.py``

.. TODO: cover the expected exceptions!
