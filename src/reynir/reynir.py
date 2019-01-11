"""

    Reynir: Natural language processing for Icelandic

    High-level wrapper for the Reynir tokenizer, parser and reducer

    Copyright (c) 2018 Miðeind ehf.
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


    This module implements a high-level interface to the Reynir
    tokenizer, parser and reducer for parsing Icelandic text into
    trees.

"""

import time
from threading import Lock
from collections import namedtuple

from tokenizer import correct_spaces, paragraphs, mark_paragraphs

from .bintokenizer import tokenize as bin_tokenize
from .fastparser import Fast_Parser, ParseError
from .reducer import Reducer
from .cache import cached_property
from .matcher import Simplifier


# The Sentence.terminals attribute returns a list of Terminal objects

Terminal = namedtuple(
    "Terminal",
    ("text", "lemma", "category", "variants", "index")
)


class _Sentence:

    """ A container for a sentence that has been extracted from the
        tokenizer. The sentence can be explicitly parsed by calling
        sentence.parse(). After parsing, a number of query functions
        are available on the parse tree. """

    def __init__(self, job, s):
        self._job = job
        self._s = s
        self._len = len(s)
        assert self._len > 0  # Input should be already sanitized
        self._err_index = None
        self._tree = self._simplified_tree = None
        self._num = None  # Number of possible combinations
        self._score = None  # Score of best parse tree
        self._terminals = None  # Cached terminals
        if self._job.parse_immediately:
            # We want an immediate parse of the sentence
            self.parse()

    def __len__(self):
        """ Return the number of tokens in the sentence """
        return self._len

    def parse(self):
        """ Parse the sentence """
        if self._num is not None:
            # Already parsed
            return self._num > 0
        job = self._job
        num = 0
        score = 0
        tree = None
        try:
            # Invoke the parser on the sentence tokens
            tree, num, score = job.parse(self._s)
        except ParseError as e:
            self._err_index = self._len - 1 if e.token_index is None else e.token_index
        self._tree = tree
        if tree is None:
            self._simplified_tree = None
        else:
            # Create a simplified tree as well
            s = Simplifier(self._s)
            s.go(tree)
            self._simplified_tree = s.tree
        self._num = num
        self._score = score
        return num > 0

    @property
    def err_index(self):
        """ Return the index of the error token, if an error occurred;
            otherwise None """
        return self._err_index

    @property
    def tokens(self):
        """ Return the tokens in the sentence """
        return self._s

    @property
    def combinations(self):
        """ Return the number of different parse tree combinations for the sentence,
            or 0 if no parse tree was found, or None if the sentence hasn't been parsed """
        return self._num

    @property
    def score(self):
        """ The score of the best parse tree for the sentence """
        return self._score

    @property
    def tree(self):
        """ Return the simplified parse tree, or None if the sentence hasn't been parsed """
        return self._simplified_tree

    @property
    def deep_tree(self):
        """ Return the original deep tree, as constructed by the parser, corresponding
            directly to grammar nonterminals and terminals """
        return self._tree

    @property
    def flat_tree(self):
        """ Return a flat text representation of the simplified parse tree """
        return None if self.tree is None else self.tree.flat

    @cached_property
    def text(self):
        """ Return a raw text representation of the sentence,
            with spaces between all tokens """
        return " ".join(t.txt for t in self._s if t.txt)

    @property
    def tidy_text(self):
        """ Return a [more] correctly spaced text representation of the sentence """
        if self.tree is None:
            # Not parsed (yet)
            txt = self.text
        else:
            # Use the terminal text representation - it's got fancy em/en-dashes and stuff
            txt = " ".join(t.text for t in self.terminals)
        return correct_spaces(txt)

    @property
    def terminals(self):
        """ Return a list of tuples, one for each terminal in the sentence.
            The tuples contain the original text of the token that matched
            the terminal, the associated word lemma, the category, and a set
            of variants (case, number, gender, etc.) """
        if self.tree is None:
            # Must parse the sentence first, without errors
            return None
        if self._terminals is not None:
            # Already calculated and cached
            return self._terminals
        # Generate the terminal list from the parse tree
        self._terminals = [
            Terminal(d.text, d.lemma, d.tcat, d.all_variants, d.index)
            for d in self.terminal_nodes
        ]
        return self._terminals

    @cached_property
    def terminal_nodes(self):
        """ Return a list of the terminal nodes within the parse tree
            for this sentence """
        if self.tree is None:
            return None
        return [d for d in self.tree.descendants if d.is_terminal]

    @property
    def lemmas(self):
        """ Convenience property to return the lemmas only """
        t = self.terminals
        return None if t is None else [terminal[1] for terminal in t]

    @property
    def ifd_tags(self):
        """ Return a list of Icelandic Frequency Dictionary (IFD) tags for
            the terminals/tokens in this sentence. """
        if self.tree is None:
            return None
        # Flatten the ifd_tags lists for the individual nodes
        # (nonterminal nodes return an empty list in the ifd_tags property)
        return [ifd_tag for d in self.tree.descendants for ifd_tag in d.ifd_tags]

    def __str__(self):
        return self.text


class _Paragraph:

    """ Encapsulates a paragraph that contains sentences """

    def __init__(self, job, p):
        self._job = job
        self._p = p

    def sentences(self):
        """ Yield the sentences within the paragraph, nicely wrapped """
        for _, sent in self._p:
            yield self._job._create_sentence(sent)

    def __iter__(self):
        """ Allow easy iteration of sentences within this paragraph """
        return iter(self.sentences())


class _Job:

    """ A parsing job object, allowing incremental parsing of text
        by paragraph and/or sentence.
    """

    def __init__(self, reynir, tokens, parse):
        self._r = reynir
        self._parser = self._r.parser
        self._reducer = self._r.reducer
        self._tokens = tokens
        self._parse_time = 0.0
        self._parse = parse
        self._num_sent = 0
        self._num_parsed = 0
        self._num_tokens = 0
        self._num_combinations = 0
        self._total_ambig = 0.0
        self._total_tokens = 0

    def _add_sentence(self, s, num, parse_time):
        """ Add a processed sentence to the statistics """
        slen = len(s)
        self._num_sent += 1
        self._num_tokens += slen
        if num > 0:
            # The sentence was parsed successfully
            self._num_parsed += 1
            self._num_combinations += num
            ambig_factor = num ** (1 / slen)
            self._total_ambig += ambig_factor * slen
            self._total_tokens += slen
        # Accumulate the time spent on parsing
        self._parse_time += parse_time

    def _create_sentence(self, s):
        """ Create a fresh _Sentence object """
        return self._r.create_sentence(self, s)

    @property
    def parse_immediately(self):
        """ Return True if sentences in the job should be parsed immediately """
        return self._parse

    def paragraphs(self):
        """ Yield the paragraphs from the token stream """
        for p in paragraphs(self._tokens):
            yield _Paragraph(self, p)

    def sentences(self):
        """ Yield the sentences from the token stream """
        for p in self.paragraphs():
            yield from p.sentences()

    def parse(self, tokens):
        """ Parse the token sequence, returning a parse tree,
            the number of trees in the parse forest, and the
            score of the best tree """
        num = 0
        score = 0
        t0 = time.time()
        try:
            forest = self.parser.go(tokens)  # May raise ParseError
            if forest is not None:
                num = Fast_Parser.num_combinations(forest)
                if num > 1:
                    # Reduce the parse forest to a single
                    # "best" (highest-scoring) parse tree
                    forest, score = self.reduce(forest)
            return forest, num, score
        finally:
            # Accumulate statistics in the job object
            self._add_sentence(tokens, num, time.time() - t0)

    def reduce(self, forest):
        """ Find the best parse tree and return it along with its score """
        return self.reducer.go_with_score(forest)

    def __iter__(self):
        """ Allow easy iteration of sentences within this job """
        return iter(self.sentences())

    @property
    def parser(self):
        """ The job's associated parser object """
        return self._parser

    @property
    def reducer(self):
        """ The job's associated reducer object """
        return self._reducer

    @property
    def num_tokens(self):
        """ Total number of tokens in sentences submitted to this job """
        return self._num_tokens

    @property
    def num_sentences(self):
        """ Total number of sentences submitted to this job """
        return self._num_sent

    @property
    def num_parsed(self):
        """ Total number of sentences successfully parsed within this job """
        return self._num_parsed

    @property
    def num_combinations(self):
        """ Sum of the total number of parse tree combinations for sentences within this job """
        return self._num_combinations

    @property
    def ambiguity(self):
        """ The weighted average total ambiguity of parsed sentences within this job """
        return (
            (self._total_ambig / self._total_tokens) if self._total_tokens > 0 else 1.0
        )

    @property
    def parse_time(self):
        """ Total time spent on parsing during this job, in seconds """
        return self._parse_time


class Reynir:

    """ Utility class to tokenize and parse text, organized
        as a sequence of sentences or alternatively as paragraphs
        of sentences. Typical usage:

        r = Reynir()
        job = r.submit(my_text)
        # Iterate through sentences and parse each one:
        for sent in job:
            if sent.parse():
                # sentence parsed successfully
                # do something with sent.tree
                print(sent.tree)
            else:
                # an error occurred in the parse
                # the error token index is at sent.err_index
                pass
        # Alternatively, split into paragraphs first:
        job = r.submit(my_text)
        for p in job.paragraphs(): # Yields paragraphs
            for sent in p.sentences(): # Yields sentences
                if sent.parse():
                    # sentence parsed successfully
                    # do something with sent.tree
                    print(sent.tree)
                else:
                    # an error occurred in the parse
                    # the error token index is at sent.err_index
                    pass
        # After parsing all sentences in a job, the following
        # statistics are available:
        num_sentences = job.num_sentences   # Total number of sentences
        num_parsed = job.num_parsed         # Thereof successfully parsed
        ambiguity = job.ambiguity           # Average ambiguity factor
        parse_time = job.parse_time         # Elapsed time since job was created

    """

    _parser = None
    _reducer = None
    _lock = Lock()

    def __init__(self):
        pass

    def tokenize(self, text):
        """ Call the tokenizer (overridable in derived classes) """
        return bin_tokenize(text)

    def create_sentence(self, job, s):
        """ Override this in derived classes to modify how sentences
            are created or postprocessed """
        return _Sentence(job, s)

    @property
    def parser(self):
        """ Return the parser instance to be used """
        with self._lock:
            if Reynir._parser is None:
                # Initialize a singleton instance of the parser and the reducer.
                # Both classes are re-entrant and thread safe.
                Reynir._parser = Fast_Parser()
                Reynir._reducer = Reducer(Reynir._parser.grammar)
            return Reynir._parser

    @property
    def reducer(self):
        """ Return the reducer instance to be used """
        # Should always retrieve the parser attribute first
        assert Reynir._reducer is not None
        return Reynir._reducer

    def submit(self, text, parse=False, *, split_paragraphs=False):
        """ Submit a text to the tokenizer and parser, yielding a job object.
            The paragraphs and sentences of the text can then be iterated
            through via the job object. If parse is set to True, the
            sentences are automatically parsed before being returned.
            Otherwise, they need to be explicitly parsed by calling
            sent.parse(). This is a more incremental, asynchronous
            approach than Reynir.parse(). """
        if split_paragraphs:
            # Original text consists of paragraphs separated by newlines:
            # insert paragraph separators before tokenization
            text = mark_paragraphs(text)
        tokens = self.tokenize(text)
        return _Job(self, tokens, parse=parse)

    def parse(self, text):
        """ Convenience function to parse text synchronously and return
            a summary of all contained sentences. """
        tokens = self.tokenize(text)
        job = _Job(self, tokens, parse=True)
        # Iterating through the sentences in the job causes
        # them to be parsed and their statistics collected
        sentences = [sent for sent in job]
        return dict(
            sentences=sentences,
            num_sentences=job.num_sentences,
            num_parsed=job.num_parsed,
            num_tokens=job.num_tokens,
            ambiguity=job.ambiguity,
            parse_time=job.parse_time,
        )

    def parse_single(self, sentence):
        """ Convenience function to parse a single sentence only """
        tokens = self.tokenize(sentence)
        job = _Job(self, tokens, parse=True)
        # Raises StopIteration if no sentence was parsed
        return next(iter(job))

    @classmethod
    def cleanup(cls):
        """ Discard memory resources held by the Reynir class object """
        cls._reducer = None
        if cls._parser:
            Fast_Parser.discard_grammar()
            cls._parser.cleanup()
            cls._parser = None
