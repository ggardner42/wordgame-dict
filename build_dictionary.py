#!/usr/bin/env python3
"""
build_dictionary.py - build the game's word list ("word count" per line).

A real dictionary decides WHAT IS A WORD; a frequency file decides HOW COMMON
it is. A word is kept only if it is in the dictionary AND in the frequency
file, so web jargon ("tcp"), typos and names in Norvig's counts never get in.

Typical use:
    python3 build_dictionary.py /usr/share/dict/words \\
        --freq count_1w.txt \\
        --blocklist blocklist.txt --allowlist allowlist.txt \\
        -o words_freq.txt --report report.txt

    (then)  python3 build_game.py words_freq.txt -o wordwheel.html

It is deterministic: the same inputs and options always give the same output
file, so you can re-run it any time. Make your hand edits in blocklist.txt and
allowlist.txt, never in the output file.

Inputs
  DICT [DICT ...]   one or more dictionary files. Lines may be plain words or
                    hunspell style "word/FLAGS". Only plain lowercase a-z words
                    are used (capitalised entries are proper nouns; entries with
                    apostrophes or hyphens are skipped).
  --freq FILE       frequency file with lines "word<whitespace>count", such as
                    Norvig's count_1w.txt. Lines starting with # are ignored.
  --blocklist FILE  words that are never kept (one per line, # comments).
  --allowlist FILE  words that are always kept, even if a rule below would
                    reject them or the dictionary lacks them. A line may also
                    be "word count" to give it a count. The blocklist wins if
                    a word is on both lists.

Junk rules (applied to words that are not on the allowlist)
  - no vowel (a e i o u y)                        hmm, tsk, pfft
  - same letter three times in a row              iii, zzz
  - qq or xx anywhere                             (seqq, xxiv)
  - a run of consonants longer than 5 (y counts   schlepps; real words such as
    as a vowel)                                   strengths, twelfths survive
  - a valid Roman numeral                         xii, xviii, mcm
    (mix is the one real word this catches; it is on the sample allowlist)
  - --min-agree K: with several dictionaries, require the word in K of them.
    Words that only one dictionary lists are often abbreviations or oddities.
"""
import argparse
import re
import sys
from collections import Counter, defaultdict

PLAIN = re.compile(r"[a-z]+")
TRIPLE = re.compile(r"(.)\1\1")
BAD_DOUBLE = re.compile(r"qq|xx")
ROMAN = re.compile(r"m{0,4}(cm|cd|d?c{0,3})(xc|xl|l?x{0,3})(ix|iv|v?i{0,3})")
VOWELS = set("aeiouy")


def consonant_run(word):
    best = run = 0
    for ch in word:
        if ch in VOWELS:
            run = 0
        else:
            run += 1
            best = max(best, run)
    return best


def read_wordlist(path):
    """Words from a blocklist/allowlist-style file. Returns {word: count-or-None}."""
    out = {}
    with open(path, encoding="utf-8", errors="replace") as f:
        for line in f:
            line = line.split("#", 1)[0].strip().lower()
            if not line:
                continue
            parts = line.split()
            count = None
            if len(parts) > 1 and parts[1].isdigit():
                count = int(parts[1])
            out[parts[0]] = count
    return out


def read_dictionary(path):
    words = set()
    with open(path, encoding="utf-8", errors="replace") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            head = line.split("/", 1)[0].split()      # drop hunspell flags
            if head and PLAIN.fullmatch(head[0]):
                words.add(head[0])
    return words


def read_freq(path):
    freq = {}
    bad = 0
    with open(path, encoding="utf-8", errors="replace") as f:
        for line in f:
            if not line.strip() or line.startswith("#"):
                continue
            parts = line.split()
            if len(parts) < 2 or not parts[-1].isdigit():
                bad += 1
                continue
            word = parts[0]
            if PLAIN.fullmatch(word) and word not in freq:
                freq[word] = int(parts[-1])
    return freq, bad


def main():
    ap = argparse.ArgumentParser(
        description="Build the game's 'word count' list from a dictionary and a frequency file.",
    )
    ap.add_argument("dictionaries", nargs="+", metavar="DICT", help="dictionary file(s)")
    ap.add_argument("--freq", required=True, metavar="FILE", help="frequency file (word count per line)")
    ap.add_argument("-o", "--output", default="words_freq.txt", help="output file (default words_freq.txt)")
    ap.add_argument("--blocklist", metavar="FILE", help="words to never keep")
    ap.add_argument("--allowlist", metavar="FILE", help="words to always keep")
    ap.add_argument("--min-len", type=int, default=3, help="shortest word (default 3)")
    ap.add_argument("--max-len", type=int, default=8, help="longest word (default 8)")
    ap.add_argument("--max-consonant-run", type=int, default=5,
                    help="reject words with more consonants than this in a row (default 5)")
    ap.add_argument("--min-agree", type=int, default=1,
                    help="with several dictionaries, require a word in at least this many (default 1)")
    ap.add_argument("--unranked-count", type=int, default=0,
                    help="dictionary words missing from the frequency file get this count "
                         "(default 0 = drop them; 1 keeps them as very rare bonus-only words)")
    ap.add_argument("--report", metavar="FILE", help="write a review report to this file")
    ap.add_argument("--review-top", type=int, default=150,
                    help="how many words per list to show in the report (default 150)")
    args = ap.parse_args()

    block = read_wordlist(args.blocklist) if args.blocklist else {}
    allow = read_wordlist(args.allowlist) if args.allowlist else {}
    for w in sorted(set(block) & set(allow)):
        print(f"warning: '{w}' is on both lists; the blocklist wins", file=sys.stderr)

    dict_sets = [read_dictionary(p) for p in args.dictionaries]
    votes = Counter()
    for s in dict_sets:
        votes.update(s)
    freq, bad_lines = read_freq(args.freq)
    if not freq:
        sys.exit("The frequency file had no usable 'word count' lines.")
    floor_count = min(freq.values())

    rejected = Counter()
    examples = defaultdict(list)   # reason -> [(count, word)]
    kept = {}

    def reject(reason, word):
        rejected[reason] += 1
        examples[reason].append((freq.get(word, 0), word))

    candidates = set(votes) | set(allow)
    for word in sorted(candidates):
        in_allow = word in allow
        if word in block:
            reject("on the blocklist", word); continue
        if not (args.min_len <= len(word) <= args.max_len):
            continue                                # silently out of range
        if not in_allow:
            if votes[word] < args.min_agree:
                reject(f"listed by fewer than {args.min_agree} dictionaries", word); continue
            if not (VOWELS & set(word)):
                reject("no vowel", word); continue
            if TRIPLE.search(word):
                reject("same letter three times in a row", word); continue
            if BAD_DOUBLE.search(word):
                reject("double q or double x", word); continue
            if consonant_run(word) > args.max_consonant_run:
                reject(f"more than {args.max_consonant_run} consonants in a row", word); continue
            if ROMAN.fullmatch(word):
                reject("Roman numeral", word); continue
        count = freq.get(word)
        if count is None:
            if in_allow:
                count = allow[word] or args.unranked_count or floor_count
            elif args.unranked_count > 0:
                count = args.unranked_count
            else:
                reject("in the dictionary but not in the frequency file", word); continue
        elif in_allow and allow[word]:
            count = allow[word]
        kept[word] = count

    ordered = sorted(kept.items(), key=lambda kv: (-kv[1], kv[0]))
    with open(args.output, "w", encoding="utf-8") as out:
        for word, count in ordered:
            out.write(f"{word} {count}\n")

    print(f"Dictionaries: {len(candidates):,} candidate words "
          f"({', '.join(str(len(s)) for s in dict_sets)} per file); "
          f"frequency file: {len(freq):,} words" +
          (f" ({bad_lines} unreadable lines)" if bad_lines else ""), file=sys.stderr)
    print(f"Kept {len(kept):,} words ({args.min_len}-{args.max_len} letters) -> {args.output}", file=sys.stderr)
    if rejected:
        print("Removed:", file=sys.stderr)
        for reason, n in rejected.most_common():
            print(f"  {n:>8,}  {reason}", file=sys.stderr)
    missing_block = sorted(w for w in block if w not in candidates)
    if missing_block:
        print(f"  ({len(missing_block)} blocklist entries were not in the dictionary anyway)", file=sys.stderr)

    if args.report:
        write_report(args, rejected, examples, kept, ordered, freq, votes, allow)
        print(f"Review report -> {args.report}", file=sys.stderr)


def write_report(args, rejected, examples, kept, ordered, freq, votes, allow):
    n = args.review_top
    lines = []
    add = lines.append
    add("REVIEW REPORT (regenerated every run; do not edit)")
    add("=" * 60)
    add("")
    add("What each rule removed (most frequent words first):")
    for reason, count in rejected.most_common():
        ex = sorted(examples[reason], key=lambda t: (-t[0], t[1]))[:12]
        add(f"  {count:>8,}  {reason}")
        add("             e.g. " + ", ".join(w for _, w in ex))
    add("")
    add(f"Most common words in the FREQUENCY file that are not in the dictionary (top {n}, lengths "
        f"{args.min_len}-{args.max_len}).")
    add("Scan for real words the dictionary lacks (add them to allowlist.txt); the rest is jargon you are glad to lose:")
    missing = [(c, w) for w, c in freq.items()
               if w not in votes and args.min_len <= len(w) <= args.max_len and w not in kept]
    missing.sort(key=lambda t: (-t[0], t[1]))
    add("  " + " ".join(w for _, w in missing[:n]))
    add("")
    for length in (3, 4):
        words = [w for w, _ in ordered if len(w) == length][:n]
        add(f"Most common KEPT {length}-letter words (junk and abbreviations hide among short words; "
            f"add offenders to blocklist.txt):")
        add("  " + " ".join(words))
        add("")
    tail = [w for w, _ in ordered][-n:]
    add(f"The {n} RAREST kept words (check the dictionary is not letting oddities through):")
    add("  " + " ".join(tail))
    add("")
    by_len = Counter(len(w) for w in kept)
    add("Words kept by length: " + ", ".join(f"{k}: {by_len[k]:,}" for k in sorted(by_len)))
    with open(args.report, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


if __name__ == "__main__":
    main()
