"""
    Reynir: Natural language processing for Icelandic

    Settings module

    Copyright (c) 2018 Miðeind ehf.

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


    This module reads and interprets the ReynirPackage.conf or Reynir.conf
    configuration file. The file can include other files using the $include
    directive, making it easier to arrange configuration sections into logical
    and manageable pieces.

    Sections are identified like so: [ section_name ]

    Comments start with # signs.

    Sections are interpreted by section handlers.

"""

import os
import codecs
import locale
import threading

from contextlib import contextmanager, closing
from collections import defaultdict
from threading import Lock
from pkg_resources import resource_stream


# The sorting locale used by default in the changedlocale function
_DEFAULT_SORT_LOCALE = ("IS_is", "UTF-8")

# A set of all valid verb argument cases
_ALL_CASES = frozenset(("nf", "þf", "þgf", "ef"))
_ALL_GENDERS = frozenset(("kk", "kvk", "hk"))
_ALL_NUMBERS = frozenset(("et", "ft"))
_SUBCLAUSES = frozenset(("nh", "mnh", "falls"))
_REFLPRN = {"sig": "sig_hk_et_þf", "sér": "sig_hk_et_þgf", "sín": "sig_hk_et_ef"}


# Magic stuff to change locale context temporarily


@contextmanager
def changedlocale(new_locale=None):
    """ Change locale for collation temporarily within a context (with-statement) """
    # The newone locale parameter should be a tuple: ('is_IS', 'UTF-8')
    old_locale = locale.getlocale(locale.LC_COLLATE)
    try:
        locale.setlocale(locale.LC_COLLATE, new_locale or _DEFAULT_SORT_LOCALE)
        yield locale.strxfrm  # Function to transform string for sorting
    finally:
        locale.setlocale(locale.LC_COLLATE, old_locale)


def sort_strings(strings, loc=None):
    """ Sort a list of strings using the specified locale's collation order """
    # Change locale temporarily for the sort
    with changedlocale(loc) as strxfrm:
        return sorted(strings, key=strxfrm)


class ConfigError(Exception):

    """ Exception class for configuration errors """

    def __init__(self, s):
        super().__init__(s)
        self.fname = None
        self.line = 0

    def set_pos(self, fname, line):
        """ Set file name and line information, if not already set """
        if not self.fname:
            self.fname = fname
            self.line = line

    def __str__(self):
        """ Return a string representation of this exception """
        s = Exception.__str__(self)
        if not self.fname:
            return s
        return "File {0}, line {1}: {2}".format(self.fname, self.line, s)


class LineReader:

    """ Read lines from a text file, recognizing $include directives """

    def __init__(self, fname, outer_fname=None, outer_line=0):
        self._fname = fname
        self._line = 0
        self._inner_rdr = None
        self._outer_fname = outer_fname
        self._outer_line = outer_line

    def fname(self):
        """ The name of the file being read """
        return self._fname if self._inner_rdr is None else self._inner_rdr.fname()

    def line(self):
        """ The number of the current line within the file """
        return self._line if self._inner_rdr is None else self._inner_rdr.line()

    def lines(self):
        """ Generator yielding lines from a text file """
        self._line = 0
        try:
            if __package__:
                stream = resource_stream(__name__, self._fname)
            else:
                stream = open(self._fname, "rb")
            with stream as inp:
                # Read config file line-by-line from the package resources
                for b in inp:
                    # We get byte strings; convert from utf-8 to strings
                    s = b.decode("utf-8")
                    self._line += 1
                    # Check for include directive: $include filename.txt
                    if s.startswith("$") and s.lower().startswith("$include "):
                        iname = s.split(maxsplit=1)[1].strip()
                        # Do some path magic to allow the included path
                        # to be relative to the current file path, or a
                        # fresh (absolute) path by itself
                        head, _ = os.path.split(self._fname)
                        iname = os.path.join(head, iname)
                        rdr = self._inner_rdr = LineReader(
                            iname, self._fname, self._line
                        )
                        for incl_s in rdr.lines():
                            yield incl_s
                        self._inner_rdr = None
                    else:
                        yield s
        except (IOError, OSError):
            if self._outer_fname:
                # This is an include file within an outer config file
                c = ConfigError(
                    "Error while opening or reading include file '{0}'".format(
                        self._fname
                    )
                )
                c.set_pos(self._outer_fname, self._outer_line)
            else:
                # This is an outermost config file
                c = ConfigError(
                    "Error while opening or reading config file '{0}'".format(
                        self._fname
                    )
                )
            raise c


class VerbObjects:

    """ Wrapper around dictionary of verbs and their objects,
        initialized from the config file """

    # Dictionary of verbs by object (argument) number, 0, 1 or 2
    # Verbs can control zero, one or two arguments (noun phrases),
    # where each argument must have a particular case
    VERBS = [set(), defaultdict(list), defaultdict(list)]
    # Dictionary of verb forms with associated scores
    # The key is the normal form of the verb + the associated cases,
    # separated by underscores, e.g. "vera_þgf_ef"
    SCORES = dict()
    # Dictionary of verbs where, for each verb + argument cases, we store a set of
    # preposition_case keys, i.e. "frá_þgf"
    PREPOSITIONS = defaultdict(set)

    # dict { verb + argument cases : verb particle}
    VERB_PARTICLES = defaultdict(set)

    VERBS_ERRORS = [set(), defaultdict(dict), defaultdict(dict)]
    VERB_PARTICLES_ERRORS = defaultdict(dict)
    PREPOSITIONS_ERRORS = defaultdict(dict)
    WRONG_VERBS = defaultdict(list)

    @staticmethod
    def add(verb, args, prepositions, particle, score):
        """ Add a verb and its objects (arguments). Called from the config file handler. """
        la = len(args)
        if la > 2:
            raise ConfigError("A verb can have 0-2 arguments; {0} given".format(la))
        if la:
            for kind in args:
                if kind not in _ALL_CASES and kind not in _SUBCLAUSES:
                    if kind in _REFLPRN:
                        kind = _REFLPRN[kind]
                    else:
                        spl = kind.split("_")
                        if spl[-1] not in _ALL_CASES and spl[-1] != "gr":
                            raise ConfigError(
                                "Invalid verb argument: '{0}'".format(kind)
                            )
            # Append a possible argument list
            arglists = VerbObjects.VERBS[la][verb]
            if args not in arglists:
                # Avoid adding the same argument list twice
                arglists.append(args)
        else:
            # Note that the verb can be argument-free
            VerbObjects.VERBS[0].add(verb)
        # Store the score, if nonzero
        verb_with_cases = "_".join([verb] + args)
        if score != 0:
            VerbObjects.SCORES[verb_with_cases] = score
        # prepositions is a list of tuples: (preposition, case/kind), e.g. ("í", "þgf") or ("í", "falls")
        d = VerbObjects.PREPOSITIONS[verb_with_cases]
        for p, kind in prepositions:
            # Add a "bare" preposition, such as "í"
            d.add(p)
            # Add a full form with case or argument kind, such as "í_þgf", or "í_nh"
            d.add(p + "_" + kind)
        if particle:
            VerbObjects.VERB_PARTICLES[verb_with_cases] = particle

    @staticmethod
    def add_error(verb, args, prepositions, particle, corr):
        """ Take note of a verb object specification with an $error pragma """
        corrlist = corr.split(",")
        errlist = corrlist[0].split("-")
        errkind = errlist[0].strip()
        verb_with_cases = "_".join([verb] + args)
        if errkind == "OBJ":
            arglists = VerbObjects.VERBS_ERRORS[len(args)][verb]
            arglists[verb_with_cases] = corr
        elif errkind == "PP":
            d = VerbObjects.PREPOSITIONS_ERRORS[verb_with_cases]
            for p, kind in prepositions:
                d[p] = corr
                d[p + "_" + kind] = corr
        elif errkind == "PRTCL":
            # !!! TODO: Parse the corr string
            VerbObjects.VERB_PARTICLES_ERRORS[verb_with_cases][particle] = corr
        elif errkind == "ALL":
            # !!! TODO: Implement this (store specification of a
            # !!! TODO: replacement of the entire construct)
            pass
        elif errkind == "PREDS":
            # !!! TODO: Implement this
            pass
        elif errkind == "WRONG":
            wrong_kind = errlist[1].strip()
            if wrong_kind == "VERB":
                # Wrong verb, must point to completely different verb + args
                VerbObjects.WRONG_VERBS[verb_with_cases] = corr
            elif wrong_kind == "OBJ":
                # !!! TODO: Implement this
                pass
            else:
                raise ConfigError("Unknown type of WRONG-XXX in $error pragma")
        else:
            raise ConfigError("Unknown error type in $error pragma: '{0}'".format(errkind))

    @staticmethod
    def verb_matches_preposition(verb_with_cases, prep_with_case):
        """ Does the given preposition with the given case fit the verb? """
        # if Settings.DEBUG:
        #    print("verb_matches_preposition: verb {0}, prep {1}, verb found {2}, prep found {3}"
        #        .format(verb_with_cases, prep_with_case,
        #            verb_with_cases in VerbObjects.PREPOSITIONS,
        #            verb_with_cases in VerbObjects.PREPOSITIONS and
        #            prep_with_case in VerbObjects.PREPOSITIONS[verb_with_cases]))
        return (
            verb_with_cases in VerbObjects.PREPOSITIONS
            and prep_with_case in VerbObjects.PREPOSITIONS[verb_with_cases]
        )

    @staticmethod
    def verb_matches_particle(verb_with_cases, particle):
        """ Does the given particle fit the verb? """
        return (
            verb_with_cases in VerbObjects.VERB_PARTICLES
            and particle in VerbObjects.VERB_PARTICLES[verb_with_cases]
        )


class VerbSubjects:

    """ Wrapper around dictionary of verbs and their subjects,
        initialized from the config file """

    # Dictionary of verbs and their associated set of subject cases
    VERBS = defaultdict(set)
    _CASE = "þgf"  # Default subject case
    # dict { verb : (wrong_case, correct_case) }
    VERBS_ERRORS = defaultdict(dict)

    @staticmethod
    def set_case(case):
        """ Set the case of the subject for the following verbs """
        # if case not in { "þf", "þgf", "ef", "none", "lhþt" }:
        #     raise ConfigError("Unknown verb subject case '{0}' in verb_subjects".format(case))
        VerbSubjects._CASE = case

    @staticmethod
    def add(verb):
        """ Add a verb and its arguments. Called from the config file handler. """
        VerbSubjects.VERBS[verb].add(VerbSubjects._CASE)

    @staticmethod
    def add_error(verb, corr):
        """ Add a verb and the correct case. Called from the config file handler. """
        corrlist = corr.split(",")
        errlist = corrlist[0].split("-")
        errkind = errlist[0].strip()
        if errkind == "SUBJ":
            if len(errlist) != 2:
                raise ConfigError("Expected $error(SUBJ-XXX, ...)")
            subj_type = errlist[1].strip()
            if subj_type == "CASE":
                corr_case = corrlist[1].strip()
                VerbSubjects.VERBS_ERRORS[verb][VerbSubjects._CASE] = corr_case
            else:
                raise ConfigError("Unknown subject specification: 'SUBJ-{0}'".format(subj_type))
        else:
            raise ConfigError("Unknown error type in $error pragma: '{0}'".format(errkind))

    @staticmethod
    def is_strictly_impersonal(verb):
        """ Returns True if the given verb is only impersonal, i.e. if it appears
            with an $error() pragma in the subject = nf section of verb_subjects
            and cannot be used with a nominative subject: ?'ég dreymdi þig' """
        return "nf" in VerbSubjects.VERBS_ERRORS.get(verb, set())


class Prepositions:

    """ Wrapper around dictionary of prepositions, initialized from the config file """

    # Dictionary of prepositions: preposition -> { set of cases that it controls }
    PP = defaultdict(set)
    # Prepositions that can be followed by an infinitive verb phrase
    # 'Beiðnin um að handtaka manninn var send lögreglunni'
    PP_NH = set()
    # A dictionary containing information from $error() pragmas associated
    # with the preposition. Each entry is again a dict of {case: error} specifications,
    # where each error spec is usually a tuple.
    PP_ERRORS = defaultdict(dict)

    @staticmethod
    def add(prep, case, nh):
        """ Add a preposition and its case. Called from the config file handler. """
        Prepositions.PP[prep].add(case)
        if nh:
            Prepositions.PP_NH.add(prep)

    @staticmethod
    def add_error(prep, case, corr):
        """ Add an error correction entry for a preposition and a case.
            An error correction entry is usually a tuple. """
        Prepositions.PP_ERRORS[prep][case] = corr


class AdjectiveTemplate:

    """ Wrapper around template list of adjective endings """

    # List of tuples: (ending, form_spec)
    ENDINGS = []

    @classmethod
    def add(cls, ending, form):
        """ Add an adjective ending and its associated form. """
        cls.ENDINGS.append((ending, form))


class DisallowedNames:

    """ Wrapper around list of disallowed person name forms """

    # Dictionary of name stems : sets of cases
    STEMS = {}

    @classmethod
    def add(cls, name, cases):
        """ Add an adjective ending and its associated form. """
        cls.STEMS[name] = set(cases)


class UndeclinableAdjectives:

    """ Wrapper around list of undeclinable adjectives """

    # Set of adjectives
    ADJECTIVES = set()

    @classmethod
    def add(cls, wrd):
        """ Add an adjective """
        cls.ADJECTIVES.add(wrd)


class StaticPhrases:

    """ Wrapper around dictionary of static phrases, initialized from the config file """

    # Default meaning for static phrases
    MEANING = ("ao", "frasi", "-")
    # Dictionary of the static phrases with their meanings
    MAP = {}
    # Dictionary of the static phrases with their IFD tags and lemmas
    # { static_phrase : (tag string, lemma string) }
    DETAILS = {}
    # List of all static phrases and their meanings
    LIST = []
    # Parsing dictionary keyed by first word of phrase
    DICT = defaultdict(list)
    # Error dictionary, { phrase : (error_code, right_phrase, right_tag_string, right_lemma_string) }
    ERROR_DICT = {}

    @staticmethod
    def add(spec):
        """ Add a static phrase to the dictionary. Called from the config file handler. """
        parts = spec.split(",")
        if len(parts) not in {1, 3}:
            raise ConfigError("Static phrase must include IFD tag list and lemmas")

        phrase = parts[0].strip()

        if len(phrase) < 3 or phrase[0] != '"' or phrase[-1] != '"':
            raise ConfigError("Static phrase must be enclosed in double quotes")

        phrase = phrase[1:-1]

        if phrase in StaticPhrases.MAP:
            raise ConfigError(
                "Static phrase '{0}' is defined more than once".format(phrase)
            )

        # First add to phrase list
        ix = len(StaticPhrases.LIST)
        m = StaticPhrases.MEANING

        mtuple = (phrase, 0, m[0], m[1], phrase, m[2])

        # Append the phrase as well as its meaning in tuple form
        StaticPhrases.LIST.append((phrase, mtuple))

        # Add to the main phrase dictionary
        StaticPhrases.MAP[phrase] = mtuple

        # If details are supplied, store them
        if len(parts) == 3:
            tags = parts[1].strip()
            lemmas = parts[2].strip()
            if len(tags) < 3 or tags[0] != '"' or tags[-1] != '"':
                raise ConfigError("IFD tag list must be enclosed in double quotes")
            if len(lemmas) < 3 or lemmas[0] != '"' or lemmas[-1] != '"':
                raise ConfigError("Lemmas must be enclosed in double quotes")
            StaticPhrases.DETAILS[phrase] = (tags[1:-1], lemmas[1:-1])

        # Dictionary structure: dict { firstword: [ (restword_list, phrase_index) ] }

        # Split phrase into words
        wlist = phrase.split()
        # Dictionary is keyed by first word
        StaticPhrases.DICT[wlist[0]].append((wlist[1:], ix))

    @staticmethod
    def add_errors(words, error):
        # Dictionary structure : { phrase : (error_code, right_phrase, right_tag_string, right_lemma_string) }
        StaticPhrases.ERROR_DICT[words] = error

    @staticmethod
    def set_meaning(meaning):
        """ Set the default meaning for static phrases """
        StaticPhrases.MEANING = tuple(meaning)

    @staticmethod
    def get_meaning(ix):
        """ Return the meaning of the phrase with index ix """
        return [StaticPhrases.LIST[ix][1]]

    @staticmethod
    def get_length(ix):
        """ Return the length of the phrase with index ix """
        return len(StaticPhrases.LIST[ix][0].split())

    @staticmethod
    def lookup(phrase):
        """ Lookup an entire phrase """
        return StaticPhrases.MAP.get(phrase)

    @staticmethod
    def has_details(phrase):
        """ Return True if tag and lemma details are available for this phrase """
        return phrase in StaticPhrases.DETAILS

    @staticmethod
    def tags(phrase):
        """ Lookup a list of IFD tags for a phrase, if available """
        details = StaticPhrases.DETAILS.get(phrase)
        return None if details is None else details[0].split()

    @staticmethod
    def lemmas(phrase):
        """ Lookup a list of lemmas for a phrase, if available """
        details = StaticPhrases.DETAILS.get(phrase)
        return None if details is None else details[1].split()


class AmbigPhrases:

    """ Wrapper around dictionary of potentially ambiguous phrases, initialized from the config file """

    # List of tuples of ambiguous phrases and their word category lists
    LIST = []
    # Parsing dictionary keyed by first word of phrase
    DICT = defaultdict(list)
    # Error dictionary, { phrase : (error_code, right_phrase, right_parts_of_speech) }
    ERROR_DICT = defaultdict(list)

    @staticmethod
    def add(words, cats):
        """ Add an ambiguous phrase to the dictionary. Called from the config file handler. """

        # First add to phrase list
        ix = len(AmbigPhrases.LIST)

        # Append the phrase as well as its meaning in tuple form
        AmbigPhrases.LIST.append((words, cats))

        # Dictionary structure: dict { firstword: [ (restword_list, phrase_index) ] }
        AmbigPhrases.DICT[words[0]].append((words[1:], ix))

    @staticmethod
    def add_error(words, error):
        # Dictionary structure: dict { phrase : (error_code, right_phrase, right_parts_of_speech) }
        AmbigPhrases.ERROR_DICT[words] = error

    @staticmethod
    def get_cats(ix):
        """ Return the word categories for the phrase with index ix """
        return AmbigPhrases.LIST[ix][1]


class NoIndexWords:

    """ Wrapper around set of word stems and categories that should
        not be indexed """

    SET = set()  # Set of (stem, cat) tuples
    _CAT = "so"  # Default category

    # The word categories that are indexed in the words table
    CATEGORIES_TO_INDEX = frozenset(
        ("kk", "kvk", "hk", "person_kk", "person_kvk", "entity", "lo", "so")
    )

    @staticmethod
    def set_cat(cat):
        """ Set the category for the following word stems """
        NoIndexWords._CAT = cat

    @staticmethod
    def add(stem):
        """ Add a word stem and its category. Called from the config file handler. """
        NoIndexWords.SET.add((stem, NoIndexWords._CAT))


class Topics:

    """ Wrapper around topics, represented as a dict (name: set) """

    DICT = defaultdict(set)  # Dict of topic name: set
    ID = dict()  # Dict of identifier: topic name
    THRESHOLD = dict()  # Dict of identifier: threshold (as a float)
    _name = None

    @staticmethod
    def set_name(name):
        """ Set the topic name for the words that follow """
        a = name.split("|")
        Topics._name = tname = a[0].strip()
        identifier = a[1].strip() if len(a) > 1 else None
        if identifier is not None and not identifier.isidentifier():
            raise ConfigError(
                "Topic identifier ('{0}') must be a valid Python identifier"
                .format(identifier)
            )
        try:
            threshold = float(a[2].strip()) if len(a) > 2 else None
        except ValueError:
            raise ConfigError("Topic threshold must be a floating point number")
        Topics.ID[tname] = identifier
        Topics.THRESHOLD[tname] = threshold

    @staticmethod
    def add(word):
        """ Add a word stem and its category. Called from the config file handler. """
        if Topics._name is None:
            raise ConfigError(
                "Must set topic name (topic = X) before specifying topic words"
            )
        if "/" not in word:
            raise ConfigError(
                "Topic words must include a slash '/' and a word category"
            )
        cat = word.split("/", maxsplit=1)[1]
        if cat not in {
            "kk",
            "kvk",
            "hk",
            "lo",
            "so",
            "entity",
            "person",
            "person_kk",
            "person_kvk",
        }:
            raise ConfigError(
                "Topic words must be nouns, verbs, adjectives, entities or persons"
            )
        # Add to topic set, after replacing spaces with underscores
        Topics.DICT[Topics._name].add(word.replace(" ", "_"))


class AdjectivePredicates:

    """ A set of arguments and prepositions associated with
        adjectives, for instance 'tengdur þgf', typically read from
        the [adjective_predicates] section of AdjectivePredicates.conf """

    # dict { adjective lemma : set of possible argument cases }
    ARGUMENTS = defaultdict(set)
    # dict { adjective lemma : set of (preposition, case) }
    PREPOSITIONS = defaultdict(set)

    # dict { adjective lemma : [ (argument case, error code) ] }
    ERROR_DICT = defaultdict(list)

    # dict { adjective lemma : set of (preposition, case) }
    ERROR_PREPOSITIONS = defaultdict(set)

    @staticmethod
    def add(adj, arg, prepositions):
        if arg:
            # Add a case that is associated with an adjective
            AdjectivePredicates.ARGUMENTS[adj].update(arg)
        if prepositions:
            # Add a (preposition, case) tuple that is associated with an adjective
            AdjectivePredicates.PREPOSITIONS[adj].update(prepositions)

    @staticmethod
    def add_error(adj, arg, prepositions, error):
        if arg and error:
            for a in arg:
                AdjectivePredicates.ERROR_DICT[adj].append((a, error))
        if prepositions:
            AdjectivePredicates.ERROR_PREPOSITIONS[adj].update(prepositions)


class Morphemes:

    # dict { morpheme : [ preferred PoS ] }
    BOUND_DICT = {}
    # dict { morpheme : [ excluded PoS ] }
    FREE_DICT = {}

    @staticmethod
    def add(morph, boundlist, freelist):
        if boundlist:
            Morphemes.BOUND_DICT[morph] = boundlist
        else:
            raise ConfigError("A definition of allowed PoS is necessary with morphemes")
        # The freelist may be empty
        Morphemes.FREE_DICT[morph] = freelist


class Preferences:

    """ Wrapper around disambiguation hints, initialized from the config file """

    # Dictionary keyed by word containing a list of tuples (worse, better)
    # where each is a list of terminal prefixes
    DICT = defaultdict(list)

    @staticmethod
    def add(word, worse, better, factor):
        """ Add a preference to the dictionary. Called from the config file handler. """
        Preferences.DICT[word].append((worse, better, factor))

    @staticmethod
    def get(word):
        """ Return a list of (worse, better, factor) tuples for the given word """
        return Preferences.DICT.get(word, None)


class StemPreferences:

    """ Wrapper around stem disambiguation hints, initialized from the config file """

    # Dictionary keyed by word form containing a list of tuples (worse, better)
    # where each is a list word stems
    DICT = dict()

    @staticmethod
    def add(word, worse, better):
        """ Add a preference to the dictionary. Called from the config file handler. """
        if word in StemPreferences.DICT:
            raise ConfigError(
                "Duplicate stem preference for word form {0}".format(word)
            )
        StemPreferences.DICT[word] = (worse, better)

    @staticmethod
    def get(word):
        """ Return a list of (worse, better) tuples for the given word form """
        return StemPreferences.DICT.get(word, None)


class NounPreferences:

    """ Wrapper for noun preferences, i.e. to assign priorities to different
        noun stems that can have identical word forms. """

    # This is a dict of noun word forms, giving the relative priorities
    # of different genders
    DICT = defaultdict(dict)

    @staticmethod
    def add(word, worse, better):
        """ Add a preference to the dictionary. Called from the config file handler. """
        if worse not in _ALL_GENDERS or better not in _ALL_GENDERS:
            raise ConfigError("Noun priorities must specify genders (kk, kvk, hk)")
        d = NounPreferences.DICT[word]
        worse_score = d.get(worse)
        better_score = d.get(better)
        if worse_score is not None:
            if better_score is not None:
                raise ConfigError("Conflicting priorities for noun {0}".format(word))
            better_score = worse_score + 4
        elif better_score is not None:
            worse_score = better_score - 4
        else:
            worse_score = -2
            better_score = 2
        d[worse] = worse_score
        d[better] = better_score
        # print("Noun prefs for '{0}' are now {1}".format(word, d))


class NamePreferences:

    """ Wrapper around well-known person names, initialized from the config file """

    SET = set()

    @staticmethod
    def add(name):
        """ Add a preference to the dictionary. Called from the config file handler. """
        NamePreferences.SET.add(name)


class BinErrata:

    """ Wrapper around BÍN errata, initialized from the config file """

    DICT = dict()

    @staticmethod
    def add(stem, ordfl, fl):
        """ Add a BÍN fix. Used by bincompress.py when generating a new
            compressed vocabulary file. """
        BinErrata.DICT[(stem, ordfl)] = fl


class BinDeletions:

    """ Wrapper around BÍN deletions, initialized from the config file """

    SET = set()

    @staticmethod
    def add(stem, ordfl, fl):
        """ Add a BÍN fix. Used by bincompress.py when generating a new
            compressed vocabulary file. """
        BinDeletions.SET.add((stem, ordfl, fl))


# Global settings


class Settings:

    _lock = threading.Lock()
    loaded = False

    # Postgres SQL database server hostname and port
    DB_HOSTNAME = os.environ.get("GREYNIR_DB_HOST", "localhost")
    DB_PORT = os.environ.get("GREYNIR_DB_PORT", "5432")  # Default PostgreSQL port

    try:
        DB_PORT = int(DB_PORT)
    except ValueError:
        raise ConfigError(
            "Invalid environment variable value: DB_PORT = {0}".format(DB_PORT)
        )

    BIN_DB_HOSTNAME = os.environ.get("GREYNIR_BIN_DB_HOST", DB_HOSTNAME)
    BIN_DB_PORT = os.environ.get("GREYNIR_BIN_DB_PORT", DB_PORT)

    try:
        BIN_DB_PORT = int(BIN_DB_PORT)
    except ValueError:
        raise ConfigError(
            "Invalid environment variable value: BIN_DB_PORT = {0}".format(BIN_DB_PORT)
        )

    # Flask server host and port
    HOST = os.environ.get("GREYNIR_HOST", "localhost")
    PORT = os.environ.get("GREYNIR_PORT", "5000")
    try:
        PORT = int(PORT)
    except ValueError:
        raise ConfigError(
            "Invalid environment variable value: GREYNIR_PORT = {0}".format(PORT)
        )

    # Flask debug parameter
    DEBUG = False

    # Similarity server
    SIMSERVER_HOST = os.environ.get("SIMSERVER_HOST", "localhost")
    SIMSERVER_PORT = os.environ.get("SIMSERVER_PORT", "5001")
    try:
        SIMSERVER_PORT = int(SIMSERVER_PORT)
    except ValueError:
        raise ConfigError(
            "Invalid environment variable value: SIMSERVER_PORT = {0}".format(
                SIMSERVER_PORT
            )
        )

    # Configuration settings from the Reynir.conf file

    @staticmethod
    def _handle_settings(s):
        """ Handle config parameters in the settings section """
        a = s.lower().split("=", maxsplit=1)
        par = a[0].strip().lower()
        val = a[1].strip()
        if val.lower() == "none":
            val = None
        elif val.lower() == "true":
            val = True
        elif val.lower() == "false":
            val = False
        try:
            if par == "db_hostname":
                Settings.DB_HOSTNAME = Settings.BIN_DB_HOSTNAME = val
            elif par == "db_port":
                Settings.DB_PORT = Settings.BIN_DB_PORT = int(val)
            elif par == "bin_db_hostname":
                # Specify this after db_hostname if different from db_hostname
                Settings.BIN_DB_HOSTNAME = val
            elif par == "bin_db_port":
                # Specify this after db_port if different from db_port
                Settings.BIN_DB_PORT = int(val)
            elif par == "host":
                Settings.HOST = val
            elif par == "port":
                Settings.PORT = int(val)
            elif par == "simserver_host":
                Settings.SIMSERVER_HOST = val
            elif par == "simserver_port":
                Settings.SIMSERVER_PORT = int(val)
            elif par == "debug":
                Settings.DEBUG = bool(val)
            else:
                raise ConfigError("Unknown configuration parameter '{0}'".format(par))
        except ValueError:
            raise ConfigError("Invalid parameter value: {0} = {1}".format(par, val))

    @staticmethod
    def _handle_static_phrases(s):
        """ Handle static phrases in the settings section """
        error = False
        if "=" not in s:
            ix = s.rfind("$error(")  # Must be at the end
            if ix >= 0:
                error = True
                # A typical format is $error(error_code, right_phrase, right_parts_of_speech)
                e = s[ix + 7 :].lstrip().rstrip(" )").split(", ")
                s = s[:ix].strip()
            StaticPhrases.add(s)
            if error:
                StaticPhrases.add_errors(s.split(",")[0], e)
            return
        # Check for a meaning spec
        a = s.split("=", maxsplit=1)
        par = a[0].strip()
        val = a[1].strip()
        if par.lower() == "meaning":
            m = val.split()
            if len(m) == 3:
                StaticPhrases.set_meaning(m)
            else:
                raise ConfigError("Meaning in static_phrases should have 3 arguments")
        else:
            raise ConfigError(
                "Unknown configuration parameter '{0}' in static_phrases".format(par)
            )

    @staticmethod
    def _handle_abbreviations(s):
        """ Handle abbreviations in the settings section """
        # Not required in the ReynirPackage module
        # and should not occur in its settings files
        assert False

    @staticmethod
    def _handle_meanings(s):
        """ Handle additional word meanings in the settings section """
        # Not required in the ReynirPackage module
        # and should not occur in its settings files
        assert False

    @staticmethod
    def _handle_verb_objects(s):
        """ Handle verb object specifications in the settings section """
        # Format: verb [arg1] [arg2] [/preposition arg]... [$score(sc)]
        # arg can be nf, þf, þgf, ef, nh, falls, sig/sér/sín, bági_kk_ft_þf
        error = None

        # Start by handling the $score() pragma, if present
        score = 0
        ix = s.rfind("$score(")  # Must be at the end
        if ix >= 0:
            sc = s[ix:]
            s = s[0:ix].strip()
            if not sc.endswith(")"):
                raise ConfigError("Invalid score pragma; form should be $score(n)")
            # There is an associated score with this verb form, to be taken
            # into consideration by the reducer
            sc = sc[7:-1].strip()
            try:
                score = int(sc)
            except ValueError:
                raise ConfigError("Invalid score ('{0}') for verb form".format(sc))

        # Check for $error
        ix = s.rfind("$error(")
        if ix >= 0:
            if not s.endswith(")"):
                raise ConfigError("Invalid error pragma; form should be $error(...)")
            error = s[ix + 7 : -1].strip()
            s = s[0:ix].strip()
            if not error:
                raise ConfigError("Expected error specification in $error(...)")

        # Process particles, should only be one in each line
        particle = None
        ix = s.rfind("*")
        if ix >= 0:
            particle = s[ix:].strip()
            s = s[0:ix].strip()
            if " " in particle:
                raise ConfigError("Particle should only be one word")
            elif len(particle) < 2:
                raise ConfigError("Particle should be at least one letter")

        # Process preposition arguments, if any
        prepositions = []
        ap = s.split("/")
        s = ap[0]
        ix = 1
        while len(ap) > ix:
            # We expect something like 'af þgf', or possibly
            # 'fyrir_hönd þf' (where the underscore needs to be replaced by a space)
            p = ap[ix].strip()
            parg = p.split()
            if len(parg) != 2:
                raise ConfigError("Preposition should have exactly one argument")
            if parg[1] not in _ALL_CASES and parg[1] not in _SUBCLAUSES:
                if parg[1] in _REFLPRN:
                    parg[1] = _REFLPRN[parg[1]]
                spl = parg[1].split("_")
                if spl[-1] == "gr":
                    spl = spl[:-1]
                if spl[-1] not in _ALL_CASES:
                    raise ConfigError("Unknown argument for preposition")
            prepositions.append((parg[0].replace("_", " "), parg[1]))
            ix += 1

        # Process verb arguments
        a = s.split()
        if len(a) < 1 or len(a) > 3:
            raise ConfigError(
                "Verb should have zero, one or two arguments and an optional score"
            )
        verb = a[0]
        if not verb.isalpha():
            raise ConfigError("Verb '{0}' is not a valid word".format(verb))

        # Add to verb database
        if error:
            VerbObjects.add_error(verb, a[1:], prepositions, particle, error)
        else:
            VerbObjects.add(verb, a[1:], prepositions, particle, score)

    @staticmethod
    def _handle_verb_subjects(s):
        """ Handle verb subject specifications in the settings section """
        # Format: subject = [case] followed by verb list
        a = s.lower().split("=", maxsplit=1)
        if len(a) == 2:
            par = a[0].strip()
            val = a[1].strip()
            if par == "subject":
                VerbSubjects.set_case(val)
            else:
                raise ConfigError("Unknown setting '{0}' in verb_subjects".format(par))
            return
        assert len(a) == 1
        par = s.strip()
        # Check for $error
        e = None
        ix = par.rfind("$error(")
        if ix >= 0:
            if par[-1] != ")":
                raise ConfigError("Missing right parenthesis in $error()")
            e = par[ix + 7 : -1].strip()
            par = par[0:ix].strip()

        if e is not None:
            VerbSubjects.add_error(par, e)
        else:
            VerbSubjects.add(par)

    @staticmethod
    def _handle_undeclinable_adjectives(s):
        """ Handle list of undeclinable adjectives """
        s = s.lower().strip()
        if not s.isalpha():
            raise ConfigError(
                "Expected word but got '{0}' in undeclinable_adjectives".format(s)
            )
        UndeclinableAdjectives.add(s)

    @staticmethod
    def _handle_noindex_words(s):
        """ Handle no index instructions in the settings section """
        # Format: category = [cat] followed by word stem list
        a = s.lower().split("=", maxsplit=1)
        par = a[0].strip()
        if len(a) == 2:
            val = a[1].strip()
            if par == "category":
                NoIndexWords.set_cat(val)
            else:
                raise ConfigError("Unknown setting '{0}' in noindex_words".format(par))
            return
        assert len(a) == 1
        NoIndexWords.add(par)

    @staticmethod
    def _handle_topics(s):
        """ Handle topic specifications """
        # Format: name = [topic name] followed by word stem list in the form word/cat
        a = s.split("=", maxsplit=1)
        par = a[0].strip()
        if len(a) == 2:
            val = a[1].strip()
            if par.lower() == "topic":
                Topics.set_name(val)
            else:
                raise ConfigError("Unknown setting '{0}' in topics".format(par))
            return
        assert len(a) == 1
        Topics.add(par)

    @staticmethod
    def _handle_prepositions(s):
        """ Handle preposition specifications in the settings section """
        # Format: pw1 pw2... case [nh]  [$error(X)]
        error = False
        corr = None
        ix = s.rfind("$error(")  # Must be at the end
        if ix >= 0:
            # A typical format is $error(FORM-inn_á)
            error = True
            e = s[ix + 7 :].lstrip().rstrip(" )").split("-")
            if len(e) == 2:
                # Probably $error(FORM-xxx_xxx)
                corr = (e[0], " ".join(e[1].split("_")))
            elif len(e) == 1:
                # Probably $error(COMPOUND)
                corr = (e[0], None)
            else:
                raise ConfigError(
                    "$error() pragma should have the form XXX[-yyy] "
                    "where XXX is a category and yyy is a phrase"
                )
            s = s[:ix].strip()
        a = s.split()
        if len(a) < 2:
            raise ConfigError("Preposition must specify a word and a case argument")
        c = a[-1]  # Case or 'nh'
        nh = c == "nh"
        if nh:
            # This is a preposition that can be followed by an infinitive verb phrase:
            # 'Beiðnin um að handtaka manninn var send lögreglunni'
            a = a[:-1]
            if len(a) < 2:
                raise ConfigError(
                    "Preposition must specify a word, case and 'nh' argument"
                )
            c = a[-1]
        if c not in {"nf", "þf", "þgf", "ef"}:  # Not a valid case
            raise ConfigError("Preposition must have a case argument (nf/þf/þgf/ef)")
        pp = " ".join(a[:-1])  # Preposition, possibly multi-word
        Prepositions.add(pp, c, nh)
        if error:
            Prepositions.add_error(pp, c, corr)

    @staticmethod
    def _handle_preferences(s):
        """ Handle ambiguity preference hints in the settings section """
        # Format: word worse1 worse2... < better
        # If two less-than signs are used, the preference is even stronger (tripled)
        # If three less-than signs are used, the preference is super strong (nine-fold)
        factor = 9
        a = s.lower().split("<<<", maxsplit=1)
        if len(a) != 2:
            factor = 3
            a = s.lower().split("<<", maxsplit=1)
            if len(a) != 2:
                # Not doubled preference: try a normal one
                a = s.lower().split("<", maxsplit=1)
                factor = 1
        if len(a) != 2:
            raise ConfigError("Ambiguity preference missing less-than sign '<'")
        w = a[0].split()
        if len(w) < 2:
            raise ConfigError(
                "Ambiguity preference must have at least one 'worse' category"
            )
        b = a[1].split()
        if len(b) < 1:
            raise ConfigError(
                "Ambiguity preference must have at least one 'better' category"
            )
        Preferences.add(w[0], w[1:], b, factor)

    @staticmethod
    def _handle_stem_preferences(s):
        """ Handle stem ambiguity preference hints in the settings section """
        # Format: word worse1 worse2... < better
        a = s.lower().split("<", maxsplit=1)
        if len(a) != 2:
            raise ConfigError("Ambiguity preference missing less-than sign '<'")
        w = a[0].split()
        if len(w) < 2:
            raise ConfigError(
                "Ambiguity preference must have at least one 'worse' category"
            )
        b = a[1].split()
        if len(b) < 1:
            raise ConfigError(
                "Ambiguity preference must have at least one 'better' category"
            )
        StemPreferences.add(w[0], w[1:], b)

    @staticmethod
    def _handle_noun_preferences(s):
        """ Handle noun preference hints in the settings section """
        # Format: noun worse1 worse2... < better
        # The worse and better specifiers are gender names (kk, kvk, hk)
        a = s.lower().split("<", maxsplit=1)
        if len(a) != 2:
            raise ConfigError("Noun preference missing less-than sign '<'")
        w = a[0].split()
        if len(w) != 2:
            raise ConfigError("Noun preference must have exactly one 'worse' gender")
        b = a[1].split()
        if len(b) != 1:
            raise ConfigError("Noun preference must have exactly one 'better' gender")
        NounPreferences.add(w[0], w[1], b[0])

    @staticmethod
    def _handle_name_preferences(s):
        """ Handle well-known person names in the settings section """
        NamePreferences.add(s)

    @staticmethod
    def _handle_bin_errata(s):
        """ Handle changes to BÍN categories ('fl') """
        a = s.split()
        if len(a) != 3:
            raise ConfigError("Expected 'stem ordfl fl' fields in bin_errata section")
        stem, ordfl, fl = a
        if not ordfl.islower() or not fl.islower():
            raise ConfigError("Expected lowercase ordfl and fl fields in bin_errata section")
        BinErrata.add(stem, ordfl, fl)

    @staticmethod
    def _handle_bin_deletions(s):
        """ Handle deletions from BÍN, given as stem/ordfl/fl triples """
        a = s.split()
        if len(a) != 3:
            raise ConfigError("Expected 'stem ordfl fl' fields in bin_deletions section")
        stem, ordfl, fl = a
        if not ordfl.islower() or not fl.islower():
            raise ConfigError("Expected lowercase ordfl and fl fields in bin_deletions section")
        BinDeletions.add(stem, ordfl, fl)

    @staticmethod
    def _handle_ambiguous_phrases(s):
        """ Handle ambiguous phrase guidance in the settings section """
        # Format: "word1 word2..." cat1 cat2...
        error = False
        if s[0] != '"':
            raise ConfigError("Ambiguous phrase must be enclosed in double quotes")
        ix = s.rfind("$error(")  # Must be at the end
        if ix >= 0:
            error = True
            # A typical format is $error(error_code, right_phrase, right_parts_of_speech)
            e = s[ix + 7 :].lstrip().rstrip(" )").split(", ")
            s = s[:ix].strip()
        q = s.rfind('"')
        if q <= 0:
            raise ConfigError("Ambiguous phrase must be enclosed in double quotes")
        # Obtain a list of the words in the phrase
        words = s[1:q].strip().lower().split()
        # Obtain a list of the corresponding word categories
        cats = s[q + 1 :].strip().lower().split()
        if len(words) != len(cats):
            raise ConfigError(
                "Ambiguous phrase has {0} words but {1} categories".format(
                    len(words), len(cats)
                )
            )
        if len(words) < 2:
            raise ConfigError("Ambiguous phrase must contain at least two words")
        AmbigPhrases.add(words, cats)
        if error:
            AmbigPhrases.add_error(s[1:q].strip().lower(), e)

    @staticmethod
    def _handle_adjective_template(s):
        """ Handle the template for new adjectives in the settings section """
        # Format: adjective-ending bin-meaning
        a = s.split()
        if len(a) != 2:
            raise ConfigError(
                "Adjective template should have an ending and a form specifier"
            )
        AdjectiveTemplate.add(a[0], a[1])

    @staticmethod
    def _handle_disallowed_names(s):
        """ Handle disallowed person name forms from the settings section """
        # Format: Name-stem case1 case2...
        a = s.split()
        if len(a) < 2:
            raise ConfigError(
                "Disallowed names must specify a name and at least one case"
            )
        DisallowedNames.add(a[0], a[1:])

    @staticmethod
    def _handle_adjective_predicates(s):
        # Process preposition arguments, if any
        error = False
        ix = s.rfind("$error(")  # Must be at the end
        if ix >= 0:
            error = True
            # A typical format is $error(error_code, right_phrase, right_parts_of_speech)
            e = s[ix + 7 :].lstrip().rstrip(" )").split(",")
            s = s[:ix].strip()

        prepositions = []
        ap = s.split("/")
        s = ap[0]
        ix = 1
        while len(ap) > ix:
            # We expect something like 'af þgf'
            p = ap[ix].strip()
            parg = p.split()
            if len(parg) != 2:
                raise ConfigError("Preposition should have exactly one argument")
            if parg[1] not in _ALL_CASES:
                raise ConfigError("Unknown argument case for preposition")
            prepositions.append((parg[0], parg[1]))
            ix += 1
        a = s.split()
        adj = a[0]
        if error:
            AdjectivePredicates.add_error(adj, a[1:], prepositions, e)
        else:
            AdjectivePredicates.add(adj, a[1:], prepositions)

    @staticmethod
    def _handle_morphemes(s):
        """ Process the contents of the [morphemes] section """
        freelist = []
        boundlist = []
        spl = s.split()
        if len(spl) < 2:
            raise ConfigError(
                "Expected at least a prefix and an attachment specification"
            )
        m = spl[0]
        for pos in spl[1:]:
            if pos:
                if pos.startswith("+"):
                    boundlist.append(pos[1:])
                elif pos.startswith("-"):
                    freelist.append(pos[1:])
                else:
                    raise ConfigError(
                        "Attachment specification should start with '+' or '-'"
                    )
        Morphemes.add(m, boundlist, freelist)

    @staticmethod
    def read(fname):
        """ Read configuration file """

        with Settings._lock:

            if Settings.loaded:
                return

            CONFIG_HANDLERS = {
                "settings": Settings._handle_settings,
                "static_phrases": Settings._handle_static_phrases,
                "abbreviations": Settings._handle_abbreviations,
                "verb_objects": Settings._handle_verb_objects,
                "verb_subjects": Settings._handle_verb_subjects,
                "prepositions": Settings._handle_prepositions,
                "preferences": Settings._handle_preferences,
                "noun_preferences": Settings._handle_noun_preferences,
                "name_preferences": Settings._handle_name_preferences,
                "stem_preferences": Settings._handle_stem_preferences,
                "ambiguous_phrases": Settings._handle_ambiguous_phrases,
                "meanings": Settings._handle_meanings,
                "adjective_template": Settings._handle_adjective_template,
                "undeclinable_adjectives": Settings._handle_undeclinable_adjectives,
                "disallowed_names": Settings._handle_disallowed_names,
                "noindex_words": Settings._handle_noindex_words,
                "topics": Settings._handle_topics,
                "adjective_predicates": Settings._handle_adjective_predicates,
                "morphemes": Settings._handle_morphemes,
                "bin_errata": Settings._handle_bin_errata,
                "bin_deletions": Settings._handle_bin_deletions,
            }
            handler = None  # Current section handler

            rdr = None
            try:
                rdr = LineReader(fname)
                for s in rdr.lines():
                    # Ignore comments
                    ix = s.find("#")
                    if ix >= 0:
                        s = s[0:ix]
                    s = s.strip()
                    if not s:
                        # Blank line: ignore
                        continue
                    if s[0] == "[" and s[-1] == "]":
                        # New section
                        section = s[1:-1].strip().lower()
                        if section in CONFIG_HANDLERS:
                            handler = CONFIG_HANDLERS[section]
                            continue
                        raise ConfigError("Unknown section name '{0}'".format(section))
                    if handler is None:
                        raise ConfigError("No handler for config line '{0}'".format(s))
                    # Call the correct handler depending on the section
                    try:
                        handler(s)
                    except ConfigError as e:
                        # Add file name and line number information to the exception
                        # if it's not already there
                        e.set_pos(rdr.fname(), rdr.line())
                        raise e

            except ConfigError as e:
                # Add file name and line number information to the exception
                # if it's not already there
                if rdr:
                    e.set_pos(rdr.fname(), rdr.line())
                raise e

            Settings.loaded = True
