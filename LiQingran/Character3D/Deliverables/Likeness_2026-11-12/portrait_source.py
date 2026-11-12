"""Inputs and object names shared by the Li Qingran builder and verifier."""

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent
REPOSITORY = ROOT.parents[3]
PREVIOUS = ROOT.parent / "Portrait_2026-11-12"
BASE = ROOT.parent / "HeadShoulders_2026-11-12"
PHOTO = ROOT.parent / "HeadShoulders_2026-09-30/Preview/Original_Reference.png"
SOURCE = PREVIOUS / "LiQingran_Portrait.blend"
HAIR_COLLECTION = "Hair • scalp, fringe, knot and long strands"

sys.path[:0] = [str(PREVIOUS), str(BASE), str(REPOSITORY / "Scripts")]

from refine_portrait import HEAD as HEAD
