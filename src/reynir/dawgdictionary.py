"""
    Reynir: Natural language processing for Icelandic

    Compound word analyzer

    Copyright (C) 2018 Miðeind ehf.
    Author: Vilhjálmur Þorsteinsson

       This program is free software: you can redistribute it and/or modify
       it under the terms of the GNU General Public License as published by
       the Free Software Foundation, either version 3 of the License, or
       (at your option) any later version.
       This program is distributed in the hope that it will be useful,
       but WITHOUT ANY WARRANTY; without even the implied warranty of
       MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
       GNU General Public License for more details.

    You should have received a copy of the GNU General Public License
    along with this program.  If not, see http://www.gnu.org/licenses/.


    The compound word analyzer takes a word not found in the
    BIN word database and attempts to resolve it into parts
    as a compound word.

    It uses a Directed Acyclic Word Graph (DAWG) internally
    to store a large set of words in an efficient structure in terms
    of storage and speed.

    The graph is pre-built and stored in a file that
    is loaded at run-time by DawgDictionary.

"""

import os
import threading
import logging
import time
import struct
import codecs


_PATH = os.path.dirname(__file__) or "."


class Wordbase:

    """ Container for a singleton instance of the word database """

    _dawg = None
    _dawg_formers = None
    _dawg_last = None

    _lock = threading.Lock()

    @classmethod
    def _load_resource(cls, resource):
        """ Load a PackedDawgDictionary from a file """
        # Assumes that the appropriate lock has been acquired
        t0 = time.time()
        pname = os.path.abspath(
            os.path.join(
                _PATH, "resources", resource + ".dawg.bin"
            )
        )
        dawg = PackedDawgDictionary()
        dawg.load(pname)
        t1 = time.time()
        logging.info(
            "Loaded packed DAWG '{1}' in {0:.2f} seconds"
            .format(t1 - t0, resource)
        )
        # Do not assign Wordbase._dawg until fully loaded, to prevent race conditions
        return dawg

    @classmethod
    def dawg(cls):
        """ Load the combined dictionary """
        with cls._lock:
            if cls._dawg is None:
                cls._dawg = cls._load_resource("ordalisti-all")  # Main dictionary
            assert cls._dawg is not None
            return cls._dawg

    @classmethod
    def dawg_formers(cls):
        """ Load the dictionary of words allowed as prefixes
            in a compound word (i.e. can occur in any part except
            the last part of the compound word) """
        with cls._lock:
            if cls._dawg_formers is None:
                cls._dawg_formers = cls._load_resource("ordalisti-formers")
            assert cls._dawg_formers is not None
            return cls._dawg_formers

    @classmethod
    def dawg_last(cls):
        """ Load the dictionary of words that are allowed as the last
            part of a compound word """
        with cls._lock:
            if cls._dawg_last is None:
                cls._dawg_last = cls._load_resource("ordalisti-last")
            assert cls._dawg_last is not None
            return cls._dawg_last


class FindNavigator:

    """ A navigation class to be used with DawgDictionary.navigate()
        to find a particular word in the dictionary by exact match
    """

    def __init__(self, word):
        self._word = word
        self._len = len(word)
        self._index = 0
        self._found = False

    def push_edge(self, firstchar):
        """ Returns True if the edge should be entered or False if not """
        # Enter the edge if it fits where we are in the word
        return self._word[self._index] == firstchar

    def accepting(self):
        """ Returns False if the navigator does not want more characters """
        # Don't go too deep
        return self._index < self._len

    def accepts(self, newchar):
        """ Returns True if the navigator will accept the new character """
        if newchar != self._word[self._index]:
            return False
        # Match: move to the next index position
        self._index += 1
        return True

    def accept(self, matched, final):
        """ Called to inform the navigator of a match and whether it is a final word """
        if final and self._index == self._len:
            # Yes, this is what we were looking for
            assert matched == self._word
            self._found = True

    # noinspection PyMethodMayBeStatic
    def pop_edge(self):
        """ Called when leaving an edge that has been navigated """
        # We only need to visit one outgoing edge, so short-circuit the edge loop
        return False

    # noinspection PyMethodMayBeStatic
    def done(self):
        """ Called when the whole navigation is done """
        pass

    def is_found(self):
        return self._found


class CompoundNavigator:

    """ A navigation class to be used with DawgDictionary.navigate()
        to find all possible compositions of shorter words that
        together form a long (compound) word.
    """

    # Stuff not in BÍN that may occur within compound words
    _JOINERS = ["", "s"]

    def __init__(self, dawg, word):
        self._dawg = dawg
        self._word = word
        self._len = len(word)
        self._index = 0
        self._parts = []

    def push_edge(self, firstchar):
        """ Returns True if the edge should be entered or False if not """
        # Follow all edges that match a letter in the rack
        # (which can be '?', matching all edges)
        return self._word[self._index] == firstchar

    def accepting(self):
        """ Returns False if the navigator does not want more characters """
        # Continue until we have generated all left parts possible from the
        # rack but leaving at least one tile
        return self._index < self._len

    def accepts(self, newchar):
        """ Returns True if the navigator will accept the new character """
        if newchar != self._word[self._index]:
            return False
        self._index += 1
        return True

    def accept(self, matched, final):
        """ Called to inform the navigator of a match and whether it is a final word """
        if final:
            # We have a valid word so far: attempt to resolve the following text
            if self._index == self._len:
                # Complete match: return a single part
                self._parts = [[matched]]
            else:
                # So far so good: try to match the rest
                for j in CompoundNavigator._JOINERS:
                    lenj = len(j)
                    if (
                        (lenj == 0) or
                        (
                            self._index + lenj < self._len and
                            self._word[self._index:self._index + lenj] == j
                        )
                    ):
                        nav = CompoundNavigator(
                            self._dawg, self._word[self._index + lenj:]
                        )
                        self._dawg.navigate(nav)
                        result = nav.result()
                        if result:
                            self._parts.extend(
                                [[matched + j] + tail for tail in result]
                            )
                            break
                        # Else, try next joiner

    # noinspection PyMethodMayBeStatic
    def pop_edge(self):
        """ Called when leaving an edge that has been navigated """
        return False

    # noinspection PyMethodMayBeStatic
    def done(self):
        """ Called when the whole navigation is done """
        pass

    def result(self):
        return self._parts


class PackedDawgDictionary:

    """ Encapsulates a DAWG dictionary that is initialized from a packed
        binary file on disk and navigated as a byte buffer. """

    def __init__(self):
        # The packed byte buffer
        self._b = None
        self._vocabulary = None
        self._root_offset = 0
        self._encoding = dict()

    def load(self, fname):
        """ Load a packed DAWG from a binary file """
        if self._b is not None:
            # Already loaded
            return
        # Quickly gulp the file contents into the byte buffer
        with open(fname, mode='rb') as fin:
            self._b = bytearray(fin.read())
        # Check the signature
        assert self._b[0:12] == b"ReynirDawg!\n"
        len_voc, = struct.Struct("<L").unpack_from(self._b, 12)
        self._vocabulary = self._b[16:16 + len_voc].decode("utf-8")
        self._root_offset = 16 + len_voc
        # Assemble a decoding dictionary where encoded indices are mapped to
        # characters, eventually with a suffixed vertical bar '|' to denote finality
        self._encoding = {
            i : c for i, c in enumerate(self._vocabulary)
        }
        self._encoding.update(
            {
                i | 0x80 : c + u"|"
                for i, c in enumerate(self._vocabulary)
            }
        )

    def find(self, word):
        """ Look for a word in the graph, returning True if it is found or False if not """
        nav = FindNavigator(word)
        self.navigate(nav)
        return nav.is_found()

    def __contains__(self, word):
        """ Enable simple lookup syntax: "word" in dawgdict """
        return self.find(word)

    def slice_compound_word(self, word):
        """ Attempt to slice an unknown word into parts, where each part is
            a valid word form in itself, and the parts form a valid compound word. """
        nav = CompoundNavigator(self, word)
        self.navigate(nav)
        w = nav.result()
        # We get back a list of lists, i.e. all possible compound word combinations
        # where each combination is a list of word parts. We return
        # the combination with the longest last part and the shortest overall
        # number of parts.
        w.sort(key = lambda x : (len(x[-1]), -len(x)), reverse = True)
        # Cut out interpretations that end with closed word categories,
        # i.e. conjunctions and prepositions
        # gr, st, abfn, nhm, fs?
        return w[0] if w else None

    def navigate(self, nav):
        """ A generic function to navigate through the DAWG under
            the control of a navigation object.

            The navigation object should implement the following interface:

            def push_edge(firstchar)
                returns True if the edge should be entered or False if not
            def accepting()
                returns False if the navigator does not want more characters
            def accepts(newchar)
                returns True if the navigator will accept and 'eat' the new character
            def accept(matched, final)
                called to inform the navigator of a match and whether it is a final word
            def pop_edge()
                called when leaving an edge that has been navigated; returns False
                if there is no need to visit other edges
            def done()
                called when the navigation is completed
        """
        if self._b is None:
            # No graph: no navigation
            nav.done()
        else:
            PackedNavigation(nav, self._b, self._root_offset, self._encoding).go()


class PackedNavigation:

    """ Manages the state for a navigation while it is in progress """

    # The structure used to decode an edge offset from bytes
    _UINT32 = struct.Struct("<L")

    # Dictionary of edge iteration caches, keyed by byte buffer
    _iter_caches = dict()

    def __init__(self, nav, b, root_offset, encoding):
        # Store the associated navigator
        self._nav = nav
        # The DAWG bytearray
        self._b = b
        self._root_offset = root_offset
        self._encoding = encoding
        if id(b) in self._iter_caches:
            # We already have a cache associated with this byte buffer
            self._iter_cache = self._iter_caches[id(b)]
        else:
            # Create a fresh cache for this byte buffer
            self._iter_cache = self._iter_caches[id(b)] = dict()

    def _iter_from_node(self, offset):
        """ A generator for yielding prefixes and next node offset along an edge
            starting at the given offset in the DAWG bytearray """
        b = self._b
        encoding = self._encoding
        num_edges = b[offset] & 0x7f
        offset += 1
        for _ in range(num_edges):
            len_byte = b[offset] & 0x7f
            offset += 1
            prefix = u"".join(encoding[b[offset + j]] for j in range(len_byte))
            offset += len_byte
            if b[offset - 1] & 0x80:
                # The last character of the prefix had a final marker: nextnode is 0
                nextnode = 0
            else:
                # Read the next node offset
                nextnode, = self._UINT32.unpack_from(b, offset)  # Tuple of length 1, i.e. (n, )
                offset += 4
            yield prefix, nextnode

    def _make_iter_from_node(self, offset):
        """ Return an iterator over the prefixes and next node pointers
            of the edge at the given offset. If this is the first time
            that the edge is iterated, cache its unpacked contents
            in a dictionary for quicker subsequent iteration. """
        try:
            d = self._iter_cache[offset]
        except KeyError:
            d = {
                prefix : nextnode
                for prefix, nextnode in self._iter_from_node(offset)
            }
            self._iter_cache[offset] = d
        return d.items()

    def _navigate_from_node(self, offset, matched):
        """ Starting from a given node, navigate outgoing edges """
        # Go through the edges of this node and follow the ones
        # okayed by the navigator
        nav = self._nav
        for prefix, nextnode in self._make_iter_from_node(offset):
            if nav.push_edge(prefix[0]):
                # This edge is a candidate: navigate through it
                self._navigate_from_edge(prefix, nextnode, matched)
                if not nav.pop_edge():
                    # Short-circuit and finish the loop if pop_edge() returns False
                    break

    def _navigate_from_edge(self, prefix, nextnode, matched):
        """ Navigate along an edge, accepting partial and full matches """
        # Go along the edge as long as the navigator is accepting
        b = self._b
        lenp = len(prefix)
        j = 0
        nav = self._nav
        while j < lenp and nav.accepting():
            # See if the navigator is OK with accepting the current character
            if not nav.accepts(prefix[j]):
                # Nope: we're done with this edge
                return
            # So far, we have a match: add a letter to the matched path
            matched += prefix[j]
            j += 1
            # Check whether the next prefix character is a vertical bar, denoting finality
            final = False
            if j < lenp:
                if prefix[j] == "|":
                    final = True
                    j += 1
            elif nextnode == 0 or b[nextnode] & 0x80:
                # If we're at the final char of the prefix and the next node is final,
                # set the final flag as well (there is no trailing vertical bar in this case)
                final = True
            # Tell the navigator where we are
            nav.accept(matched, final)
        # We're done following the prefix for as long as it goes and
        # as long as the navigator was accepting
        if j < lenp:
            # We didn't complete the prefix, so the navigator must no longer
            # be interested (accepting): we're done
            return
        if nextnode != 0 and nav.accepting():
            # Gone through the entire edge and still have rack letters left:
            # continue with the next node
            self._navigate_from_node(nextnode, matched)

    def go(self):
        """ Perform the navigation using the given navigator """
        # The ship is ready to go
        if self._nav.accepting():
            # Leave shore and navigate the open seas
            self._navigate_from_node(self._root_offset, "")
        self._nav.done()

