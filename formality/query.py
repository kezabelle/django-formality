import string
import json.decoder
from urllib.parse import quote, unquote, quote_plus

import json.scanner
from typing import Dict, Union, Text, Any, List



def loads(
    qs: Union[str, bytes], encoding: str = 'utf-8', coerce: bool = True
) -> Dict[str, Union[Dict[Text, Any], List[Any], int, float, bool, None]]:
    """
    References:
        https://benalman.com/projects/jquery-bbq-plugin/
        https://benalman.com/code/projects/jquery-bbq/examples/deparam/
        https://github.com/cowboy/jquery-bbq/blob/8e0064ba68a34bcd805e15499cb45de3f4cc398d/jquery.ba-bbq.js#L444-L556
    """
    constants = {
    "true": True,
    "false": False,
    "null": None,
    "NaN": json.decoder.NaN,
    "Infinity": json.decoder.PosInf,
    "-Infinity": json.decoder.NegInf,
    }
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
        param = part.split("=", 1)
        # translate key as per urllib.parse.parse_qsl
        key = unquote(param[0].replace("+", " "), encoding)
        try:
            # translate value as per urllib.parse.parse_qsl
            val = unquote(param[1].replace("+", " "), encoding)
        except IndexError:
            # No value was defined, so set something meaningful.
            val = ""
        cur: Union[Dict[Text, Any], List] = obj
        i = 0
        # If key is more complex than 'foo', like 'a[]' or 'a[b][c]', split it
        # into its component parts.
        keys = key.split("][")
        keys_last = len(keys) - 1

        # If the first keys part contains [ and the last ends with ], then []
        # are correctly balanced.
        if "[" in keys[0] and "]" in keys[keys_last]:
            # Remove the trailing ] from the last keys part.
            keys[keys_last] = keys[keys_last][:-1]

            # Split first keys part into two parts on the [ and add them back onto
            # the beginning of the keys array.
            keys = [*keys.pop(0).split("["), *keys]
            keys_last = len(keys) - 1
        else:
            keys_last = 0

        if len(param) == 2:
            if coerce and val:
                if val in constants:
                    val = constants[val]
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
                while i <= keys_last:

                    key = len(cur) if keys[i] == "" else keys[i]
                    # Does it look like an array key? If so, make it one.
                    if isinstance(key, str) and key[0] in string.digits:
                        try:
                            key = int(key)
                        except ValueError:
                            pass

                    # https://opengg.github.io/babel-plugin-transform-ternary-to-if-else/
                    # Todo: figure out how to unwrap this from being 2 closures
                    def inner2():
                        if keys[i + 1] and any(
                            chr not in string.digits for chr in keys[i + 1]
                        ):
                            return {}
                        return []

                    def inner():
                        if i < keys_last:
                            try:
                                return cur[key]
                            except (IndexError, KeyError):
                                return inner2()
                        return val

                    # Need the value slightly ahead-of-time to backfill incomplete
                    # arrays with the same type...
                    bit = inner()
                    if isinstance(cur, list) and isinstance(key, int):
                        # Have to fill up the list if the key isn't 0, because
                        # Python is less lax and it'd be an:
                        # IndexError: list assignment index out of range
                        while len(cur) <= key:
                            cur.append(type(bit)())
                    cur[key] = bit
                    cur = cur[key]
                    i += 1
            # Simple key, even simpler rules, since only scalars and shallow
            # arrays are allowed.
            else:
                # val is already an array, so push on the next value.
                if isinstance(obj, dict) and key in obj and isinstance(obj[key], list):
                    # if isinstance(obj[key], list):
                    obj[key].append(val)
                # val isn't an array, but since a second value has been specified,
                # convert val into an array.
                elif not isinstance(obj, list) and key in obj:
                    obj[key] = [obj.get(key, ""), val]
                # val is a scalar.
                else:
                    obj[key] = val
        elif key:
            obj[key] = val

    return obj


def dumps(data: Dict[str, Union[Dict[Text, Any], List[Any], int, float, bool, None]], encoding='utf-8'):
    """
    Dump a (potentially) nested dictionary into a URL encoded string.

    References:
        https://github.com/jquery/jquery/blob/683ceb8ff067ac53a7cb464ba1ec3f88e353e3f5/src/serialize.js#L55-L91
        https://github.com/knowledgecode/jquery-param/blob/94db6fd4a34107543e4fbad84d119986a155a01f/src/index.js#L10-L48
    """
    s = []
    constants = {
        True: "true",
        False: "false",
        None: "null",
        json.decoder.PosInf: "Infinity",
        json.decoder.NegInf: "-Infinity",
        # Can't put float('nan') -> NaN in here because it doesn't compute as
        # the same: float('nan') == float('nan') is False
    }

    def add(key, value):
        # Allow for coercion to work if re-loading the same value...
        if isinstance(value, int):
            # Subclasses of int/float may override __repr__, but we still
            # want to encode them as integers/floats in JSON. One example
            # within the standard library is IntEnum.
            value = int.__repr__(value)
        elif value in constants:
            value = constants[value]
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
        return f'{quoted_key}={quoted_value}'

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
    return "&".join(build_params('', data))
