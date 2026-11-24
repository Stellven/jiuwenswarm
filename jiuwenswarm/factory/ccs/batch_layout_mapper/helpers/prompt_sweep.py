"""Generate cold and primed probe targets in exact engine token counts."""

import argparse
import json


DEFAULT_LENGTHS = (2, 3, 7, 8, 9, 12, 13, 14, 15, 16, 17, 24, 25, 33)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--lengths", nargs="+", type=int, default=DEFAULT_LENGTHS,
                        help="Distinct total token counts, each at least 2")
    args = parser.parse_args()
    if min(args.lengths) < 2 or len(set(args.lengths)) != len(args.lengths):
        parser.error("prompt lengths must be distinct and at least 2")
    for length in args.lengths:
        for mode, prefix in (("cold", 0), ("primed", length // 2)):
            print(json.dumps({"id": f"{mode}-{length}", "mode": mode,
                              "prompt_tokens": length, "shared_prefix_tokens": prefix}))


if __name__ == "__main__":
    main()
