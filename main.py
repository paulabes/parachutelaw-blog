"""Parachute Law Content Engine — CLI entry point."""

import argparse

from pipeline import run_pipeline


def main():
    parser = argparse.ArgumentParser(description="Parachute Law Content Engine")
    parser.add_argument("--topic", required=True, help="Blog topic to research and write about")
    parser.add_argument("--mode", choices=["original", "outrank"], default="original",
                        help="'original' writes from scratch, 'outrank' finds and beats a competitor article")
    args = parser.parse_args()

    run_pipeline(args.topic, mode=args.mode)


if __name__ == "__main__":
    main()
