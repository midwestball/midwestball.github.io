# Projection UI boundaries

- Projection data is public, schema-versioned Storage JSON. Never add credentials or a Supabase client.
- Forecast distributions are separate from historical league statistics.
- Use published entity paths. Never construct object names from entity keys.
- The published PDF geometry defines probability calculations and chart shading.
- At most four unique entities may be selected.
