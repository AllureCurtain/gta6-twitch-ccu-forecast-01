# GTA VI Twitch CCU forecast

Entry for the make.fun competition `gta6-twitch-ccu-forecast-01`: forecast,
hour by hour, how many people watch Grand Theft Auto VI live on Twitch over
the 24 UTC hours of its release day, from the first hour's viewer count.

## What the program does

`main.py` (Python 3.13, standard library only, no network) reads one case
file from `$MAKEFUN_INPUT_DIR` (else `/input/`) and writes one forecast file
per case to `$MAKEFUN_OUTPUT_DIR` (else `/output/`), as
`{"hours": [{"hour": h, "q": [q05, q25, q50, q75, q95]}, ...]}` for hours
2–24.

## Method

Analog launches. Each case ships past big launches with their hourly viewer
counts. For each past launch, the program looks at the ratio of its viewers
in hour h to its viewers in hour 1, and fits one straight line per hour:

    log(viewers_h / viewers_1) ~ log(viewers_1)

The line captures the key pattern in the data: a launch whose first hour was
already huge has little headroom left, while one whose first hour was small
ramps much further (log peak ratio correlates about −0.79 with log hour-1
viewers across the comparables). The forecast reads the line off at this
launch's own hour-1 print. The spread is the residual standard deviation of
the fit, shrunk by 0.8, turned into normal quantiles on the log scale.

Only comparables that behave like a real launch day are used: all 24
release-day hours present, a positive hour-1 print, and hour 1 at least 1%
of the launch's peak. That drops simultaneous-global launches whose hour 1
was nearly dead before a later single unlock, and the target game's own
pre-release history, which has no release day yet.

The program is deterministic: two runs on the same case write byte-identical
output, in about 0.05 s per case.

## Practice results

Scored on the four practice cases (Marvel's Wolverine, Red Dead Redemption 2,
God of War Ragnarök, Marvel's Spider-Man 2) against their recorded hourly
counts, mean pinball loss on the log scale:

| case | this entry | house baseline |
|---|---|---|
| Marvel's Wolverine | 0.207 | 0.744 |
| Red Dead Redemption 2 | 0.200 | 0.287 |
| God of War Ragnarök | 0.175 | 0.215 |
| Marvel's Spider-Man 2 | 0.192 | 0.303 |
| **overall** | **0.193** | **0.387** |

Typical miss (median): 34.4% vs the baseline's 82.7%. 90% coverage: 1.000
vs 0.783. Leave-one-out over the 30 usable comparables gives a loss of
0.364 vs 0.462 for the baseline, so the advantage is not just the four
practice cases.

## Run it locally

```sh
mkdir -p out
MAKEFUN_INPUT_DIR=<kit>/input MAKEFUN_OUTPUT_DIR=out python3 main.py
```
