# American numerical Greeks: independent stability studies

Python 3.12.14; Linux x86_64. Synthetic inputs only.
K=100, maturity=1 year, sigma=.20; exercise=American. Dividend yield stays fixed.
FD: Smax=400, Rannacher on, omega=1.2, PSOR tolerance=1e-10, max iterations=10000.
Base absolute bumps: spot=2.5, volatility=.005, rate=.001, maturity=.01 years.
Vega/Rho are per absolute unit; Theta is calendar theta per year.
Central formulas are used in these cases. Every perturbation solves exercise anew.
Grid, domain and controls are frozen inside each risk calculation.

## put, S=100, r=0.05, q=0

### Bump scale (fixed M=320, Nt=100)

| Setting | Delta | Gamma | Vega | Theta | Rho | Flags |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| 0.25 | -0.41122236 | 0.04601360 | 37.51933336 | -2.24111907 | -30.23717820 | spot bump smaller than grid spacing: interpolation-limited |
| 0.5 | -0.41122236 | 0.02300680 | 37.51031208 | -2.24127187 | -30.22843842 | none detected |
| 1 | -0.41190011 | 0.02300663 | 37.50556417 | -2.24094166 | -30.22850968 | none detected |
| 2 | -0.41460242 | 0.02300601 | 37.50349820 | -2.24097097 | -30.22180801 | none detected |

### Spatial M (fixed Nt=100, fixed base bumps)

| Setting | Delta | Gamma | Vega | Theta | Rho | Flags |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| 160 | -0.41171272 | 0.02303915 | 37.54143170 | -2.24464712 | -30.14317245 | none detected |
| 320 | -0.41190011 | 0.02300663 | 37.50556417 | -2.24094166 | -30.22850968 | none detected |
| 640 | -0.41195270 | 0.02299602 | 37.48855575 | -2.23845238 | -30.21774964 | none detected |

### Temporal Nt (fixed M=320, fixed base bumps)

| Setting | Delta | Gamma | Vega | Theta | Rho | Flags |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| 50 | -0.41190350 | 0.02301216 | 37.49607861 | -2.23991471 | -30.20648403 | none detected |
| 100 | -0.41190011 | 0.02300663 | 37.50556417 | -2.24094166 | -30.22850968 | none detected |
| 200 | -0.41189725 | 0.02300449 | 37.50657626 | -2.23989863 | -30.21389384 | none detected |

### Independent CRR steps (fixed base bumps, inspect even/odd separately)

| Setting | Delta | Gamma | Vega | Theta | Rho | Flags |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| 800 | -0.41182883 | 0.02360419 | 37.48054628 | -2.23764825 | -30.21063256 | none detected |
| 801 | -0.41204358 | 0.02276952 | 37.50150982 | -2.23819716 | -30.24188332 | none detected |
| 1600 | -0.41194614 | 0.02342555 | 37.48398720 | -2.23779897 | -30.21461271 | none detected |
| 1601 | -0.41196727 | 0.02259814 | 37.49448151 | -2.23806972 | -30.23022877 | none detected |

### Finer bump plateau (M=640, Nt=100; base spot bump=1.25, others unchanged)

| Setting | Delta | Gamma | Vega | Theta | Rho | Flags |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| 0.5 | -0.41110661 | 0.02299632 | 37.48806151 | -2.23857605 | -30.21569581 | none detected |
| 1 | -0.41127594 | 0.02299626 | 37.48855575 | -2.23845238 | -30.21774964 | none detected |
| 2 | -0.41195270 | 0.02299602 | 37.48384321 | -2.23870371 | -30.21414681 | none detected |

## call, S=100, r=0.02, q=0.1

### Bump scale (fixed M=320, Nt=100)

| Setting | Delta | Gamma | Vega | Theta | Rho | Flags |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| 0.25 | 0.44501667 | 0.05216241 | 35.20886103 | -1.55040394 | 21.59511979 | spot bump smaller than grid spacing: interpolation-limited |
| 0.5 | 0.44501667 | 0.02608121 | 35.20124868 | -1.55043272 | 21.59843899 | none detected |
| 1 | 0.44552676 | 0.02607178 | 35.18118281 | -1.55062052 | 21.60033068 | none detected |
| 2 | 0.44756838 | 0.02603436 | 35.18120391 | -1.55097514 | 21.59976144 | none detected |

### Spatial M (fixed Nt=100, fixed base bumps)

| Setting | Delta | Gamma | Vega | Theta | Rho | Flags |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| 160 | 0.44549743 | 0.02614920 | 35.37288652 | -1.56036785 | 21.73175245 | none detected |
| 320 | 0.44552676 | 0.02607178 | 35.18118281 | -1.55062052 | 21.60033068 | none detected |
| 640 | 0.44554034 | 0.02605384 | 35.15966428 | -1.54868591 | 21.57215252 | none detected |

### Temporal Nt (fixed M=320, fixed base bumps)

| Setting | Delta | Gamma | Vega | Theta | Rho | Flags |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| 50 | 0.44552950 | 0.02607759 | 35.16905918 | -1.55185193 | 21.60663559 | none detected |
| 100 | 0.44552676 | 0.02607178 | 35.18118281 | -1.55062052 | 21.60033068 | none detected |
| 200 | 0.44552447 | 0.02606951 | 35.18269220 | -1.55078203 | 21.60299356 | none detected |

### Independent CRR steps (fixed base bumps, inspect even/odd separately)

| Setting | Delta | Gamma | Vega | Theta | Rho | Flags |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| 800 | 0.44549175 | 0.02646869 | 35.15823126 | -1.54717818 | 21.58058606 | none detected |
| 801 | 0.44552466 | 0.02589806 | 35.17587477 | -1.54712827 | 21.59925494 | none detected |
| 1600 | 0.44552187 | 0.02634970 | 35.15805673 | -1.54795434 | 21.57095613 | none detected |
| 1601 | 0.44553136 | 0.02575067 | 35.16679982 | -1.54793823 | 21.58003329 | none detected |

### Finer bump plateau (M=640, Nt=100; base spot bump=1.25, others unchanged)

| Setting | Delta | Gamma | Vega | Theta | Rho | Flags |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| 0.5 | 0.44490404 | 0.02606563 | 35.15927888 | -1.54850920 | 21.57312259 | none detected |
| 1 | 0.44503128 | 0.02606327 | 35.15966428 | -1.54868591 | 21.57215252 | none detected |
| 2 | 0.44554034 | 0.02605384 | 35.15881036 | -1.54875498 | 21.57187383 | none detected |

## put, S=81, r=0.05, q=0

### Bump scale (fixed M=320, Nt=100)

| Setting | Delta | Gamma | Vega | Theta | Rho | Flags |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| 0.25 | -0.98860849 | 0.03645282 | 0.00000000 | -0.00000000 | 0.00000000 | exercise regime changes across repricings; spot bump smaller than grid spacing: interpolation-limited |
| 0.5 | -0.98481132 | 0.02430188 | 0.40740543 | -0.00000000 | 0.00000000 | exercise regime changes across repricings |
| 1 | -0.97375418 | 0.02099665 | 1.18782650 | -0.00000000 | 0.00000000 | exercise regime changes across repricings |
| 2 | -0.95149125 | 0.01940350 | 1.69609970 | -0.00000000 | -0.57721221 | exercise regime changes across repricings |

### Spatial M (fixed Nt=100, fixed base bumps)

| Setting | Delta | Gamma | Vega | Theta | Rho | Flags |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| 160 | -0.97272476 | 0.01794123 | 3.24318460 | -0.14294535 | -4.69161842 | exercise regime changes across repricings |
| 320 | -0.97375418 | 0.02099665 | 1.18782650 | -0.00000000 | 0.00000000 | exercise regime changes across repricings |
| 640 | -0.97407509 | 0.02047275 | 1.00809742 | -0.05735364 | -1.44236725 | exercise regime changes across repricings |

### Temporal Nt (fixed M=320, fixed base bumps)

| Setting | Delta | Gamma | Vega | Theta | Rho | Flags |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| 50 | -0.97380880 | 0.02095296 | 1.17568784 | -0.00000000 | 0.00000000 | exercise regime changes across repricings |
| 100 | -0.97375418 | 0.02099665 | 1.18782650 | -0.00000000 | 0.00000000 | exercise regime changes across repricings |
| 200 | -0.97373400 | 0.02101280 | 1.19210884 | -0.00000000 | 0.00000000 | exercise regime changes across repricings |

## Interpretation and limits

Compare h/2, h and 2h at FIXED mesh, then change M or Nt separately with FIXED bumps.
The .25 bump-scale row deliberately uses hS<dS to expose interpolation sensitivity.
The wider put spot-bump range 1.25/2.5/5 has Delta spread above the declared 0.003 budget.
That result is retained. The finer plateau independently fixes M=640 and varies spot bumps .625/1.25/2.5.
Tests retain Delta budget 0.003; they do not relax it to accommodate the wider-bump bias.
Comparing the two setups changes both mesh and spot-bump range; it does not isolate either error source.
Only the separate fixed-mesh bump and fixed-bump refinement studies are used for that assessment.
Smaller bumps do not guarantee better Greeks. Price interpolation and solver noise are amplified,
especially by the second spot difference. A mesh/bump plateau is empirical evidence, not an error bound.
The near-boundary put (S=81) can change exercise regime across bumps. No universal smooth derivative
or stable Gamma is asserted there. Even/odd CRR noise is separate from FD interpolation error.
In particular, near-boundary Theta is zero on M=320 across the temporal study but changes
when the spatial mesh is refined. Temporal stability alone must not be interpreted as Greek accuracy.
For the continuation put with fixed hS=2.5, CRR1600/1601 Gamma retains an even/odd spread
of about 0.000827; the independent method is not an exact sensitivity reference.
No global signs for American Theta/Rho or other numerical sensitivities are imposed.
PSOR residual tolerance does not bound sensitivity error. 'None detected' is not a stability certificate.
Expiry returns explicit unavailable sensitivities; domain edges use documented forward stencils.
This module does not implement portfolio scenarios or P&L.
