from __future__ import absolute_import, division, print_function, unicode_literals

##########################################################
# Author: Yichen Huang (Eugene)
# GitHub: https://github.com/yichen0831/opencc-python
# January, 2016
##########################################################
##########################################################
# Revised by: Hopkins1 
# June, 2016
# Apache License Version 2.0, January 2004
# - Use a tree-like structure hold the result during conversion
# - Always choose the longest matching string from left to right in dictionary
#   by trying lookups in the dictionary rather than looping
# - Split the incoming string into smaller strings before processing to improve speed
# - Only match once per dictionary
# - If a dictionary is configured as part of a group, only match once per group
#   in order of the listed dictionaries
# - Cache the results of reading a dictionary in self.dict_cache
# - Use "from __future__ import" to allow support for both Python 2.7
#   and Python >3.2
##########################################################
import io
import json
import os
import re

CONFIG_DIR = 'config'
DICT_DIR = 'dictionary'


class OpenCC:
    def __init__(self, conversion=None):
        """
        init OpenCC
        :param conversion: the conversion of usage, options are
         'hk2s', 's2hk', 's2t', 's2tw', 's2twp', 't2hk', 't2s', 't2tw', 'tw2s', 'tw2sp', etc
         check the json file names in config directory
        :return: None
        """
        self.conversion_name = ''
        self.conversion = conversion
        self._dict_init_done = False
        self._dict_chain = list()
        self._dict_chain_data = list()
        self.dict_cache = dict()
        # List of sentence separators from OpenCC PhraseExtract.cpp. None of these separators are allowed as
        # part of a dictionary entry
        self.split_chars_re = re.compile(
            r'(\s+|-|,|\.|\?|!|\*|　|，|。|、|；|：|？|！|…|“|”|‘|’|『|』|「|」|﹁|﹂|—|－|（|）|《|》|〈|〉|～|．|／|＼|︒|︑|︔|︓|︿|﹀|︹|︺|︙|︐|［|﹇|］|﹈|︕|︖|︰|︳|︴|︽|︾|︵|︶|｛|︷|｝|︸|﹃|﹄|【|︻|】|︼)')
        if self.conversion is not None:
            self._init_dict()

    def convert(self, string):
        """
        Convert string from Simplified Chinese to Traditional Chinese or vice versa
        """
        if not self._dict_init_done:
            self._init_dict()
            self._dict_init_done = True

        result = []
        # Separate string using the list of separators in a regular expression
        split_string_list = self.split_chars_re.split(string)
        for i in range(0, len(split_string_list)):
            if i % 2 == 0:
                # Work with the text string
                # Append converted string to result
                result.append(self._convert(split_string_list[i], self._dict_chain_data))
            else:
                # Work with the separator
                # Append separator string to converted_string
                result.append(split_string_list[i])
        # Join it all together to return a result
        return "".join(result)

    def _convert(self, string, dictionary = []):
        """
        Convert string from Simplified Chinese to Traditional Chinese or vice versa
        If a dictionary is part of a group of dictionaries, stop conversion on a word
        after the first match is found.
        :param string: the input string
        :param dictionary: list of dictionaries to be applied against the string
        :return: converted string
        """
        tree = StringTree(string)
        for c_dict in dictionary:
            tree.create_parse_tree(c_dict)
            tree = StringTree("".join(tree.inorder()))
        return "".join(tree.inorder())

    def _init_dict(self):
        """
        initialize the dict with chosen conversion
        :return: None
        """
        if self.conversion is None:
            raise ValueError('conversion is not set')

        self._dict_chain = []
        config = self.conversion + '.json'
        config_file = os.path.join(os.path.dirname(__file__), CONFIG_DIR, config)
        with open(config_file) as f:
            setting_json = json.load(f)

        self.conversion_name = setting_json.get('name')

        for chain in setting_json.get('conversion_chain'):
            self._add_dict_chain(self._dict_chain, chain.get('dict'))

        self._dict_chain_data = []
        self._add_dictionaries(self._dict_chain, self._dict_chain_data)
        # Make sure all dictionaries are in a list
        for index, c_dict in enumerate(self._dict_chain_data):
           if isinstance(c_dict, tuple):
               self._dict_chain_data[index] = [c_dict]
        self._dict_init_done = True

    def _add_dictionaries(self, chain_list, chain_data):
        for item in chain_list:
            if isinstance(item, list):
                chain = []
                self._add_dictionaries(item, chain)
                chain_data.append(chain)
            else:
                if not item in self.dict_cache:
                    map_dict = {}
                    # Default max key length to smallest possible value
                    max_len = 1
                    # Default min key length to very large value
                    min_len = 1000
                    with io.open(item, "r", encoding="utf-8") as f:
                        for line in f:
                            key, value = line.strip().split('\t')
                            map_dict[key] = value
                            if len(key) > max_len:
                                max_len = len(key)
                            if len(key) < min_len:
                                min_len = len(key)
                    chain_data.append((max_len, min_len, map_dict))
                    self.dict_cache[item] = (max_len, min_len, map_dict)
                else:
                    chain_data.append(self.dict_cache[item])

    def _add_dict_chain(self, dict_chain, dict_dict):
        """
        add dict chain
        :param dict_chain: the dict chain to add to
        :param dict_dict: the dict to be added in
        :return: None
        """
        if dict_dict.get('type') == 'group':
            # Create a sublist of dictionaries for a group
            chain = []
            for dict_item in dict_dict.get('dicts'):
                self._add_dict_chain(chain, dict_item)
            dict_chain.append(chain)
        elif dict_dict.get('type') == 'txt':
            filename = dict_dict.get('file')
            dict_file = os.path.join(os.path.dirname(__file__), DICT_DIR, filename)
            dict_chain.append(dict_file)

    def set_conversion(self, conversion):
        """
        set conversion
        :param conversion: the conversion of usage, options are
         'hk2s', 's2hk', 's2t', 's2tw', 's2twp', 't2hk', 't2s', 't2tw', 'tw2s', and 'tw2sp'
         check the json file names in config directory
        :return: None
        """
        if self.conversion == conversion:
            return
        else:
            self._dict_init_done = False
            self.conversion = conversion

#############################################

class TreeNode(object):
    LEFT = 0
    RIGHT = 1

    def __init__(self, value, hint=None):
        self.branch = [None, None]
        self.value = value
        self.matched = False
        self.length_hint = hint

    def set_matched(self, matched):
        self.matched = matched

    def set_value(self, value):
        self.value = value

    def set_branch(self, branch, node):
        self.branch[branch] = node

    def set_hint(self, hint):
        self.length_hint = hint

class StringTree(object):
    def __init__(self, string):
        self.root = TreeNode(string)

    def create_parse_tree(self, test_dict_list):
        """
        Compare smaller and smaller sub-strings going from left to
        rightin root node value against a test_dict_list entry. If match is found,
        create tree nodes for remaining left and right string portions and place
        these nodes on a stack for processing.

        :param test_dict_list: a list of tuples of the max key length and dict
                        currently being applied against the string
        """
        # Stacks to hold nodes with unmatched strings
        working_stack = [self.root]
        unmatched_stack =[]

        # process stack
        for test_dict in test_dict_list:
            while working_stack:
                curr = working_stack.pop()
                value, lstring, rstring, test_len = self.__findMatch(curr.value, test_dict, curr.length_hint)
                if (value):
                    curr.set_value(value)
                    curr.set_hint(None)
                    curr.set_matched(True)
                    if (lstring):
                        node = TreeNode(lstring, test_len)
                        working_stack.append(node)
                        curr.set_branch(TreeNode.LEFT, node)
                    if (rstring):
                        node = TreeNode(rstring, test_len)
                        working_stack.append(node)
                        curr.set_branch(TreeNode.RIGHT, node)
                else:
                    unmatched_stack.append(curr)
                    curr.length_hint = None
            # swap stacks
            temp = working_stack
            working_stack = unmatched_stack
            unmatched_stack = temp

    def inorder(self):
        """
        Do a non-recursive inorder traversal of the tree.
        :return: list of strings
        """
        return_val = []
        stack = []
        curr = self.root

        while True:
            while curr:
                stack.append(curr)
                curr = curr.branch[TreeNode.LEFT]

            if stack:
                curr = stack.pop()
                return_val.append(curr.value)
                curr = curr.branch[TreeNode.RIGHT]
            else:
                break
        return return_val

    def __findMatch(self, string, test_dict, hint = None):
        """
        Compare smaller and smaller sub-strings going from left to
        right against test_dict. If an entry is found, return it as well
        as the remaining string(s) and the test length.

        :param cstring:  the string to find a match
        :param test_dict: a tuple of the max key length and dict currently being
                          applied against the string
        :return: the new matched value, old string to left of the match, old string to right
                of the match (may be all None if no match found), last test length
        """
        string_len = len(string)
        lstring = None
        rstring = None
        test_len = min (string_len, test_dict[0])
        if hint:
            test_len = min (test_len, hint)
        min_len = test_dict[1]
        while test_len >= min_len:
            # Loop through trying successively smaller substrings in the dictionary
            for i in range(0, string_len - test_len + 1):
                if string[i:i+test_len] in test_dict[2]:
                    # Match found.
                    if i > 0:
                        # Put everything to the left of the match into lstring
                        lstring = string[:i]
                    if (i+test_len) < string_len:
                        # Put everything to the right of the match into rstring
                        rstring = string[i+test_len:]
                    # Save the dictionary value
                    value = test_dict[2][string[i:i+test_len]]
                    if len(value.split(' ')) > 1:
                        # multiple mapping, use the first one for now
                        value = value.split(' ')[0]
                    return value, lstring, rstring, test_len
            test_len -= 1
        # No match found
        return None, None, None, None


