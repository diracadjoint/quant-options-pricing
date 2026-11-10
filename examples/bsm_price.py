"""Run after installing the package: python examples/bsm_price.py."""

from options_engine import bsm_price


if __name__ == "__main__":
    for option_type in ("call", "put"):
        price = bsm_price(100, 100, 1, 0.05, 0.20, option_type=option_type)
        print(f"{option_type.capitalize()}: {price:.12f}")
