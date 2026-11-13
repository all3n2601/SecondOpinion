import argparse

from second_opinion.release import load_release


def main() -> None:
    parser = argparse.ArgumentParser(prog="second_opinion")
    parser.add_argument("--release", required=True, help="folder with the five TCGA-BRCA release files")
    parser.add_argument("--report", required=True, help="report to audit (Markdown)")
    parser.add_argument("--out", default="audit.json", help="where to write audit.json")
    args = parser.parse_args()

    load_release(args.release)
    raise NotImplementedError("claim extraction, checks and audit.json export are not built yet")


if __name__ == "__main__":
    main()
