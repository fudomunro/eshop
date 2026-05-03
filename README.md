This projects retrieves data from the Nintendo e-shop and provides additional ways to filter it, beyond what is provided in the official UI.

In particular, we want filter games based on the percentage discount currently on offer.

There's an example request in `sample.curl` which we will use as our starting point.

## Usage

No external dependencies required — runs with Python 3 stdlib only.

```
python3 eshop_deals.py [OPTIONS]
```

### Options

| Flag | Description | Default |
|------|-------------|---------|
| `-d`, `--min-discount` | Minimum discount percentage to show | `0` |
| `-p`, `--price-range` | Filter by price range | all |
| `-n`, `--limit` | Max number of results to show | `40` |
| `-o`, `--csv` | Save results to a CSV file | none |
| `--no-cache` | Skip the local cache and fetch fresh data | cache enabled |

Responses are cached in `~/.cache/eshop_deals/` for 1 hour. Subsequent requests with the same filters and page reuse the cached response without hitting the API.

### Examples

Show all deals with at least 80% discount:

```
$ python3 eshop_deals.py -d 80
Found 10 deals with >= 80.0% discount

Title                                            Publisher        MSRP    Sale   Discount
-----------------------------------------------  ---------------  ------  -----  --------
Kartoon Racing: Singleplayer Multiplayer Racing  Weakfish Studio  $10.89  $1.08  90.1%
Pandaty                                          Weakfish Studio  $11.70  $1.17  90.0%
Boxerpunk Stories                                Weakfish Studio  $12.85  $1.28  90.0%
Gliding Square                                   Weakfish Studio  $5.10   $0.76  85.1%
Blacksmith Forger                                Weakfish Studio  $6.69   $1.00  85.1%
```

Filter by price range and discount, limit to 5 results:

```
$ python3 eshop_deals.py -p '$10 - $19.99' -d 30 -n 5
Found 5 deals with >= 30.0% discount

Title                           Publisher          MSRP    Sale    Discount
------------------------------  -----------------  ------  ------  --------
Fallen Legion Revenants         NIS America        $50.39  $10.07  80.0%
GRIP                            Wired Productions  $50.39  $10.07  80.0%
The Coma: Triple Threat Bundle  Headup Games       $44.99  $10.34  77.0%
Anime vs Evil: Apocalypse       Axyos Games        $34.00  $10.20  70.0%
CONSCRIPT                       Team17             $29.50  $10.03  66.0%
```

Save results to CSV:

```
$ python3 eshop_deals.py -d 70 -o deals.csv
```

This writes a CSV with columns `title,publisher,msrp,sale_price,discount_pct`:

```csv
title,publisher,msrp,sale_price,discount_pct
Kartoon Racing: Singleplayer Multiplayer Racing,Weakfish Studio,$10.89,$1.08,90.1
Pandaty,Weakfish Studio,$11.70,$1.17,90.0
Boxerpunk Stories,Weakfish Studio,$12.85,$1.28,90.0
```
