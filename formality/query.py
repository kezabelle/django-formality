import string
import json.decoder
import types
from urllib.parse import unquote, quote_plus

import json.scanner
from typing import Dict, Union, Text, Any, List, Tuple, Iterator
from django.core.exceptions import SuspiciousOperation, TooManyFieldsSent


class MalformedData(SuspiciousOperation):
    """
    When encountering fields like a[[[] or b[]]] just drop them immediately
    and loudly.
    """

    __slots__ = ("args", "message", "key")

    def __init__(self, *args):
        super().__init__(*args)
        self.key = args[0]

    def __str__(self):
        return f"Invalid nesting characters in key {self.key!r}"


COERCE_LOAD_CONSTANTS = types.MappingProxyType(
    {
        "true": True,
        "false": False,
        "null": None,
        "NaN": json.decoder.NaN,
        "Infinity": json.decoder.PosInf,
        "-Infinity": json.decoder.NegInf,
    }
)
COERCE_DUMP_CONSTANTS = types.MappingProxyType(
    {
        True: "true",
        False: "false",
        None: "null",
        json.decoder.PosInf: "Infinity",
        json.decoder.NegInf: "-Infinity",
        # Can't put float('nan') -> NaN in here because it doesn't compute as
        # the same: float('nan') == float('nan') is False
    }
)


def loads(
    qs: Union[str, bytes],
    *,
    encoding: str = "utf-8",
    coerce: bool = True,
    max_num_fields: int = 1000,
    max_depth: int = 5,
) -> Dict[
    Union[str, int],
    Union[Dict[Union[str, int], Any], List[Any], int, float, bool, None],
]:
    """
    Parse a string or bytestring into a nested dictionary. This handles
    converting a query string (GET) or "application/x-www-form-urlencoded" form (POST)
    in the form a[][test][]=1 into something like:
    {"a": [{"test": [1]}]}

    Before parsing begins, the string is checked for "&" separators, and if
    there are more than `max_num_fields` it will throw `TooManyFieldsSent` and
    stop executing.

    Accepts a `max_depth` parameter which controls how many levels of nesting
    a single key can go. This allows avoiding inflating deeply nested lists designed
    to spin the hamster wheels of your CPU (e.g. a[][][][][][][][][][][]=1 can
    be prevented from generating {'a': [[[[[[[[[[[1]]]]]]]]]]]} into the data)

    By default, coercing to Python-specific types a-la JSON is enabled, so
    that the request may pass around a consistent representation of data.

    References:
        https://benalman.com/projects/jquery-bbq-plugin/
        https://benalman.com/code/projects/jquery-bbq/examples/deparam/
    """
    obj: Dict[
        Union[str, int],
        Union[Dict[Union[str, int], Any], List[Any], int, float, bool, None],
    ] = {}
    # Fast path, empty query-string.
    if not qs:
        return obj

    if isinstance(qs, bytes):
        # query_string normally contains URL-encoded data, a subset of ASCII.
        try:
            qs = qs.decode(encoding)
        except UnicodeDecodeError:
            # ... but some user agents are misbehaving :-(
            qs = qs.decode("iso-8859-1")

    if max_num_fields:
        num_fields = 1 + qs.count("&")
        if max_num_fields < num_fields:
            raise TooManyFieldsSent(
                f"The number of GET/POST parameters exceeded {max_num_fields!r}; received {num_fields!r} parameters"
            )

    seen_fields = 0
    # Iterate over all name=value pairs.
    for part in qs.split("&"):
        key, sep, val = part.partition("=")
        if not key:
            continue
        obj, seen_fields = _load_key_value(
            key,
            val,
            obj=obj,
            encoding=encoding,
            coerce=coerce,
            max_num_fields=max_num_fields,
            max_depth=max_depth,
            seen_fields=seen_fields,
        )
    return obj


def load(
    pairs: Iterator[Union[bytes, str]],
    *,
    encoding: str = "utf-8",
    coerce: bool = True,
    max_num_fields: int = 1000,
    max_depth: int = 5,
):
    """
    Takes an iterator or iterable of 2-tuples as input in the form (key, value),
    and produces a nested dictionary, mimicing the behaviour of `loads` which
    handles query strings (GET) and `application/x-www-form-urlencoded` (POST) data.

    The value given as pairs[1] may be a single scalar value, or an array of
    individual values, as provided by a MultiValueDict/QueryDict in Django, where
    the key `a` may be referenced as .POST["a"] to get the single value, or
    .POST.getlist("a") which would return [x, y, z]. Each individual value is
    parsed as of it had been given as a=1&a=2&a=3 for consistency.

    Unlike `loads`, this parser throws `TooManyFieldsSent` once it has seen
    more than `max_num_fields`, rather than ahead-of-time based on counting
    separators; this is because it can receive an iterator of unknown length,
    so has to track as it goes.

    By default, coercing to Python-specific types a-la JSON is enabled, so
    that the request may pass around a consistent representation of data.
    """
    obj: Dict[
        Union[str, int],
        Union[Dict[Union[str, int], Any], List[Any], int, float, bool, None],
    ] = {}
    if not pairs:
        return obj

    seen_fields = 0
    for num_fields, pair in enumerate(pairs, start=1):
        key, val = pair
        # Check as we go for overflowing the expected number of fields.
        # We can't call len() on the pairs ahead of time because we may be getting
        # a `dict_itemiterator` or something as input.
        if max_num_fields < num_fields:
            raise TooManyFieldsSent(
                f"The number of GET/POST parameters exceeded {max_num_fields!r}; received {num_fields!r} parameters"
            )
        if not key:
            continue
        if isinstance(val, list):
            if len(val) > 1:
                for i, valpart in enumerate(val, start=0):

                    # If it's a list but the incoming key doesn't declare it as such,
                    # fix it, so that a[test]: [1, 2] becomes a[test][]: [1, 2] and
                    # stops the 2 overwriting the 1...
                    usekey = key
                    if key[-2:] != "[]":
                        last_open, last_close = key.rfind("["), key.rfind("]")
                        if last_open and last_close:
                            subcomponent = key[last_open + 1 : last_close]
                            for chr in subcomponent:
                                if chr in string.digits:
                                    continue
                                else:
                                    usekey = f"{key}[{i}]"
                                    break
                            else:
                                # All digits, doesn't need a [] adding..
                                pass

                    obj, seen_fields = _load_key_value(
                        usekey,
                        valpart,
                        obj=obj,
                        encoding=encoding,
                        coerce=coerce,
                        max_num_fields=max_num_fields,
                        max_depth=max_depth,
                        seen_fields=seen_fields,
                    )
            elif val:

                # If it's a list but the incoming key doesn't declare it as such,
                # fix it, so that a[test]: [1, 2] becomes a[test][]: [1, 2] and
                # stops the 2 overwriting the 1...
                # if key[-2:] != "[]":
                #     last_open, last_close = key.rfind('['), key.rfind(']')
                #     if last_open and last_close:
                #         subcomponent = key[last_open + 1:last_close]
                #         for chr in subcomponent:
                #             if chr in string.digits:
                #                 continue
                #             else:
                #                 key = f"{key}[]"
                #                 break
                #         else:
                #             # All digits, doesn't need a [] adding..
                #             pass

                obj, seen_fields = _load_key_value(
                    key,
                    val[0],
                    obj=obj,
                    encoding=encoding,
                    coerce=coerce,
                    max_num_fields=max_num_fields,
                    max_depth=max_depth,
                    seen_fields=seen_fields,
                )
        else:
            obj, seen_fields = _load_key_value(
                key,
                val,
                obj=obj,
                encoding=encoding,
                coerce=coerce,
                max_num_fields=max_num_fields,
                max_depth=max_depth,
                seen_fields=seen_fields,
            )
    return obj


def _load_key_value(
    key: str,
    val: Any,
    obj,
    *,
    encoding: str = "utf-8",
    coerce: bool = True,
    max_num_fields: int = 1000,
    max_depth: int = 5,
    seen_fields: int = 0,
):
    """
    Convert a single key + value into the nested format, based on the representation
    of the key; e.g. a[][abc] might become {"a": [{"abc": ...}]}

    If the number of nested parts in a key is more than `max_depth` this key
    will throw `TooManyFieldsSent`.

    If `seen_fields` has been incremented to more than `max_num_fields` either
    within this function or by a caller, this key will throw `TooManyFieldsSent`.

    By default, coercing of `val` to a Python-specific type a-la JSON is enabled, so
    that the request may pass around a consistent representation of data.

    References:
        https://benalman.com/projects/jquery-bbq-plugin/
        https://benalman.com/code/projects/jquery-bbq/examples/deparam/
        https://github.com/cowboy/jquery-bbq/blob/8e0064ba68a34bcd805e15499cb45de3f4cc398d/jquery.ba-bbq.js#L444-L556
    """
    # translate key as per urllib.parse.parse_qsl
    key = unquote(key.replace("+", " "), encoding)
    # Skip empty keys (e.g. "&foo=1&&bar=2")
    if not key:
        return obj, seen_fields
    # Just drop processing immediately if the key looks invalid. Yes there
    # are false positives for if someone tries to do a[[[] expecting a key
    # of "[[" or something, but that may not even be what they're expecting...
    if "[[" in key or "]]" in key or key[0:2] == "[]":
        raise MalformedData(key)
        # translate value as per urllib.parse.parse_qsl
    if isinstance(val, str):
        val = unquote(val.replace("+", " "), encoding)
    cur = obj
    # Check whether inflating this key would push us over our expected
    # maximum depth BEFORE doing the inflate, to avoid a[][][][][][][][]...
    # from over-committing memory usage.
    # We use a depth of 6 to allow for 5 levels of nesting including the
    # root key.
    # Find the total first-split, and then within what would be keys[0] thereafter
    # find the count of second-splits (see correctly balanced, below).
    # That should give us the same number (??) as we'd see if we did the
    # splitting and then checked, which would potentially balloon memory
    # just to then error.
    total_depth = key.count("][") + key[0 : key.find("]")].count("[")
    if max_depth < total_depth:
        raise TooManyFieldsSent(
            f"The depth of nested GET/POST parameters exceeded {max_depth!r}; received {total_depth!r} nested parameters"
        )
    # If key is more complex than 'foo', like 'a[]' or 'a[b][c]', split it
    # into its component parts.
    keys = key.split("][")
    keys_last = len(keys) - 1

    # If the first keys part contains [ and the last ends with ], then []
    # are correctly balanced.
    if "[" in keys[0] and keys[keys_last][-1] == "]":
        # Remove the trailing ] from the last keys part.
        keys[keys_last] = keys[keys_last][:-1]
        # Split first keys part into two parts on the [ and add them back onto
        # the beginning of the keys array.
        keys = [*keys.pop(0).split("["), *keys]
        keys_last = len(keys) - 1
        seen_fields += keys_last + 1
    else:
        keys_last = 0
        # Always add 1, even if it's a simple key.
        seen_fields += 1

    # Prevent any single (nested) key from continuing if it would blow over the limit
    # This doesn't preclude spamming in a single a[][][][][][][][][][][][]...
    # and inflating too many items, but I'll handle that via depth checks.
    if max_num_fields < seen_fields:
        raise TooManyFieldsSent(
            f"The number of GET/POST parameters (including nesting) exceeded {max_num_fields!r}; received {seen_fields!r} (possibly nested) parameters"
        )

    if coerce and val:
        if val in COERCE_LOAD_CONSTANTS:
            val = COERCE_LOAD_CONSTANTS[val]
        elif isinstance(val, str):
            # using .match would seem to catch "1�" and "3\r\n"
            # but using .fullmatch doesn't catch '0000000000000000000000'
            match_number = json.scanner.NUMBER_RE.fullmatch(val)
            if match_number is not None:
                integer, frac, exp = match_number.groups()
                if frac or exp:
                    val = float(integer + (frac or "") + (exp or ""))
                else:
                    val = int(integer)
            elif all(chr in string.digits for chr in val):
                if val[0] == "0":
                    # don't convert, because it's a special string
                    # like 'account': '003532663'
                    pass
                else:
                    val = int(val)

    # Complex key, build deep object structure based on a few rules:
    # The 'cur' pointer starts at the object top-level.
    #
    #   * [] = array push (n is set to array length), [n] = array if n is
    #     numeric, otherwise object.
    #
    #   * If at the last keys part, set the value.
    #
    #   * For each keys part, if the current level is undefined create an
    #     object or array based on the type of the next keys part.
    #
    #   * Move the 'cur' pointer to the next level.
    #
    #   * Rinse & repeat.
    if keys_last:
        for i, key in enumerate(keys):
            # test for '' the slightly quicker way (12ns faster), '' means
            # array append, anything else, including '0', '1', 'abc'
            # means array OR object add at given index/key.
            if not key:
                key = len(cur)
            # Does it look like an array key? If so, make it one.
            elif isinstance(key, str):
                # Walk each character, and only convert to an int if all
                # of them are numbery. On reasonable length strings, this is
                # faster (on balance) than try: int() except:... which takes
                # 1µs for "9things" vs 150ns for this method; where "9" takes
                # 250ns this way and 140ns using try/except.
                for chr in key:
                    if chr in string.digits:
                        continue
                    else:
                        break
                else:
                    key = int(key)
                    # TODO: either here or in the while loop to backfill an array,
                    #   ensure that adding N items also increases the seen_fields?
                    if max_num_fields < key:
                        raise TooManyFieldsSent(
                            f"The index [{key}] of parameter exceeded {max_num_fields!r} total allowed parameters"
                        )

            # fed https://github.com/AceMetrix/jquery-deparam/blob/81428b3939c4cbe488202b5fa823ad661d64fb49/jquery-deparam.js#L83-L86
            # to https://opengg.github.io/babel-plugin-transform-ternary-to-if-else/
            # Need the value slightly ahead-of-time to backfill incomplete
            # arrays with the same type...
            if i < keys_last:
                try:
                    bit = cur[key]
                except (IndexError, KeyError):
                    if keys[i + 1]:
                        # It's only a dictionary if the next key has non
                        # numeric characters in it. See above for performance
                        # details for doing it this way.
                        for chr in keys[i + 1]:
                            if chr in string.digits:
                                continue
                            else:
                                bit = {}
                                break
                        else:
                            bit = []
                    else:
                        bit = []
            else:
                bit = val

            if isinstance(cur, list):
                bit_type = type(bit)
                # Have to fill up the list if the key isn't 0, because
                # Python is less lax and it'd be an:
                # IndexError: list assignment index out of range
                while len(cur) <= key:
                    # We try to fill up with the SAME type (e.g. str = '',
                    # int = 0, list = [] ...) by preference, but if the __new__
                    # or __init__ REQUIRES arguments, we won't know them so
                    # insert a hole of the singleton None...
                    # unfortunately this means any parser for this value has to
                    # be None aware? Though I think that's mostly for FILES
                    # where InMemoryUploadedFile doesn't support blank instantiation.
                    try:
                        empty_val = bit_type()
                    except TypeError:
                        empty_val = None
                    cur.append(empty_val)
            cur[key] = cur = bit

    # Simple key, even simpler rules, since only scalars and shallow
    # arrays are allowed.
    elif isinstance(obj, dict) and isinstance(obj.get(key), list):
        # If we've parsed as second value like foo[]=1&foo[]=2, keep
        # going as an already-made list.
        # If it's not got the array/dict chars, like foo[]=1&foo=2
        # then still treat it as an array, because foo=1&foo=2 should
        # be multiple values for the same key
        obj[key].append(val)
    # val isn't an array, but since a second value has been specified,
    # convert val into an array.
    # It implicitly ought to be an array/list here, so we can hopefully
    # ignore the required isinstance check...
    elif key in obj:
        obj[key] = [obj[key], val]
    # val is a scalar.
    else:
        obj[key] = val
    return obj, seen_fields


def dumps(
    data: Dict[str, Union[Dict[Text, Any], List[Any], int, float, bool, None]],
    *,
    encoding="utf-8",
    coerce: bool = True,
    max_num_fields: int = 1000,
    max_depth: int = 5,
):
    """
    Dump a (potentially) nested dictionary into a URL encoded string.

    References:
        https://github.com/jquery/jquery/blob/683ceb8ff067ac53a7cb464ba1ec3f88e353e3f5/src/serialize.js#L55-L91
        https://github.com/knowledgecode/jquery-param/blob/94db6fd4a34107543e4fbad84d119986a155a01f/src/index.js#L10-L48
    """
    s = []

    def add(key, value):
        # Allow for coercion to work if re-loading the same value...
        # The true/false ones have to come before the isinstance test for ints
        # because isinstance(True, int) is True...
        if value is True or value is False:
            value = COERCE_DUMP_CONSTANTS[value]
        if isinstance(value, int):
            # Subclasses of int/float may override __repr__, but we still
            # want to encode them as integers/floats in JSON. One example
            # within the standard library is IntEnum.
            value = int.__repr__(value)
        elif value in COERCE_DUMP_CONSTANTS:
            value = COERCE_DUMP_CONSTANTS[value]
        elif isinstance(value, float):
            # see comment above for int
            if value != value:
                value = "NaN"
            else:
                value = float.__repr__(value)
        else:
            value = str(value)
        quoted_key = quote_plus(key, encoding=encoding)
        quoted_value = quote_plus(value, encoding=encoding)
        return f"{quoted_key}={quoted_value}"

    def build_params(prefix, obj) -> list:
        if prefix:

            if isinstance(obj, list):
                for i, value in enumerate(obj):
                    build_params(f"{prefix}[{i}]", value)
            elif isinstance(obj, dict):
                for key, value in obj.items():
                    build_params(f"{prefix}[{key}]", value)
            else:
                s.append(add(prefix, obj))

        elif isinstance(obj, list):
            for i, value in enumerate(obj):
                s.append(add(f"{prefix}[{i}]", value))
        else:
            for key, value in obj.items():
                build_params(key, value)
        return s

    return "&".join(build_params("", data))
