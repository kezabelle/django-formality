django-formality
================

:author: Keryn Knight
:version: 0.1.0

If `Django`_ had support for parsing nested query-string and form-encoded data,
**and** the existing Forms API supported nested data, what would that look like,
and how much of a RESTy API could be built on such?

Brief
-----

Currently, this is *just* a parser capable of dumping structured query-string data in the form of::

    a[][item]=4&a[][item]=5&a[][item]=6

into a data-structure like::

    {'a': [{'item': 4}, {'item': 5}, {'item': 6}]}

It mostly tries to conform sensibly(ish) to `Rack`_ and `jQuery-BBQ`_ (and is in fact a semi-transliteration of the latter) but skirts certain edge cases I'm not brainy
enough to solve ... That basically means I'll throw an exception for *"malformed"* data.

Eventually, I've got plans for a bunch more. But this
is absolutely currently just an experiment in how far I'll
be able to take things

Goals
-----

An optimistic list of the things I'd like this to achieve, regardless of if I currently know how. Off the top of my head:

- Nested structure support for normal web forms & query strings, like `PHP`_, `Rack`_ and `jQuery-BBQ`_ have.

  - circuit-breaking of those nested values if they surpass a given limit
    (following e.g. Django's `DATA_UPLOAD_MAX_NUMBER_FIELDS`_)

- The ability to use the Forms API to describe nested data,
  for both input parsing and output.
- Flexible parsing and content-negotiation based on those Forms.
- `OpenAPI`_ generation from the very same Forms, so I can have nice `Swagger UI`_
  or `ReDoc`_ output.

  - Ideally, I want the ability to do this for *anything* I can detect as being
    a form-based view.

.. _Django: https://www.djangoproject.com/
.. _jQuery-BBQ: https://benalman.com/projects/jquery-bbq-plugin/
.. _PHP: https://www.php.net/manual/en/function.parse-str.php
.. _Rack: https://rack.github.io/
.. _DATA_UPLOAD_MAX_NUMBER_FIELDS: https://docs.djangoproject.com/en/4.0/ref/settings/
.. _OpenAPI: https://swagger.io/
.. _Swagger UI: https://swagger.io/tools/swagger-ui/
.. _ReDoc: https://github.com/Redocly/redoc
