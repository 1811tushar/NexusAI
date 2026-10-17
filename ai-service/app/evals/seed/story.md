# The planted story (ground truth for the demo and the evaluation)

Generated with seed 20260101. All numbers below are computed from the seed SQL, not typed by hand.

**Hero question:** Why did Q2 revenue decline compared to Q1, and what should management investigate?

* **Outcome:** total revenue fell from 2,768,725.00 (Q1 2026) to 2,605,975.00 (Q2 2026): -162,750.00 (-5.9%).
* **PRIMARY cause - West / Home:** 345,150.00 -> 189,840.00 (-45.0%), which is 95.4% of the net change.
  Documents explain it: supplier stock-out (May-June) plus a competitor price cut in the West from mid-April. Only the documents give the *why*; only SQL gives the exact numbers.
* **SECONDARY cause - South marketing cut:** South marketing spend 68,364.20 -> 45,784.95 (-33.0%) in April-May.
  South revenue changed by -66,705.00 (41.0% of the net change); South new customers 1,330 -> 965.
* **RED HERRING - East / Apparel:** -4.6% Q2 vs Q1 2026, but the same seasonal dip appears in 2025 (-6.3%). Not a cause.
* **GROWTH - North / Electronics:** 20.8% Q2 vs Q1.
* **Conflicting document:** the regional digest claims East apparel was the main driver and that West revenue rose. The data says otherwise.
* **Facts only in documents:** supplier name and dates, competitor name and discount, approval thresholds, planned budgets. **Facts only in SQL:** per-product numbers, customer counts.
