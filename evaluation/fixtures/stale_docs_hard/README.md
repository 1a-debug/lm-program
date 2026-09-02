# Calculator

## Known limitation

`divide` currently allows a zero divisor to reach Python's division operator,
which raises `ZeroDivisionError`. It must be updated to raise a clear
`ValueError` instead.
