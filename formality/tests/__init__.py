import sys
import unittest

from .test_query import (
    TestLoadDjangoQueries,
    TestLoadJQueryBbqQueries,
    TestLoadRackQueries,
    TestLoadOdditiesAndMalformed,
    TestStrictlyUnhandledQueries,
    TestDumpQueries,
    TestRoundTripping,
    TestManyFields,
)

__all__ = [
    "TestLoadDjangoQueries",
    "TestLoadJQueryBbqQueries",
    "TestLoadRackQueries",
    "TestLoadOdditiesAndMalformed",
    "TestStrictlyUnhandledQueries",
    "TestDumpQueries",
    "TestRoundTripping",
    "TestManyFields",
]

if __name__ == "__main__":
    unittest.main(
        verbosity=2,
        catchbreak=True,
        tb_locals=True,
        failfast=False,
        buffer=False,
    )
