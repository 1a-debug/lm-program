# Clamp contract

`clamp(value, lower, upper)` must constrain the result to the inclusive
`[lower, upper]` interval. Values below the lower bound return `lower`; values
above the upper bound return `upper`; values inside the interval are unchanged.
