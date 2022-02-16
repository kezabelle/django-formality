import re
import string
from collections import namedtuple
from itertools import zip_longest
from typing import Dict, Any



def parse_nested_query(qs: str, separator = None):
    params = {}
    parts = qs.split('&')
    for part in parts:
        key, sep, value = part.partition('=')
        _normalize_params(params, key, value, 0)
    return params

def _normalize_params(params, name, value, depth):
    if not name:
        # nil name, treat same as empty string (required by tests)
        k, after = '', ''
    elif depth == 0:

        if '[' in name:
            # Start of parameter nesting, use part before brackets as key
            start = name.index('[', 1)
            k = name[0:start]
            after = name[start:]
            del start
        else:
            # Plain parameter with no nesting
            k = name
            after = ''

    elif name[0:2] == "[]":
        # Array nesting
        k = "[]"
        after = name[2:]
    elif name[0] == "[" and name.find(']', 1):
        # Hash nesting, use the part inside brackets as the key
        start = name.find(']', 1)
        k = name[1:start]
        after = name[start + 1:]
    else:
        # Probably malformed input, nested but not starting with [
        # treat full name as key for backwards compatibility.
        k = name
        after = ''

    value = value or ''

    if not k:
        if value and name == "[]":
            return [value]
        else:
            return value

    if after == '':
        if k == '[]' and depth != 0:
            return [value]
        else:
            params[k] = value
    elif after == '[':
        params[name] = value
    elif after == '[]':
        if k not in params:
            params[k] = []

        if not isinstance(params[k], list):
            raise TypeError(f"expected list (got {params[k].__class__.__name__}) for param '{k}'")
        params[k].append(value)
    elif after[0:2] == "[]":
        # Recognize x[][y] (hash inside array) parameters

        child_key = ''
        if after[2] == "[" and after[-1] == "]":
            child_key = after[3: len(after) - 4]
            if child_key and '[' not in child_key and ']' not in child_key:
                # Handle other nested array parameters
                child_key = after[2:]
            # print(child_key)

        if k not in params:
            params[k] = []
        # elif k in params:
        #     raise TypeError("fuck")

        if not isinstance(params[k], list):
            raise TypeError(f"expected list (got {params[k].__class__.__name__}) for param '{k}'")

        if params[k] and isinstance(params[k][-1], dict) and not params_hash_has_key(params[k][-1], child_key):
            _normalize_params(params[k], child_key, value, depth+1)
        else:
            params[k] = _normalize_params({}, child_key, value, depth+1)
    else:
        if k not in params:
            params[k] = {}
        elif not isinstance(params[k], dict):
            raise TypeError(f"expected dict (got {params[k].__class__.__name__}) for param '{k}'")
        params = _normalize_params(params[k], after, value, depth+1)

    return params

def params_hash_has_key(hash, key):
    if re.match('\[\]', key):
        return False

    parts = re.split('[\[\]]+')
    for part in parts:
        ...
    # key.split(/[\[\]]+/).inject(hash) do |h, part|
    # next h if part == ''
    # return false unless params_hash_type?(h) && h.key?(part)
    # h[part]

    return True





# import re
#
#
# class NestedParser:
#     _valid = None
#     errors = None
#
#     def __init__(self, data, options={}):
#         self.data = data
#         self._merge_options(options)
#
#     def _merge_options(self, options):
#         DEFAULT_OPTIONS = {
#             "separator": "mixed-dot",
#             "raise_duplicate": True,
#             "assign_duplicate": False
#         }
#
#         options = {**DEFAULT_OPTIONS, **options}
#         self._options = options
#
#         assert self._options.get("separator", "mixed-dot") in [
#             "dot", "bracket", "mixed", "mixed-dot"]
#         assert isinstance(self._options.get("raise_duplicate", False), bool)
#         assert isinstance(self._options.get("assign_duplicate", False), bool)
#
#         self.__is_dot = False
#         self.__is_mixed = False
#         self.__is_bracket = False
#         self.__is_mixed_dot = False
#         if self._options["separator"] == "dot":
#             self.__is_dot = True
#         elif self._options["separator"] == "mixed":
#             self.__is_mixed = True
#         elif self._options["separator"] == "mixed-dot":
#             self.__is_mixed_dot = True
#         else:
#             self.__is_bracket = True
#             self._reg = re.compile(r"\[|\]")
#
#     def mixed_split(self, key):
#         def span(key, i):
#             old = i
#             while i != len(key):
#                 if key[i] in ".[]":
#                     break
#                 i += 1
#             if old == i:
#                 raise ValueError(
#                     f"invalid format key '{full_keys}', empty key value at position {i + pos}")
#             return i
#
#         full_keys = key
#         idx = span(key, 0)
#         pos = idx
#         keys = [key[:idx]]
#         key = key[idx:]
#
#         i = 0
#         last_is_list = False
#         while i < len(key):
#             if key[i] == '[':
#                 i += 1
#                 idx = span(key, i)
#                 if key[idx] != ']':
#                     raise ValueError(
#                         f"invalid format key '{full_keys}', not end with bracket at position {i + pos}")
#                 sub = key[i: idx]
#                 if not sub.isdigit():
#                     raise ValueError(
#                         f"invalid format key '{full_keys}', list key is not a valid number at position {i + pos}")
#                 keys.append(int(key[i: idx]))
#                 i = idx + 1
#                 last_is_list = True
#             elif key[i] == ']':
#                 raise ValueError(
#                     f"invalid format key '{full_keys}', not start with bracket at position {i + pos}")
#             elif (key[i] == '.' and self.__is_mixed_dot) or (
#                 not self.__is_mixed_dot and (
#                     (key[i] != '.' and last_is_list) or
#                     (key[i] == '.' and not last_is_list)
#                 )
#             ):
#                 if self.__is_mixed_dot or not last_is_list:
#                     i += 1
#                 idx = span(key, i)
#                 keys.append(key[i: idx])
#                 i = idx
#                 last_is_list = False
#             else:
#                 raise ValueError(
#                     f"invalid format key '{full_keys}', invalid char at position {i + pos}")
#         return keys
#
#     def split_key(self, key):
#         # remove space
#         k = key.replace(" ", "")
#         if len(k) != len(key):
#             raise Exception(f"invalid format from key {key}, no space allowed")
#
#         # remove empty string and count key length for check is a good format
#         # reduce + filter are a hight cost so do manualy with for loop
#
#         # optimize by split with string func
#         if self.__is_mixed or self.__is_mixed_dot:
#             return self.mixed_split(key)
#         if self.__is_dot:
#             length = 1
#             splitter = key.split(".")
#         else:
#             length = 2
#             splitter = self._reg.split(key)
#
#         check = -length
#
#         results = []
#         for select in splitter:
#             if select:
#                 results.append(select)
#                 check += len(select) + length
#
#         if len(key) != check:
#             raise Exception(f"invalid format from key {key}")
#         return results
#
#     def set_type(self, dtc, key, value, full_keys, prev=None, last=False):
#         if isinstance(dtc, list):
#             key = int(key)
#             if len(dtc) < key:
#                 raise ValueError(
#                     f"key \"{full_keys}\" is upper than actual list")
#             if len(dtc) == key:
#                 dtc.append(value)
#         elif isinstance(dtc, dict):
#             if key not in dtc or last and self._options["assign_duplicate"]:
#                 dtc[key] = value
#         else:
#             if self._options["raise_duplicate"]:
#                 raise ValueError(
#                     f"invalid rewrite key from \"{full_keys}\" to \"{dtc}\"")
#             elif self._options["assign_duplicate"]:
#                 dtc = prev['dtc']
#                 dtc[prev['key']] = prev['type']
#                 return self.set_type(dtc[prev['key']], key, value, full_keys, prev, last)
#         return key
#
#     def get_next_type(self, key):
#         if self.__is_mixed or self.__is_mixed_dot:
#             return [] if isinstance(key, int) else {}
#         return [] if key.isdigit() else {}
#
#     def convert_value(self, data, key):
#         return data[key]
#
#     def construct(self, data):
#         dictionary = {}
#         prev = {}
#
#         for key in data:
#             keys = self.split_key(key)
#             tmp = dictionary
#
#             # need it for duplicate assignement
#             prev['key'] = keys[0]
#             prev['dtc'] = tmp
#             prev['type'] = None
#
#             # optimize with while loop instend of for in with zip function
#             i = 0
#             lenght = len(keys) - 1
#             while i < lenght:
#                 set_type = self.get_next_type(keys[i+1])
#                 index = self.set_type(tmp, keys[i], set_type, key, prev)
#
#                 prev['dtc'] = tmp
#                 prev['key'] = index
#                 prev['type'] = set_type
#
#                 tmp = tmp[index]
#                 i += 1
#
#             value = self.convert_value(data, key)
#             self.set_type(tmp, keys[-1], value, key, prev, True)
#         return dictionary
#
#     def is_valid(self):
#         self._valid = False
#         # try:
#         self.__validate_data = self.construct(self.data)
#         self._valid = True
#         # except Exception as err:
#         #     self.errors = err
#         return self._valid
#
#     @property
#     def validate_data(self):
#         if self._valid is None:
#             raise ValueError(
#                 "You need to be call is_valid() before access validate_data")
#         if self._valid is False:
#             raise ValueError("You can't get validate data")
#         return self.__validate_data


# def parse_nested_query2(qs: str, separator = None):
#     params = {}
#     parts = qs.split('&')
#     for part in parts:
#         key, sep, value = part.partition('=')
#         params[key] = value
#     np = NestedParser(params, {"separator": "bracket"})
#     np.is_valid()
#     return np.validate_data


class NestingToken(namedtuple("NestingToken", ("expecting", "parent", "index", "part", "start", "end"))):
    # @property
    # def expects_parent_to_be(self):
    #     if self.index == "":
    #         return list
    #     elif all(bit in string.digits for bit in self.index):
    #         return list
    #     return dict
    #
    # @property
    # def item(self):
    #     if self.index == "":
    #         return None
    #     elif all(bit in string.digits for bit in self.index):
    #         return int(self.index)
    #     return self.index

    def __repr__(self):
        return f'<NestingToken [{self.expecting.__name__!s}] parent={self.parent!r}, index={self.index!r}, part={self.part!r}, start={self.start}, end={self.end}>'


class NestedKey:
    __slots__ = ('value', 'iterator', "seen", "opencloses", "lastindex", 'is_open')
    START = '['
    END = ']'

    def __new__(cls, value):
        instance = super().__new__(cls)
        instance.value = value
        instance.iterator = iter(instance.value)
        instance.seen = ''
        instance.opencloses = []
        instance.lastindex = 0  #len(value)
        instance.is_open = False
        return instance

    def __repr__(self):
        return f'<{self.__class__.__qualname__} value={self.value!r}, seen={self.seen!r}>'

    def parse_until(self, values=()):
        seen = ""
        for char in self.iterator:
            self.lastindex += 1
            self.seen += char
            if char in values:
                # self.is_open = not self.is_open
                return seen, char
            seen += char
        return seen, ""

    def parse_until_start(self):
        previous_start = self.lastindex
        taken, lastchar = self.parse_until(self.START)
        # if self.is_open:
        #     self.opencloses.append([self.lastindex, None, taken])
        # else:
        #     self.opencloses.append([previous_start, self.lastindex, taken])
        return taken, lastchar, self.lastindex

    def parse_until_end(self):
        taken, lastchar = self.parse_until(self.END)
        # if self.is_open:
        #     self.opencloses[-1][1] = self.lastindex-1
        return taken, lastchar, self.lastindex-1

    def incomplete(self):
        return self.seen != self.value

    def complete(self):
        return self.seen == self.value

    def consume(self):
        # if self.START not in self.value and self.END not in self.value:
        #
        # i = 0
        # print(self.value)
        # Handle the simple case, no nested keys ...
        if self.START not in self.value or self.END not in self.value:
            end = len(self.value)
            self.opencloses.append(
                # (self.lastindex, end, self.value)
                ["", 0, "", self.value, "", end, dict]
            )
            self.seen = self.value
            self.lastindex = end
            yield self.value, ""

        first = True
        while self.incomplete():
            # start_begins = self.lastindex
            start, start_stop_char, start_stops_at = self.parse_until_start()

            if first:
                self.opencloses.append(
                    ["", 0, "", start, "", start_stops_at-1, dict]
                )
                first = False

            if start_stop_char == self.START:
                self.is_open = True
                if self.is_open:
                    self.opencloses.append(
                        [start, start_stops_at, start_stop_char, None, None, None, dict]
                    )

            end, end_stop_char, end_stops_at = self.parse_until_end()
            if self.is_open:

                if end == "":
                    end = None
                    expecting = list
                # x[0..]
                elif end[0] in string.digits:
                    # x[23]
                    if all(bit in string.digits for bit in end):
                        expecting = list
                        try:
                            end = int(end)
                        except ValueError as e:
                            # x[2???]
                            expecting = dict
                    else:
                        # x[2bd]
                        expecting = dict
                else:
                    expecting = dict

                self.opencloses[-1][3] = end
                self.opencloses[-1][4] = end_stop_char
                self.opencloses[-1][5] = end_stops_at
                self.opencloses[-1][6] = expecting
                #
                # append(
                #     (end, start_stop_char, end_stop_char, self.value[start_stops_at:end_stops_at])
                # )
            self.is_open = False
            # start, start_lastchar = self.parse_until(self.START)
            # start_ends = self.lastindex-1
            # start_bit = self.value[start_begins:start_ends]
            #
            # if start_lastchar == self.START:
            #     self.opencloses.append(
            #         (start, start_begins, start_ends, start_lastchar, start_bit)
            #     )

            # if start_lastchar == self.START:
            #
            # end_begins = self.lastindex
            # end, end_lastchar = self.parse_until(self.END)
            # end_ends = self.lastindex -1
            # end_bit = self.value[end_begins:end_ends]
            #
            # if end_lastchar == self.END:
            #     self.opencloses[-1] += (end, end_begins, end_ends, end_lastchar, end_bit)

            # Index access, e.g. x[]


            # if start and end and start_lastchar == self.START and end_lastchar == self.END:
            #     print('consuming INDEX ACCESS', locals())
            #
            # # elif start:
            # else:
            #     print('consuming', locals())
            # end, end_upto = self.parse_until_end()
            # end_ends = self.lastindex-1
            # if start:
            #     yield 'start', start, start_upto, start_begins, start_ends
            # yield 'end', end, end_upto, start_ends, end_ends
            #
            # yield NestingToken(
            #         expecting,
            #         taken,
            #         index,
            #         part,
            #         start,
            #         end,
            # )
            # start = ""
            # end = ""
            # for char in self.iterator:
            #     i += 1
            #     # self.lastindex += 1
            #     # self.seen += char
            #     if char == ']':
            #         # self.is_open = not self.is_open
            #         break
            #     end += char
            #
            # for char in end:
            #     # self.lastindex += 1
            #     # self.seen += char
            #     end = end[1:]
            #     if char == '[':
            #         # self.is_open = not self.is_open
            #         break
            #     start += char
            #     print(start, end)
            # if end:
            #     yield end
            # start = self.parse_until_start()
            # # # if start:
            # yield start
            # # # if end:
            # # # if all(bit in string.digits for bit in end):
            # yield end
            # # else:
            #     yield end, 'dict item'
        # if self.opencloses and self.opencloses[-1][1] is None:
        #     self.opencloses[-1][1] = self.lastindex
        # print(self.opencloses)
        # print('*'*32)

    # def _nesting_tokens(self):
    #     if not self.complete():
    #         raise ValueError("unfinished")
    #
    #     first = True
    #     for start, end, taken in self.opencloses:
    #         # index = self.value[start:end]
    #         part = None # self.value[start-1:end+1]
    #
    #         # Top level should always expect to be added into a dict
    #         if first:
    #             expecting = dict
    #             first = False
    #         else:
    #             if taken == "":
    #                 expecting = list
    #             elif all(bit in string.digits for bit in taken):
    #                 expecting = list
    #                 try:
    #                     taken = int(taken)
    #                 except ValueError as e:
    #                     expecting = dict
    #             else:
    #                 expecting = dict
    #
    #         yield NestingToken(
    #             expecting,
    #             taken,
    #             None,
    #             None,
    #             start,
    #             end,
    #         )

    def tokens(self):
        tuple(self.consume())
        return self.opencloses

    # def tokens1(self):
    #     tuple(self.consume())
    #     return tuple(self._nesting_tokens())




def parse_nested_query3(qs: str):
    params = {}
    for part in qs.split('&'):
        key, _, value = part.partition('=')
        currkey = peeked = ''
        is_open = False
        nestedkey = NestedKey(key)
        while nestedkey.incomplete():
            partofkey = nestedkey.parse_until('[')
            if partofkey:
                subkey = nestedkey.parse_until(']')
                print(partofkey, subkey)
                break
        continue
        for current_char, next_char in zip_longest(key, key[1:], fillvalue=''):
            if next_char:
                pass
            else:
                is_open = False
                # currkey += current_char
                print(f'subkey is {currkey}')
            if current_char == '[':
                # Simple array index, x[]
                if next_char == ']':
                    print(f'{peeked} is array')
                    # if peeked not in params:
                    #     params[peeked] = []
                    currkey = ''
                # Array index by number, x[2]
                elif next_char in string.digits:
                    is_open = True
                    currkey = ''



                    print(f'{peeked} is array')
                # Prevent quoted dictionary access
                elif next_char == "'" or next_char == '"':
                    raise ValueError("Quoted value ...")
                # Dictionary access, x[test]
                else:
                    is_open = True
                    currkey = ''
                    print(f'{peeked} is dict')
            elif current_char == ']' and is_open:
                is_open = False
            elif is_open:
                currkey += current_char

            peeked += current_char


def parse_nested_query4(qs: str):
    # components = re.split("\[\]|\[(.+?)\]", "qs")
    # # Last part is value, including the = symbol.
    # value = components.pop()
    # array_append = ["", ""]
    params = {}
    # fixups = []

    def next_param(x):

        return

    for kvi, keyvalue in enumerate(qs.split('&')):
        key, _, value = keyvalue.partition('=')
        currlevel = params
        keyreader = NestedKey(key).tokens()
        key_count = len(keyreader)-1
        prevkey = None
        prevlevel = currlevel
        for i, keypart in enumerate(keyreader):
            # try:
            #     nextpart = keyreader[i+1]
            # except IndexError:
            #     nextpart = None
            parent, from_index, open, key, close, to_index, expecting = keypart

            if key is None:
                key = len(currlevel)


            # if isinstance(key, int):
            #     if prevkey in prevlevel and isinstance(prevlevel[prevkey], dict):
            #         prevlevel[prevkey] = [*currlevel.values()]
            #         currlevel = prevlevel[prevkey]
            #     if key:
            #         while len(currlevel) <= key:
            #             currlevel.append("")
            #     if key_count == i:
            #         currlevel[key] = value
            #     # fixups.append(currlevel)
            # else:
            currlevel[key] = {}
            # Last iteration, finally add the value
            if key_count == i:
                currlevel[key] = value
            # Just increase our depth
            else:
                currlevel = currlevel[key]
            # if not isinstance(currlevel, expecting):
            #     raise ValueError("fucked level")
            #
            # if isinstance(currlevel, dict):
            #     if key is None:
            #         raise ValueError("missing key part for dict")
            #     else:
            #         currlevel[key] = ""
            # elif isinstance(currlevel, list):
            #     if key is None:
            #         currlevel.append("")
            #     elif len(currlevel) < key:
            #         while len(currlevel) <key:
            #             currlevel.append("")
            #     else:
            #         pass
            # else:
            #     pass

            #
            # if nextpart is not None:
            #     container = nextpart[6]()
            #     if isinstance(container, list):
            #
            #         if nextpart[3]:
            #             while len(container) < nextpart[3]:
            #                 container.append("")
            #         if key == "":
            #             container.append("")
            #         else:
            #             currlevel[key] = container
            #     else:
            #         currlevel[key] = container
            #     currlevel = currlevel[key]
            #     print(currlevel)
            # else:
            #     currlevel[key] = value
            prevkey = key
            print('*'*32)
        # currlevel = value
        # print("key + split parts", keyvalue, keyparts)

    from pprint import pprint
    pprint(params)
    return params
        # for keyi, keypart in enumerate(keyparts):
        #     try:
        #         previouspart = keyparts[keyi-1]
        #         previoustype = previouspart.expecting
        #     except IndexError:
        #         previouspart = None
        #         previouspart = None
        #     try:
        #         nextpart = keyparts[keyi+1]
        #         nexttype = nextpart.expecting
        #     except IndexError:
        #         nextpart = None
        #         nexttype = value
        #     # First time, try and populate the top-level key
        #     if keyi == 0:
        #         if not keypart.parent:
        #             raise ValueError("empty top-level ...")
        #         elif not isinstance(currlevel, dict):
        #             raise TypeError("Screwed the reset somewhere, currlevel is not a dict")
        #         elif keypart.parent not in currlevel:
        #             currlevel[keypart.parent] = keypart.expecting()
        #         elif keypart.parent in currlevel and not isinstance(currlevel[keypart.parent], keypart.expecting):
        #             raise TypeError(f"Expected {keypart.parent} to be {keypart.expecting.__name__} container, got {currlevel.__class__.__name__}")
        #         currlevel = currlevel[keypart.parent]
        # #                 currlevel[keypart.parent] = keypart.expecting()
        # #                 currlevel = currlevel[keypart.parent]
        # #             else:
        # #                 raise ValueError("Already set ...")
        # #     # Every other thing should be nested on the top-level key
        # #     else:
        # #         # if nextpart:
        # #
        # #         # if not isinstance(currlevel, previouspart.expecting):
        # #         #     raise TypeError(f"Expected previous part to be {keypart.expecting.__name__} container, got {currlevel.__class__.__name__}")
        # #         if isinstance(currlevel, list):
        # #             if keypart.parent:
        # #                 currlevel.insert(keypart.parent, keypart.expecting())
        # #                 currlevel = currlevel[keypart.parent]
        # #             else:
        # #                 currlevel.append(keypart.expecting())
        # #                 currlevel = currlevel[-1]
        # #         elif isinstance(currlevel, dict):
        # #             currlevel[keypart.parent] = ""
        # #         # currlevel[keypart.parent] = keypart.expecting()
        # #         # print(currlevel)
        # # currlevel[keypart.parent] = value
        # # key_sections = [section_end.split("]") for section_end in key.split("[")]
        # # # key_sections = tuple((len(key_section), key_section) for key_section in key_sections)
        # # print(key_sections)
        # # currkey = ''
        # # for section in key_sections:
        # #     length = len(section)
        # #     print(length, section)
        # #     if length == 1:
        # #         item = section.pop()
        # #         if not item:
        # #             print('unbalanced square brackets')
        # #         else:
        # #             currkey = item
        # #     # pass
        # # print('*'*32)
    return params

x = (
    # 'a=1&b[]=1&b[]=2&c[test]=1&c[best]=2&c[test]=2&d[][test]=1&d[][test2]=2',
    # "x[][y][woo]=1&x[][z]=2&x[][y][woo]=3&x[][z]=4",

    # "abc=1",
    "xyz[2][][y][][woo]=4&abc=1&def[[[]&a[[[=2",
    # "a[[[]=1",
    # "a[]]]=1",
    # "a[[[=1",
    # "a]]]=1",
    # "xyz[[2][y][]t[[][woo]=4&abc=1&def[[[]&a[[[=2",

    # "x[][z][w]=1&x[][z]=2&x[][y][w]=3&x[][z]=4",
    # "x[][z][w]=1&x[][z][j]=2&x[][y][w]=3&x[][b]=4",
    # "d[]=a&d[]=b&d[]=c",
    # "d[][a]=a&d[][b]=b&d[][c]=c",

)
for test in x:
    #[_.split("]") for _ in x.split("[")]
    # x = NestedKey(val)
    # print(val)
    # print(tuple(x.consume()))
    # print(x.tokens())
    # print(x.parse(until="["))
    # print(x.parse(until="]"))
    # print(x.parse(until="]"))

    parse_nested_query(test)
    # np = NestedParser(test, {"separator": "bracket"})
    # np.is_valid()
    # print(np.errors)
    # print(np.validate_data)

