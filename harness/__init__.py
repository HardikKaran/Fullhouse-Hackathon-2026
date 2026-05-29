"""Dev harness around the frozen Fullhouse engine.

Importing anything under `harness` pulls in `harness.paths`, which bootstraps
the vendored engine onto sys.path. Submodules:

  paths    engine bootstrap + constants + canonical bot file paths
  metrics  bb/100 win-rate + 95% confidence interval
  duel     heads-up, seat-rotated, multi-match (hero vs one villain)
  table    6-max table (hero vs five reference bots), seat-rotated
  gauntlet hero vs every reference bot + the 6-max table -> summary
"""
