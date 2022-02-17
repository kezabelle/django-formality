import sys
import unittest
import formality

try:
    from hypothesis import given, strategies as st, settings

    HAS_HYPOTHESIS = True
except ModuleNotFoundError:
    HAS_HYPOTHESIS = False


class TestDjangoQueries(unittest.TestCase):
    # These come from running the Django test suite and instrumenting
    # QueryDict.__init__ like so:
    # print(repr(original_qs), repr(query_string), repr(self.encoding), repr(dict(self)), sep=", ", end=",\n")
    # Where django produces only string *values*, with coercion we get proper
    # json compatible values, such that it should be treatable *as* json...
    # Note also that values which aren't _intended_ to be a list don't
    # become one.
    str_examples = (
        (
            "",
            "",
            "iso-8859-1",
            {},
        ),
        (
            "",
            "",
            "iso-8859-15",
            {},
        ),
        (
            "",
            "",
            "iso-8859-16",
            {},
        ),
        (
            "",
            "",
            "koi8-r",
            {},
        ),
        (
            "",
            "",
            "utf-16",
            {},
        ),
        (
            "",
            "",
            "utf-8",
            {},
        ),
        (
            "",
            "",
            "utf8",
            {},
        ),
        (
            "a=1&a=2",
            "a=1&a=2",
            "utf-8",
            {"a": [1, 2]},
        ),
        (
            "a=3&a=4",
            "a=3&a=4",
            "utf-8",
            {"a": [3, 4]},
        ),
        (
            "counter=0000000000000000000000",
            "counter=0000000000000000000000",
            "utf-8",
            {"counter": 0},
        ),
        (
            "is_superuser__exact=0&is_staff__exact=0",
            "is_superuser__exact=0&is_staff__exact=0",
            "utf-8",
            {"is_superuser__exact": 0, "is_staff__exact": 0},
        ),
        (
            "key1&key2&key3&key4=yep",
            "key1&key2&key3&key4=yep",
            "utf-8",
            {"key1": "", "key2": "", "key3": "", "key4": "yep"},
        ),
        (
            "key1&key2&key3",
            "key1&key2&key3",
            "utf-8",
            {"key1": "", "key2": "", "key3": ""},
        ),
        (
            "name=Yesterday&composers=J&composers=P",
            "name=Yesterday&composers=J&composers=P",
            "utf-8",
            {"name": "Yesterday", "composers": ["J", "P"]},
        ),
        (
            "next=/flatpage_root/sekrit/",
            "next=/flatpage_root/sekrit/",
            "utf-8",
            {"next": "/flatpage_root/sekrit/"},
        ),
    )
    bytes_examples = (
        (
            b"q='John Do'",
            "q='John Do'",
            "utf-8",
            {"q": "'John Do'"},
        ),
        (
            b"q='John Doe' John",
            "q='John Doe' John",
            "utf-8",
            {"q": "'John Doe' John"},
        ),
        (
            b"q='John Doe'",
            "q='John Doe'",
            "utf-8",
            {"q": "'John Doe'"},
        ),
        (
            b"q='John O'Hara'",
            "q='John O'Hara'",
            "utf-8",
            {"q": "'John O'Hara'"},
        ),
        (
            b"q='John O\\'Hara'",
            "q='John O\\'Hara'",
            "utf-8",
            {"q": "'John O\\'Hara'"},
        ),
        (
            b"a=1&a=2&a=3\r\n",
            "a=1&a=2&a=3\r\n",
            "utf-8",
            {"a": [1, 2, "3\r\n"]},
        ),
        # This doesn't coerce to a Python boolean because it wouldn't convert
        # via JSON.
        (
            b"contributors__isnull=True",
            "contributors__isnull=True",
            "utf-8",
            {"contributors__isnull": "True"},
        ),
        (
            b"counter=0000000000000000000000",
            "counter=0000000000000000000000",
            "utf-8",
            {"counter": 0},
        ),
        (
            b"o=-1",
            "o=-1",
            "utf-8",
            {"o": -1},
        ),
        (
            b"password__startswith=sha1$",
            "password__startswith=sha1$",
            "utf-8",
            {"password__startswith": "sha1$"},
        ),
    )
    # These mostly come from Django too, but not all of them.
    decoding_examples = (
        (
            "next=/test_admin/admin2/&next2=test",
            "next=/test_admin/admin2/",
            "utf-8",
            {"next": "/test_admin/admin2/", "next2": "test"},
        ),
        (
            "cur=%A4",
            "cur=%A4",
            "iso-8859-15",
            {"cur": "€"},
        ),
        (
            "cur%A4=1",
            "cur%A4=1",
            "iso-8859-15",
            {'cur€': 1},
        ),
        (
            b"author__email=alfred%40example.com",
            "author__email=alfred%40example.com",
            "utf-8",
            {"author__email": "alfred@example.com"},
        ),
        (
            b"color__id__exact=StringNotInteger%21",
            "color__id__exact=StringNotInteger%21",
            "utf-8",
            {"color__id__exact": "StringNotInteger!"},
        ),
        (
            b"content_type=application%2Factivity%2Bjson%3B+charset%3Dutf-8",
            "content_type=application%2Factivity%2Bjson%3B+charset%3Dutf-8",
            "utf-8",
            {"content_type": "application/activity+json; charset=utf-8"},
        ),
        (
            b"decade__in=the+90s",
            "decade__in=the+90s",
            "utf-8",
            {"decade__in": "the 90s"},
        ),
        (
            b"key=Espa%C3%B1a",
            "key=Espa%C3%B1a",
            "utf-8",
            {"key": "España"},
        ),
        (
            b"myfield=%2Ftest_admin%2Fadmin%2Fsecure-view2%2F",
            "myfield=%2Ftest_admin%2Fadmin%2Fsecure-view2%2F",
            "utf-8",
            {"myfield": "/test_admin/admin/secure-view2/"},
        ),
        # Encoding issues tested internally in Django
        (
            b"name=Hello G\xc3\xbcnter",
            "name=Hello Günter",
            "utf-8",
            {"name": "Hello Günter"},
        ),
        (
            b"name=Hello G\xc3\xbcnter",
            "name=Hello GĂŒnter",
            "iso-8859-16",
            {"name": "Hello GĂŒnter"},
        ),
        (
            b"name=Hello%20G%C3%BCnter",
            "name=Hello%20G%C3%BCnter",
            "iso-8859-16",
            {"name": "Hello GĂŒnter"},
        ),
        (
            b"name=Hello%20G%C3%BCnter",
            "name=Hello%20G%C3%BCnter",
            "utf-8",
            {"name": "Hello Günter"},
        ),
        (
            b"name=My+Action",
            "name=My+Action",
            "utf-8",
            {"name": "My Action"},
        ),
        (
            b"name=My+Section",
            "name=My+Section",
            "utf-8",
            {"name": "My Section"},
        ),
        (
            b"name+name=MyAction",
            "name+name=MyAction",
            "utf-8",
            {'name name': 'MyAction'},
        ),
        (
            b"abc%20def=1",
            "name+name=MyAction",
            "utf-8",
            {'abc def': 1},
        ),
        (
            b"next=/url%2520with%2520spaces/",
            "next=/url%2520with%2520spaces/",
            "utf-8",
            {"next": "/url%20with%20spaces/"},
        ),
        (
            b"next=/view%3Fparam%3Dftp%3A//example.com",
            "next=/view%3Fparam%3Dftp%3A//example.com",
            "utf-8",
            {"next": "/view?param=ftp://example.com"},
        ),
        (
            b"next=javascript%3Aalert%28%22XSS%22%29",
            "next=javascript%3Aalert%28%22XSS%22%29",
            "utf-8",
            {"next": 'javascript:alert("XSS")'},
        ),
        (
            b"q=some%00thing",
            "q=some%00thing",
            "utf-8",
            {"q": "some\x00thing"},
        ),
        (
            b"url=http%3A%2F%2Flocalhost%3A55698",
            "url=http%3A%2F%2Flocalhost%3A55698",
            "utf-8",
            {"url": "http://localhost:55698"},
        ),
        (
            b"var=%C3%B2",
            "var=%C3%B2",
            "utf-8",
            {"var": "ò"},
        ),
        (
            b"var=1\xef\xbf\xbd",
            "var=1�",
            "utf-8",
            {"var": "1�"},
        ),
        (
            b"want=caf%C3%A9",
            "want=caf%C3%A9",
            "utf-8",
            {"want": "café"},
        ),
        (
            b"want=caf%E9",
            "want=caf%E9",
            "utf-8",
            {"want": "caf�"},
        ),
        (
            b"want=caf\xc3\xa9",
            "want=café",
            "utf-8",
            {"want": "café"},
        ),
        (
            b"want=caf\xe9",
            "want=café",
            "utf-8",
            {"want": "café"},
        ),
        (
            b"year=2002",
            "year=2002",
            "utf-8",
            {"year": 2002},
        ),
    )

    def test_str(self):
        for qs, _, encoding, result in self.str_examples:
            with self.subTest(data=qs, encoding=encoding):
                self.assertEqual(formality.query.loads(qs, coerce=True), result)

    def test_bytes(self):
        for qs, _, encoding, result in self.bytes_examples:
            with self.subTest(data=qs, encoding=encoding):
                self.assertEqual(formality.query.loads(qs, coerce=True), result)

    def test_urldecoding(self):
        for qs, _, encoding, result in self.decoding_examples:
            with self.subTest(data=qs, encoding=encoding):
                self.assertEqual(formality.query.loads(qs, coerce=True), result)


class TestJQueryBbqQueries(unittest.TestCase):
    pass


class TestMalformed(unittest.TestCase):
    pass


if HAS_HYPOTHESIS:

    class TestFuzzLoads(unittest.TestCase):
        @given(qs=st.text(), coerce=st.booleans())
        @settings(max_examples=1000)
        def test_fuzz_loads(self, qs, coerce):
            self.assertIsInstance(formality.query.loads(qs=qs, coerce=coerce), dict)


if __name__ == "__main__":
    unittest.main(
        module=sys.modules[__name__],
        verbosity=2,
        catchbreak=True,
        tb_locals=True,
        failfast=False,
        buffer=False,
    )
