import string
import json.decoder
import types
from urllib.parse import unquote, quote_plus

import json.scanner
from typing import Dict, Union, Text, Any, List
from django.core.exceptions import SuspiciousOperation


class MalformedData(SuspiciousOperation):
    """
    When encountering fields like a[[[] or b[]]] just drop them immediately
    and loudly.
    """

    __slots__ = ("args", "message", "data", "key")

    def __init__(self, *args, data: str):
        super().__init__(*args)
        self.data = data
        self.key = args[0]

    def __str__(self):
        return f"Invalid nesting characters in key {self.key!r} of {self.data[0:200]!r}"


COERCE_LOAD_CONSTANTS = types.MappingProxyType({
    "true": True,
    "false": False,
    "null": None,
    "NaN": json.decoder.NaN,
    "Infinity": json.decoder.PosInf,
    "-Infinity": json.decoder.NegInf,
})
COERCE_DUMP_CONSTANTS = types.MappingProxyType({
    True: "true",
    False: "false",
    None: "null",
    json.decoder.PosInf: "Infinity",
    json.decoder.NegInf: "-Infinity",
    # Can't put float('nan') -> NaN in here because it doesn't compute as
    # the same: float('nan') == float('nan') is False
})


def loads(
    qs: Union[str, bytes],
    encoding: str = "utf-8",
    coerce: bool = True,
) -> Dict[str, Union[Dict[Text, Any], List[Any], int, float, bool, None]]:
    """
    References:
        https://benalman.com/projects/jquery-bbq-plugin/
        https://benalman.com/code/projects/jquery-bbq/examples/deparam/
        https://github.com/cowboy/jquery-bbq/blob/8e0064ba68a34bcd805e15499cb45de3f4cc398d/jquery.ba-bbq.js#L444-L556
    """
    obj = {}
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

    # Iterate over all name=value pairs.
    for part in qs.split("&"):
        key, sep, val = part.partition("=")
        # translate key as per urllib.parse.parse_qsl
        key = unquote(key.replace("+", " "), encoding)
        # Skip empty keys (e.g. "&foo=1&&bar=2")
        if not key:
            continue
        # Just drop processing immediately if the key looks invalid. Yes there
        # are false positives for if someone tries to do a[[[] expecting a key
        # of "[[" or something, but that may not even be what they're expecting...
        if "[[" in key or "]]" in key or key[0:2] == "[]":
            raise MalformedData(key, data=qs)
            # translate value as per urllib.parse.parse_qsl
        val = unquote(val.replace("+", " "), encoding)
        cur: Union[Dict[Text, Any], List] = obj
        i = 0
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
        else:
            keys_last = 0

        # if key:
        if coerce and val:
            if val in COERCE_LOAD_CONSTANTS:
                val = COERCE_LOAD_CONSTANTS[val]
            else:
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

                if key == "":
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
                        cur.append(bit_type())
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

    return obj


def dumps(
    data: Dict[str, Union[Dict[Text, Any], List[Any], int, float, bool, None]],
    encoding="utf-8",
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
