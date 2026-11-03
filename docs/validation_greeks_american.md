# European Greeks and American CRR validation

Measured on Python 3.12.14, Linux x86_64.
Timings depend on hardware and load; no market data is used.

## Analytic Greek check

S=K=100, remaining years=1, r=0.05, sigma=0.20, q=0.02; European call.

| Greek | Analytic | Central difference | Absolute difference |
| --- | ---: | ---: | ---: |
| delta | 0.5868511461 | 0.5868511390 | 7.11e-09 |
| gamma | 0.0189505788 | 0.0189505786 | 1.2e-10 |
| vega | 37.9011575100 | 37.9011575092 | 8.49e-10 |
| theta | -5.0893189140 | -5.0893189144 | 3.88e-10 |
| rho | 49.4581091053 | 49.4581090990 | 6.3e-09 |

Spot bump=0.01; other bumps=1e-5. Vega/Rho are per absolute unit;
Theta is per calendar year. Daily Theta=Theta/365; 1pp Vega/Rho=value/100.

## Tree refinement

S=K=100, remaining years=1, r=0.05, sigma=0.20, q=0.
European reference=BSM. Premium uses the European control on the same tree.

| Option | N | American | European tree | BSM | European error/K | Premium | Seconds |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| call | 100 | 10.43061166 | 10.43061166 | 10.45058357 | 0.0002 | 0.00000000 | 0.0027 |
| call | 101 | 10.46795467 | 10.46795467 | 10.45058357 | 0.000174 | 0.00000000 | 0.0021 |
| call | 200 | 10.44059126 | 10.44059126 | 10.45058357 | 9.99e-05 | 0.00000000 | 0.0076 |
| call | 201 | 10.45930793 | 10.45930793 | 10.45058357 | 8.72e-05 | 0.00000000 | 0.0079 |
| call | 400 | 10.44558584 | 10.44558584 | 10.45058357 | 5e-05 | 0.00000000 | 0.0339 |
| call | 401 | 10.45495550 | 10.45495550 | 10.45058357 | 4.37e-05 | 0.00000000 | 0.0326 |
| call | 800 | 10.44808431 | 10.44808431 | 10.45058357 | 2.5e-05 | 0.00000000 | 0.1369 |
| call | 801 | 10.45277198 | 10.45277198 | 10.45058357 | 2.19e-05 | 0.00000000 | 0.1405 |
| put | 100 | 6.08235441 | 5.55355411 | 5.57352602 | 0.0002 | 0.52880030 | 0.0025 |
| put | 101 | 6.10456705 | 5.59089712 | 5.57352602 | 0.000174 | 0.51366993 | 0.0021 |
| put | 200 | 6.08638275 | 5.56353371 | 5.57352602 | 9.99e-05 | 0.52284904 | 0.0079 |
| put | 201 | 6.09752111 | 5.58225038 | 5.57352602 | 8.72e-05 | 0.51527074 | 0.0084 |
| put | 400 | 6.08840590 | 5.56852829 | 5.57352602 | 5e-05 | 0.51987761 | 0.0331 |
| put | 401 | 6.09398858 | 5.57789795 | 5.57352602 | 4.37e-05 | 0.51609063 | 0.0333 |
| put | 800 | 6.08940162 | 5.57102676 | 5.57352602 | 2.5e-05 | 0.51837485 | 0.1431 |
| put | 801 | 6.09219614 | 5.57571443 | 5.57352602 | 2.19e-05 | 0.51648171 | 0.1370 |

Even and odd sequences oscillate around their limits; refine them separately.
The non-dividend call has zero early-exercise premium. The put has a positive premium.
Tests require European error/K < 1e-3 at N=800/801, and the refined
American put within 0.003 of the standard 6.0896 benchmark at N=1600.
This is a limited benchmark, not an exhaustive parameter-domain accuracy guarantee.
No continuous exercise frontier or American Greeks are reported by this implementation.
