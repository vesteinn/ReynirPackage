"""

    Reynir: Natural language processing for Icelandic

    Reducer module

    Copyright (C) 2019 Miðeind ehf.
    Original author: Vilhjálmur Þorsteinsson

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


    The classes within this module reduce a parse forest containing
    multiple possible parses of a sentence to a single most likely
    parse tree.

    The reduction uses five methods:

  * First, a dictionary of preferred token interpretations (fetched
    from config/Prefs.conf), where words like 'ekki' are classified
    as being more likely to be from one category than another
    (in this case adverb rather than noun);

  * Second, a set of general heuristics (adverbs being by default less
    preferred than other categories, etc.);

  * Third, production priorities within nonterminals, as specified
    using > signs between productions in Reynir.grammar;

  * Fourth, scores explicitly assigned to nonterminals in Reynir.grammar
    and verb forms in Verbs.conf using the $score() pragma;

  * Fifth, verb-preposition matching where particular combinations
    of prepositions with verbs (eventually including verb objects
    in particular cases) receive bonus scores. For instance,
    "Dómarinn frestaði mótinu vegna veðurs" ("The referee postponed
    the competition due to weather") will attach the preposition
    "vegna veðurs" to the verb "fresta" with an argument in the
    dative case, instead of to the noun "mótinu".

    The verb-preposition matching is driven by the configuration file
    config/Verbs.conf. (This file was originally generated from data
    generously provided by Eiríkur Rögnvaldsson, professor emeritus
    of linguistics at the University of Iceland, whom we thank).

    The parse forest is created by the enhanced Earley parser in
    fastparser.py. It is densely packed in an SPPF (Shared Packed
    Parse Forest) structure, where identical subtrees are shared rather than
    being duplicated throughout the parse forest. However, verb-preposition
    matching requires a partial unpacking of the forest so that we
    can give different scores to structurally identical subtrees, depending
    on enclosing verbs. Some of these unpacked subtrees may then be eliminated
    by the bottom-up reducer, while others survive the pruning process.

    The partial unpacking is performed by the PrepositionUnpacker class
    within ParseForestReducer. The unpacking only applies to tree nodes
    tagged with "enable_prep_bonus" (typically SagnInnskot), i.e. their
    descendant nodes up to those tagged with "begin_prep_scope"
    or "purge_prep", or noun phrase nonterminal nodes ("Nl_*"). This
    unpacking scope is sufficient to include the contained prepositions
    within the parent SagnInnskot node, i.e. the terminals whose names
    have the form fs_*.

"""

import copy
from collections import defaultdict

from .fastparser import Node, ParseForestNavigator, ParseForestPrinter
from .settings import Preferences, NounPreferences, VerbObjects
from .binparser import BIN_Token


_PREP_SCOPE_SET = frozenset(("begin_prep_scope", "purge_prep", "no_prep"))
_PREP_ALL_SET = frozenset(_PREP_SCOPE_SET | {"enable_prep_bonus"})
_CASES_SET = frozenset(BIN_Token.CASES)
_VERB_PREP_BONUS = 7  # Give 7 extra points for a verb/preposition match
_VERB_PREP_PENALTY = -2  # Subtract 2 points for a non-match
_LENGTH_BONUS_FACTOR = 10  # For length bonus, multiply number of tokens by this factor

# Noun categories set
_NOUN_SET = BIN_Token.GENDERS_SET  # kk, kvk, hk


def copy_node(node):
    """ Copy the tree under the given node, including the node itself.
        Stop when coming to a nested preposition scope or to a
        noun phrase (Nafnliður, Nl_*) """

    def dup(node):
        """ Duplicate (copy) this node """
        if node is None:
            return None
        nt = node.nonterminal if node.is_completed else None
        if nt is not None:
            if nt.has_any_tag(_PREP_SCOPE_SET):
                # No copying from this point
                return node
            if nt.is_noun_phrase:
                # No need to copy Nl after we've been through the
                # preposition itself
                return node
            if nt.is_optional and node.is_empty:
                # Explicitly nullable nonterminal with no child: don't bother copying
                return node
        # Recurse to copy the child tree as well
        return copy_node(node)

    if node is None:
        return None
    # First, copy the node itself
    node = Node.copy(node)
    # Then, copy the children as required by applying the dup() function
    node.transform_children(dup)
    # Return the fresh copy
    return node


class PrepositionUnpacker(ParseForestNavigator):

    """ Subclass to duplicate (split) the tree at every enclosing
        preposition scope (SagnInnskot) """

    def __init__(self):
        super().__init__(visit_all=False)

    def _visit_nonterminal(self, level, node):
        """ Create a result object to capture information about
            productions (families of children) of this nonterminal """
        return defaultdict(list)

    def _add_result(self, results, ix, r):
        """ Capture a particular child node r of family ix """
        results[ix].append(r)

    def _process_results(self, results, node):
        """ Go through the child productions (families) and
            duplicate any nodes that have the enable_prep_bonus
            tag, so that they can receive independent scores in
            the reducer depending on the containing verb context """
        for family_ix, children in results.items():
            for ix, child_nt in enumerate(children):
                # child_nt is None for all uninteresting nodes, i.e. terminal/token nodes
                # and nonterminal nodes that are not completed
                if child_nt is not None and child_nt.has_tag("enable_prep_bonus"):
                    # This is a nonterminal node marked with enable_prep_bonus:
                    # Duplicate its subtree
                    node.transform_child(family_ix, ix, copy_node)
        # Return the nonterminal corresponding to this node,
        # if the node represents a completed nonterminal
        return node.nonterminal if node.is_completed else None

    @classmethod
    def navigate(cls, root_node):
        cls().go(root_node)


class ReductionInfo:

    """ Class to accumulate information about a nonterminal and its
        child production(s) during reduction """

    def __init__(self, reducer, node):
        self.reducer = reducer
        self.node = node
        self.sc = defaultdict(lambda: dict(sc=0))  # Child tree scores
        # We are only interested in completed nonterminals
        self.nt = node.nonterminal if node.is_completed else None
        self.name = self.nt.name if self.nt else None
        # Verb/preposition matching stuff
        self.pushed_prep_bonus = False
        verb = reducer.get_current_verb()
        if self.nt:
            if self.nt.has_tag("enable_prep_bonus"):
                # SagnInnskot has this tag
                reducer.push_prep_bonus(None if verb is None else verb[:])
                self.pushed_prep_bonus = True
            elif self.nt.has_tag("begin_prep_scope") or self.nt.is_noun_phrase:
                # Setning and SetningÁnF have this tag, and we also
                # enter a new prep bonus scope in noun phrases
                reducer.push_prep_bonus(None)
                self.pushed_prep_bonus = True
                verb = None
        reducer.push_current_verb(verb)
        self.start_verb = verb

    def add_child_score(self, ix, sc):
        """ Add a child node's score to the parent family's score,
            where the parent family has index ix (0..n) """
        self.sc[ix]["sc"] += sc["sc"]
        # Carry information about contained prepositions ("fs") and verbs ("so")
        # up the tree
        for key in ("so", "sl"):
            if key in sc:
                if key in self.sc[ix]:
                    self.sc[ix][key].extend(sc[key])
                else:
                    self.sc[ix][key] = sc[key][:]
                if key == "sl":
                    self.reducer.set_current_verb(sc[key])

    def add_child_production(self):
        """ Reset the current verb scope for each family """
        self.reducer.set_current_verb(self.start_verb)

    def process(self, node):
        """ After accumulating scores for all possible productions
            of this nonterminal (families of children), find the
            highest scoring one and reduce the tree to that child only """
        try:

            csc = self.sc
            if not csc:
                return dict(sc=0)  # Empty node
            if len(csc) == 1:
                # Not ambiguous: only one result, do a shortcut
                [sc] = csc.values()  # Will raise an exception if not exactly one value
            else:
                # Eliminate all families except the best scoring one
                # Sort in decreasing order by score, using the family index
                # as a tie-breaker for determinism
                s = sorted(csc.items(), key=lambda x: (x[1]["sc"], -x[0]), reverse=True)
                # This is the best scoring family
                # (and the one with the lowest index
                # if there are many with the same score)
                ix, sc = s[0]
                # And now for the key action of the reducer: Eliminate all other families
                node.reduce_to(ix)

            if self.nt is not None:
                # We will be adjusting the result: make sure we do so on
                # a separate dict copy (we don't want to clobber the child's dict)
                # Get score adjustment for this nonterminal, if any
                # (This is the $score(+/-N) pragma from Reynir.grammar)
                sc["sc"] += self.reducer._score_adj.get(self.nt, 0)

                if self.nt.has_tag("apply_length_bonus"):
                    # Give this nonterminal a bonus depending on how many tokens
                    # it encloses
                    bonus = (self.node.end - self.node.start - 1) * _LENGTH_BONUS_FACTOR
                    sc["sc"] += bonus

                if (
                    self.nt.has_tag("apply_prep_bonus")
                    and self.reducer.get_prep_bonus() is not None
                ):
                    # This is a nonterminal that we like to see in a verb/prep context
                    # An example is Dagsetning which we like to be associated with a verb
                    # rather than a noun phrase
                    sc["sc"] += _VERB_PREP_BONUS

                if self.nt.has_tag("pick_up_verb"):
                    verb = sc.get("so")
                    if verb is not None:
                        sc["sl"] = verb[:]

                if self.nt.has_any_tag({"begin_prep_scope", "purge_verb"}):
                    # Delete information about contained verbs
                    # SagnRuna, EinSetningÁnF, SagnHluti, NhFyllingAtv
                    # and Setning have this tag
                    sc.pop("so", None)  # Simpler than if "so" in sc: del sc["so"]
                    sc.pop("sl", None)
            return sc

        finally:
            # Make sure we pop everything that was pushed in __init__()
            if self.pushed_prep_bonus:
                self.reducer.pop_prep_bonus()
            self.reducer.pop_current_verb()


class ParseForestReducer(ParseForestNavigator):

    """ Subclass to navigate a parse forest and reduce it
        so that the highest-scoring alternative production of a nonterminal
        (family of children) survives at each point of ambiguity """

    def __init__(self, grammar, scores):
        super().__init__()
        self._scores = scores
        self._grammar = grammar
        self._score_adj = grammar._nt_scores
        self._prep_bonus_stack = [None]
        self._current_verb_stack = [None]
        self._bonus_cache = dict()

    def push_prep_bonus(self, val):
        self._prep_bonus_stack.append(val)

    def pop_prep_bonus(self):
        self._prep_bonus_stack.pop()

    def get_prep_bonus(self):
        return self._prep_bonus_stack[-1]

    def push_current_verb(self, val):
        self._current_verb_stack.append(val)

    def pop_current_verb(self):
        self._current_verb_stack.pop()

    def get_current_verb(self):
        return self._current_verb_stack[-1]

    def set_current_verb(self, val):
        self._current_verb_stack[-1] = val

    def verb_prep_bonus(self, prep_terminal, prep_token, verb_terminal, verb_token):
        """ Return a verb/preposition match bonus, as and if applicable """
        # Only do this if the prepositions match the verb being connected to
        m = verb_token.match_with_meaning(verb_terminal)
        verb = m.stofn
        if "MM" in m.beyging:
            # Use MM-NH nominal form for MM verbs,
            # i.e. "eignast" instead of "eiga" for a verb such as "eignaðist"
            verb = BIN_Token.mm_verb_stem(verb)
        verb_with_cases = verb + verb_terminal.verb_cases
        if prep_terminal.num_variants:
            # Normal terminal, such as fs_ef
            prep_case = prep_terminal.variant(0)
            if prep_case in _CASES_SET:
                prep_with_case = prep_token + "_" + prep_case
            else:
                # Probably fs_nh: match all cases
                prep_with_case = prep_token
        else:
            # Literal terminal, such as "á:fs" - match all cases
            prep_with_case = prep_token
        # Do a lookup in the verb/preposition lexicon from the settings
        # (typically stored in VerbPrepositions.conf)
        if VerbObjects.verb_matches_preposition(verb_with_cases, prep_with_case):
            # If the verb clicks with the given preposition in the
            # given case, give a healthy bonus
            return _VERB_PREP_BONUS
        # If no match, discourage
        return _VERB_PREP_PENALTY

    def _visit_epsilon(self, level):
        """ At Epsilon node """
        return dict(sc=0)  # Score 0

    def _visit_token(self, level, node):
        """ At token node """
        # Return the score of this token/terminal match
        d = dict()
        sc = self._scores[node.start][node.terminal]
        if node.terminal.matches_category("fs"):
            # Preposition terminal - this is either a normal fs_case terminal
            # or a literal terminal such as "á:fs"
            prep_bonus = self.get_prep_bonus()
            if prep_bonus is not None:
                # We are inside a preposition bonus zone:
                # give bonus points if this preposition terminal matches
                # an enclosing verb
                # Iterate through enclosing verbs
                final_bonus = None
                for terminal, token in prep_bonus:
                    # Attempt to find the preposition matching bonus in the cache
                    key = (node.terminal, node.token.lower, terminal, token)
                    bonus = self._bonus_cache.get(key)
                    if bonus is None:
                        bonus = self._bonus_cache[key] = self.verb_prep_bonus(*key)
                    if bonus is not None:
                        # Found a bonus, which can be positive or negative
                        if final_bonus is None:
                            final_bonus = bonus
                        else:
                            # Give the highest bonus that is available
                            final_bonus = max(final_bonus, bonus)
                if final_bonus is not None:
                    sc += final_bonus
        elif node.terminal.matches_category("so"):  # !!! Was .startswith("so")
            # Verb terminal: pick up the verb
            d["so"] = [(node.terminal, node.token)]
        d["sc"] = sc
        # node.score = sc
        return d

    def _visit_nonterminal(self, level, node):
        """ At nonterminal node """
        # Return a fresh object to collect results, unless the
        # node doesn't span any tokens, in which case we don't bother
        return ReductionInfo(self, node) if node.is_span else None

    def _visit_family(self, results, level, node, ix, prod):
        """ Add information about a family of children to the result object """
        # if node.is_ambiguous:
        #     print(f"Visiting family {ix} of head node {node}")
        if results is not None:
            results.add_child_production()

    def _add_result(self, results, ix, sc):
        """ Append a single result to the result object """
        # Add up scores for each family of children
        # print(f"Node {results.node}: family {ix}, adding child score {sc}")
        if results is not None:
            results.add_child_score(ix, sc)

    def _process_results(self, results, node):
        """ Sort scores after visiting children, then prune the child families
            (productions) leaving only the top-scoring family (production) """
        d = dict(sc=0) if results is None else results.process(node)
        # node.score = d["sc"]
        return d

    def _check_stacks(self):
        """ Runtime sanity check of the reducer stacks """
        assert len(self._prep_bonus_stack) == 1 and self._prep_bonus_stack[0] is None
        assert (
            len(self._current_verb_stack) == 1 and self._current_verb_stack[0] is None
        )

    def go(self, root_node):
        """ Perform the reduction, but first split the tree underneath
            nodes that have the enable_prep_bonus tag """
        self._check_stacks()  # !!! DEBUG
        PrepositionUnpacker.navigate(root_node)
        # ParseForestPrinter.print_forest(root_node, skip_duplicates = True)
        # Start normal navigation of the tree after the split
        result = super().go(root_node)
        self._check_stacks()  # !!! DEBUG
        return result


class OptionFinder(ParseForestNavigator):

    """ Subclass to navigate a parse forest and populate the set
        of terminals that match each token """

    def _visit_token(self, level, node):
        """ At token node """
        # assert node.terminal is not None
        self._finals[node.start].add(node.terminal)
        self._tokens[node.start] = node.token
        return None

    def __init__(self, finals, tokens):
        super().__init__()
        self._finals = finals
        self._tokens = tokens


class Reducer:

    """ Reduces parse forests to a single most likely parse tree """

    def __init__(self, grammar):
        self._grammar = grammar

    def _find_options(self, forest, finals, tokens):
        """ Find token-terminal match options in a parse forest with a root in w """
        OptionFinder(finals, tokens).go(forest)

    def _calc_terminal_scores(self, w):
        """ Calculate the score for each possible terminal/token match """

        # First pass: for each token, find the possible terminals that
        # can correspond to that token
        finals = defaultdict(set)
        tokens = dict()
        self._find_options(w, finals, tokens)

        # Second pass: find a (partial) ordering by scoring the terminal alternatives for each token
        scores = dict()
        noun_prefs = NounPreferences.DICT

        # Loop through the indices of the tokens spanned by this tree
        for i in range(w.start, w.end):

            s = finals[i]
            # Initially, each alternative has a score of 0
            scores[i] = {terminal: 0 for terminal in s}

            if len(s) <= 1:
                # No ambiguity to resolve here
                continue

            token = tokens[i]
            # More than one terminal in the option set for the token at index i
            # Calculate the relative scores
            # Find out whether the first part of all the terminals are the same
            same_first = len(set(terminal.first for terminal in s)) == 1
            txt = txt_last = token.lower
            composite = False
            # Get the last part of a composite word (e.g. 'jaðar-áhrifin' -> 'áhrifin')
            if token.is_word and token.t2 and "-" in token.t2[0].ordmynd:
                composite = True
                txt_last = token.t2[0].ordmynd.rsplit("-", maxsplit=1)[-1]
            # No need to check preferences if the first parts of all possible terminals are equal
            # Look up the preference ordering from Reynir.conf, if any
            prefs = None if same_first else Preferences.get(txt_last)
            sc = scores[i]
            if prefs:
                adj_worse = defaultdict(int)
                adj_better = defaultdict(int)
                for worse, better, factor in prefs:
                    for wt in s:
                        if wt.first in worse:
                            for bt in s:
                                if wt is not bt and bt.first in better:
                                    if bt.name[0] in "\"'":
                                        # Literal terminal:
                                        # be even more aggressive in promoting it
                                        adj_w = -2 * factor
                                        adj_b = +6 * factor
                                    else:
                                        adj_w = -2 * factor
                                        adj_b = +4 * factor
                                    adj_worse[wt] = min(adj_worse[wt], adj_w)
                                    adj_better[bt] = max(adj_better[bt], adj_b)
                for wt, adj in adj_worse.items():
                    sc[wt] += adj
                for bt, adj in adj_better.items():
                    sc[bt] += adj

            # Apply heuristics to each terminal that potentially matches this token
            for t in s:

                if t.is_literal:
                    # Give a bonus for exact or semi-exact matches with
                    # literal terminals
                    sc[t] += 2

                tfirst = t.first
                if tfirst == "ao" or tfirst == "eo":
                    # Subtract from the score of all ao and eo
                    sc[t] -= 1
                elif tfirst == "no":
                    if t.is_singular:
                        # Add to singular nouns relative to plural ones
                        sc[t] += 1
                    elif t.is_abbrev:
                        # Punish abbreviations in favor of other more specific terminals
                        sc[t] -= 1
                    if token.is_word and token.is_upper and token.t2:
                        # Punish connection of normal noun terminal to
                        # an uppercase word that can be a person or entity name
                        if any(
                            m.fl in {"ism", "erm", "nafn", "föð", "móð", "örn", "fyr"}
                            for m in token.t2
                        ):
                            # logging.info(
                            #     "Punishing connection of {0} with 'no' terminal"
                            #     .format(tokens[i].t1))
                            sc[t] -= 5
                    # Noun priorities, i.e. between different genders
                    # of the same word form (for example "ára" which can refer to
                    # three stems with different genders)
                    if txt_last in noun_prefs:
                        np = noun_prefs[txt_last].get(t.gender, 0)
                        sc[t] += np
                elif tfirst == "fs":
                    if t.has_variant("nf"):
                        # Reduce the weight of the 'artificial' nominative prepositions
                        # 'næstum', 'sem', 'um'
                        # Make other cases outweigh the Nl_nf bonus of +4 (-2 -3 = -5)
                        sc[t] -= 8
                    elif txt == "við" and t.has_variant("þgf"):
                        # Smaller bonus for við + þgf (is rarer than við + þf)
                        sc[t] += 1
                    elif txt == "sem" and t.has_variant("þf"):
                        sc[t] -= 4
                    elif txt == "á" and t.has_variant("þgf"):
                        # Larger bonus for á + þgf to resolve conflict with verb 'eiga'
                        sc[t] += 4
                    else:
                        # Else, give a bonus for each matched preposition
                        sc[t] += 2
                elif tfirst == "lo":
                    if composite:
                        # If this is a composite word, it's less likely
                        # to be an adjective, so give it a penalty
                        sc[t] -= 3
                elif tfirst == "so":
                    if t.num_variants > 0 and t.variant(0) in "012":
                        # Consider verb arguments
                        # Normally, we give a bonus for verb arguments: the more matched, the better
                        numcases = int(t.variant(0))
                        adj = 2 * numcases
                        # !!! TODO: Logic should be added here to encourage zero arguments
                        # for verbs in the middle voice
                        if numcases == 0:
                            # Zero arguments: we might not like this
                            vo0 = VerbObjects.VERBS[0]
                            if all(
                                (m.stofn not in vo0)
                                and (m.ordmynd not in vo0)
                                and ("MM" not in m.beyging)
                                for m in token.t2
                                if m.ordfl == "so"
                            ):
                                # No meaning where the verb has zero arguments
                                # print("Subtracting 5 points for 0-arg verb {0}".format(tokens[i].t1))
                                adj = -5
                        # Apply score adjustments for verbs with particular object cases,
                        # as specified by $score(n) pragmas in Verbs.conf
                        # In the (rare) cases where there are conflicting scores,
                        # apply the most positive adjustment
                        adjmax = 0
                        for m in token.t2:
                            if m.ordfl == "so":
                                key = m.stofn + t.verb_cases
                                score = VerbObjects.SCORES.get(key)
                                if score is not None:
                                    adjmax = score
                                    break
                        sc[t] += adj + adjmax
                    if t.is_sagnb:
                        # We like sagnb and lh, it means that more
                        # than one piece clicks into place
                        sc[t] += 6
                    elif t.is_lh:
                        # sagnb is preferred to lh, but vb (veik beyging) is discouraged
                        if t.has_variant("vb"):
                            sc[t] -= 2
                        else:
                            sc[t] += 3
                    elif t.is_lh_nt:
                        sc[t] += 12  # Encourage LHNT rather than LO
                    elif t.is_mm:
                        # Encourage mm forms. The encouragement should be better than
                        # the score for matching a single case, so we pick so_0_mm
                        # rather than so_1_þgf, for instance.
                        sc[t] += 3
                    elif t.is_vh:
                        # Encourage vh forms
                        sc[t] += 2
                    if t.is_subj:
                        # Give a small bonus for subject matches
                        if t.has_variant("none"):
                            # ... but a punishment for subj_none
                            sc[t] -= 3
                        else:
                            sc[t] += 1
                    if t.is_nh:
                        if (i > 0) and any(pt.first == "nhm" for pt in finals[i - 1]):
                            # Give a bonus for adjacent nhm + so_nh terminals
                            sc[t] += 4  # Prop up the verb terminal with the nh variant
                            for pt in scores[i - 1].keys():
                                if pt.first == "nhm":
                                    # Prop up the nhm terminal
                                    scores[i - 1][pt] += 2
                                    break
                        if any(
                            pt.first == "no" and pt.has_variant("ef") and pt.is_plural
                            for pt in s
                        ):
                            # If this is a so_nh and an alternative no_ef_ft exists, choose this one
                            # (for example, 'hafa', 'vera', 'gera', 'fara', 'mynda', 'berja', 'borða')
                            sc[t] += 4
                    if (i > 0) and token.is_upper:
                        # The token is uppercase and not at the start of a sentence:
                        # discourage it from being a verb
                        sc[t] -= 4
                elif tfirst == "tala":
                    if t.has_variant("ef"):
                        # Try to avoid interpreting plain numbers as possessives
                        sc[t] -= 4
                elif tfirst == "person":
                    if t.has_variant("nf"):
                        # Prefer person names in the nominative case
                        sc[t] += 2
                elif tfirst == "sérnafn":
                    if not token.t2:
                        # If there are no BÍN meanings, we had no choice but to use sérnafn,
                        # so alleviate some of the penalty given by the grammar
                        sc[t] += 4
                    else:
                        # BÍN meanings are available: discourage this
                        # print(f"Discouraging sérnafn {txt}, BÍN meanings are {tokens[i].t2}")
                        sc[t] -= 10
                        if i == w.start:
                            # First token in sentence, and we have BÍN meanings:
                            # further discourage this
                            sc[t] -= 6
                elif tfirst == "fyrirtæki":
                    # We encourage company names to be interpreted as such,
                    # so we give company abbreviations ('hf.', 'Corp.', 'Limited')
                    # a high priority
                    sc[t] += 24
                elif tfirst == "st" or (tfirst == "sem" and t.colon_cat == "st"):
                    if txt == "sem":
                        # Discourage "sem" as a pure conjunction (samtenging)
                        # (it does not get a penalty when occurring as
                        # a connective conjunction, 'stt')
                        sc[t] -= 6
                elif tfirst == "abfn":
                    # If we have number and gender information with the reflexive
                    # pronoun, that's good: encourage it
                    sc[t] += 6 if t.num_variants > 1 else 2
                elif tfirst == "gr":
                    # Encourage separate definite article rather than pronoun
                    sc[t] += 2

        return scores

    def _reduce(self, w, scores):
        """ Reduce a forest with a root in w based on subtree scores """
        return ParseForestReducer(self._grammar, scores).go(w)

    def go_with_score(self, forest):
        """ Returns the argument forest after pruning it down to a single tree """
        if forest is None:
            return (None, 0)
        scores = self._calc_terminal_scores(forest)
        # Third pass: navigate the tree bottom-up, eliminating lower-rated
        # options (subtrees) in favor of higher rated ones
        score = self._reduce(forest, scores)
        return (forest, score["sc"])

    def go(self, forest):
        """ Return only the reduced forest, without its score """
        w, _ = self.go_with_score(forest)
        return w
