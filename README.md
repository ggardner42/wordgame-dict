# wordgame-dict

Build a clean, frequency-ranked word list for word games from a raw dictionary and a word-frequency file.

Raw dictionaries are full of oddities (abbreviations, proper nouns, archaic words), and raw frequency lists are full of web jargon, typos and names. This tool keeps only the words that **both** sources agree on, applies a handful of conservative junk filters, and lets you steer the result with a blocklist and an allowlist, so you never edit the output by hand. The output is a plain text file of `word count` lines.

It was built for [word-wheel](../word-wheel), but the output is generic and works for any game that wants common words with frequencies.

## How it works

- **The dictionary decides what is a word.** `tcp`, `href`, `couldn` and other jargon or tokenizing leftovers that appear in frequency lists are dropped because no dictionary lists them.
- **The frequency file decides how common a word is.** Every kept word carries its count, so a game can pick everyday words, weight choices by frequency, or score rare words higher.
- **Junk rules** catch what both sources let through (see below).
- **`blocklist.txt` and `allowlist.txt`** hold your decisions. Re-running the script re-applies them.
- **A review report** shows what each rule removed and where the remaining junk tends to hide, so tuning takes minutes, not a read through a million words.
- **It is deterministic.** The same inputs and options always produce a byte-identical output file.

## Requirements

Python 3 with no third-party packages (developed and tested with Python 3.13).

You also need two data files, which are not included:

- **A dictionary**: one word per line. `/usr/share/dict/words` works. Hunspell-style `word/FLAGS` lines are accepted too. Several dictionary files can be given.
- **A frequency file**: lines of `word<whitespace>count`, such as `count_1w.txt` from Peter Norvig's [Natural Language Corpus Data](https://norvig.com/ngrams/) page. Lines starting with `#` are ignored.

A good source of dictionaries and frequency lists, all under at most MIT License, can be found here: `https://github.com/BartMassey/wordlists.git`

## Quick start

```sh
python3 build_dictionary.py /usr/share/dict/words \
    --freq count_1w.txt \
    --blocklist blocklist.txt \
    --allowlist allowlist.txt \
    -o words_freq.txt \
    --report report.txt
```

The script prints a summary of what was kept and removed, and writes:

- `words_freq.txt`, the word list: one `word count` pair per line, most frequent first (ties alphabetical).
- `report.txt`, a review report (only when `--report` is given).

The output looks like this (illustrative numbers):

```
the 23135851162
of 13151942776
and 12997637966
...
```

## The junk rules

Applied to every word that is not on the allowlist. Each is designed to remove junk without removing real words.

| Rule | Removes | Notes |
| --- | --- | --- |
| Plain lowercase `a-z` only | capitalized entries (proper nouns), apostrophes, hyphens, digits, accents | applied when reading the dictionary |
| Length range | words outside `--min-len` / `--max-len` (default 3 to 8) | |
| No vowel | `hmm`, `shh`, `tsk`, `pfft` | `y` counts as a vowel, so `gym`, `myth`, `rhythm` survive |
| Same letter three times in a row | `iii`, `zzz`, `xiii` | |
| Double `q` or double `x` | `seqq`, `xxiv` | |
| Consonant run | more than `--max-consonant-run` (default 5) consonants in a row | real words such as `strengths` and `twelfths` survive |
| Roman numerals | `xii`, `lxvi`, `mcm` | `mix` is the one real word this catches; it is on the sample allowlist |
| `--min-agree K` | words listed by fewer than K of your dictionaries | useful with several dictionaries; words only one lists are often abbreviations |

A word that is in the dictionary but missing from the frequency file is dropped by default. With `--unranked-count 1` such words are kept with that count instead (very rare words, useful as accepted-but-never-shown bonus words in a game).

## Blocklist and allowlist

Both are plain text: one word per line, `#` starts a comment, matching is exact (list `fucked` and `fucking` separately from `fuck`).

- **`blocklist.txt`** is never kept. The sample file contains profanity, slurs and common abbreviation or jargon junk (about 190 words). It is a starting point: delete lines you disagree with, add your own. I deliberately left out real words with innocent main senses (for example `sat`, `aids`, `cracker`, `yahoo`) and anatomical terms.
- **`allowlist.txt`** is always kept, even if a junk rule would reject it or the dictionary lacks it. A line may also be `word count` to set the frequency yourself. If the word is in the frequency file it keeps that count. If it has no count anywhere, it gets `--unranked-count` when you set one, otherwise the lowest count in the frequency file.
- If a word is on both lists, the blocklist wins and a warning is printed.

## The review report

`--report FILE` writes a report that is regenerated on every run:

1. What each rule removed, with the most frequent examples. Check that no real words are in there.
2. The most common words in the **frequency file that the dictionary lacks**. Skim for real words your dictionary is missing (add them to the allowlist). The rest is jargon you are glad to lose.
3. The most common kept 3- and 4-letter words. Abbreviations hide here (`gov`, `fwy`). Add offenders to the blocklist.
4. The rarest kept words, to check that the dictionary is not letting oddities through.
5. Counts of kept words by length.

A good workflow: run, read the report, edit the two lists, run again, repeat. Because the script is deterministic and your decisions live in the two list files, you can regenerate at any time.

## Options

| Option | Default | Meaning |
| --- | --- | --- |
| `DICT [DICT ...]` | required | one or more dictionary files |
| `--freq FILE` | required | frequency file (`word count` per line) |
| `-o`, `--output FILE` | `words_freq.txt` | output file |
| `--blocklist FILE` | none | words to never keep |
| `--allowlist FILE` | none | words to always keep |
| `--min-len N` | 3 | shortest word to keep |
| `--max-len N` | 8 | longest word to keep |
| `--max-consonant-run N` | 5 | reject more consonants than this in a row |
| `--min-agree K` | 1 | require a word in at least K dictionaries |
| `--unranked-count N` | 0 (drop) | count given to dictionary words missing from the frequency file |
| `--report FILE` | none | write the review report |
| `--review-top N` | 150 | how many words per list in the report |

## Notes and limits

- The frequency file's quality matters. A web-derived list reflects web usage, so a few ordinary dictionary words may rank oddly and a few abbreviations that are also dictionary words (`gov`, `inc`) will look common. The report is designed to surface those.
- There is no stemming. `walk`, `walks` and `walked` are separate entries with separate counts.
- The sample blocklist is English-only and certainly incomplete. Treat it as a draft you own.

## Credits

Written with [Claude](https://claude.ai) (Anthropic) in collaboration with the project owner.
