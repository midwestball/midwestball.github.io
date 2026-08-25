### Context
Discrete catalog stats were published as histograms (`bins[]`) and Knowball branched chart + CDF paths, which blocked a single inclusive standing contract. Rug-plot `samples[]` on league JSON existed only for a viz experiment that is no longer in product.

### Decision
Ballnet fits a reflected Gaussian KDE for every published catalog `stat.id` and emits `curve[]` (plus domain / `yMax` / catalog bounds). Knowball charts only that KDE. Catalog `kind: discrete` stays as formatting metadata; it does not select a histogram. League files do not include `bins` or `samples`.

### Consequences
- Inclusive CDF is `kdeCdf` on the plotted curve for every stat; `histogramCdf` and histogram bars are retired.
- Ready ⟺ qualified + non-empty `curve[]` after league merge. Do not re-embed curves on player pages.
- Do not invent curves from leftover `bins` in Knowball. Republish Stage D → E → `league/` (+ pages, because discrete percentiles change).
- Histogram / rug-plot notes in older ADRs and the ETL brief are superseded by this record.
