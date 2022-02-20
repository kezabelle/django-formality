import sys
import unittest

from .test_query import *

if __name__ == "__main__":
    unittest.main(
        verbosity=2,
        catchbreak=True,
        tb_locals=True,
        failfast=False,
        buffer=False,
    )
