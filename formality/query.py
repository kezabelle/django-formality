import re
import string
from collections import namedtuple
from itertools import zip_longest
from json.decoder import NegInf, PosInf, NaN

from json.scanner import NUMBER_RE
from typing import Dict, Any





def parse_nested_query(qs: str, coerce=True):
    obj = {}
    parts = qs.split('&')
    for part in parts:
        key, sep, val = part.partition('=')
        # key may need decoding?
        cur = obj
        i = 0
        # If key is more complex than 'foo', like 'a[]' or 'a[b][c]', split it
        # into its component parts.
        keys = key.split('][')
        keys_last = len(keys) - 1

        # If the first keys part contains [ and the last ends with ], then []
        # are correctly balanced.
        if '[' in keys[0] and ']' in keys[keys_last]:
            # Remove the trailing ] from the last keys part.
            keys[keys_last] = keys[keys_last][:-1]

            # Split first keys part into two parts on the [ and add them back onto
            # the beginning of the keys array.
            keys = [*keys.pop(0).split('['), *keys]
            keys_last = len(keys) - 1
        else:
            keys_last = 0

        if val:

            if coerce:
                if val == "true":
                    val = True
                elif val == "false":
                    val = False
                elif val == "null":
                    val = None
                elif val == "NaN":
                    val = NaN
                elif val == "Infinity":
                    val = PosInf
                elif val == "-Infinity":
                    val = NegInf
                else:
                    match_number = NUMBER_RE.match(val)
                    if match_number is not None:
                        integer, frac, exp = match_number.groups()
                        if frac or exp:
                            val = float(integer + (frac or '') + (exp or ''))
                        else:
                            val = int(integer)



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

                    def inner2():
                        if keys[i+1] and any(chr not in string.digits for chr in keys[i+1]):
                            return {}
                        return []

                    def inner():
                        if i < keys_last:
                            try:
                                return cur[key]
                            except (IndexError, KeyError):
                                return inner2()
                        return val

                    # if i < keys_last:
                    #     if not cur[key]:
                    #         if keys[i+1]:
                    #             cur = cur[key] = {}
                    #         else:
                    #             cur = cur[key] = []
                    if isinstance(cur, list) and isinstance(key, int):
                        while len(cur) <= key:
                            cur.append(inner())
                    else:
                        cur[key] = inner()
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

        else:
            # No value was defined, so set something meaningful.
            obj[key] = ''
    return obj




from pprint import pprint

tests = (
    "xyz[2][][y][][woo]=4&abc=1&def[[[]&a[[[=2",

    "b[z][]=",
    "a=1&a=2&a=3&b=4&c=true&d=0",
    "a[]=1&a[]=2&a[]=3&b=4&c=true&d=0",
    "a[]=4&a[]=5&a[]=6&b[x][]=7&b[y]=8&b[z][]=9&b[z][]=0&b[z][]=true&b[z][]=false&b[z][]=undefined&b[z][]=&c=1",
    "a[]=0&a[1][]=1&a[1][]=2&a[2][]=3&a[2][1][]=4&a[2][1][]=5&a[2][2][]=6&a[3][b][]=7&a[3][b][1][]=8&a[3][b][1][]=9 &a[3][b][2][0][c]=10&a[3][b][2][0][d]=11&a[3][b][3][0][]=12&a[3][b][4][0][0][]=13&a[3][b][5][e][f][g][]=14 &a[3][b][5][e][f][g][1][]=15&a[3][b][]=16&a[]=17",
)
for test in tests:
    pprint(parse_nested_query(test))

