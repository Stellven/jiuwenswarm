# Illustration to adapt, not a drop-in patch.

def boundary_lengths(logical: int, physical: int) -> list[int]:
    """Choose rows just below, at, and above relevant configured cuts."""
    if not 0 < physical <= logical:
        raise ValueError("expected 0 < physical <= logical")
    aligned = logical - logical % physical
    cuts = {physical, logical, 2 * aligned}
    return sorted({cut + delta for cut in cuts for delta in (-1, 0, 1)
                   if cut + delta > 0})


if __name__ == "__main__":
    print(boundary_lengths(13, 8))
