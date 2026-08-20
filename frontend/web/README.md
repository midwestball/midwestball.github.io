# Knowball frontend lab

Next.js prototype for the public stats UI. Data ingestion lives in the private `ballnet` backend — this app uses mocked league distributions only.

## ExpandableStatRow

Tremor / Recharts implementation. Sliders share a 0–100 percentile track. Distribution charts use the raw stat scale; copy and tooltips explain rank and relative frequency.

```bash
npm install
npm run dev
```

Open [http://localhost:3000](http://localhost:3000).
