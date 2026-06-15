# Quant protocol helper — multi-protocol branching

Almost every quantitation report repeats the same branching: detect MS1 vs MS2, detect Average vs other MS1 protocols, enumerate components, iterate the right way for each protocol. This is a factored helper you can paste into your report or extract to a shared module.

The pattern is equivalent to what `reports/top-3.py` does across its three `calculateProteinIntensity*` functions, but with a single dispatch table instead of copy-pasted branches.

## Drop-in helper

Paste into your report (or a local `quant_protocol.py` next to it):

```python
"""Shared quant-protocol helper: detects the protocol and dispatches
protein-intensity extraction to the right implementation."""
import msparser


def describe_protocol(qMethod):
    """Return (is_ms1, is_average, protocol_name)."""
    protocol = qMethod.getProtocol()
    protocol_name = protocol.getType()   # 'average'|'precursor'|'replicate'|'reporter'|'multiplex'|'null'
    is_ms1 = protocol_name not in ('reporter', 'multiplex')
    is_average = is_ms1 and (protocol.getAverage() is not None)
    return is_ms1, is_average, protocol_name


def component_names(qMethod, include_avg_sentinel=True):
    """List of component names, 0-based iteration order.

    For Average protocols where there's effectively one virtual component,
    returns ['Avg'] when include_avg_sentinel is True. Set False if the
    caller prefers to handle the zero-component case itself."""
    names = [
        qMethod.getComponentByNumber(c).getName()
        for c in range(qMethod.getNumberOfComponents())
    ]
    if not names and include_avg_sentinel:
        names = ['Avg']
    return names


def iter_match_components(quant, protein, is_ms1):
    """Yield (match_or_key, component_accessor) tuples for every peptide
    match of `protein`, in protocol-appropriate form.

    For MS1:   match_or_key = ms_ms1quant_match      component_accessor = match.getComponent(name)
    For MS2:   match_or_key = ms_peptide_quant_key   component_accessor = quant.getComponentIntensities(key)[component_index]

    Caller code then branches on is_ms1 to extract values uniformly.
    """
    if is_ms1:
        hit_no    = protein.getHitNumber()
        member_no = protein.getMemberNumber()
        n = quant.getNumMatchesForHit(hit_no, member_no)
        for i in range(1, n + 1):
            yield quant.getMatchForHit(i, hit_no, member_no)
    else:
        keys = quant.getPeptideQuantKeys(protein.getAccession(), protein.getDB())
        for i in range(keys.size()):
            yield keys.get(i)


def match_intensity(quant, qMethod, match_or_key, component_name,
                    is_ms1, component_index=None, apply_quality_thresholds=True):
    """Extract the intensity value for (match, component).

    MS1: reads from match.getComponent(name).getAbsoluteValue(),
         optionally skipping matches that fail the method's quality thresholds.
    MS2: reads intensities[component_index] via quant.getComponentIntensities(key).

    Returns float intensity, or None if the match should be skipped.
    """
    if is_ms1:
        match = match_or_key
        if apply_quality_thresholds and not _passes_ms1_quality(qMethod, match):
            return None
        if not match.hasComponent(component_name):
            return None
        return match.getComponent(component_name).getAbsoluteValue()
    else:
        key = match_or_key
        intensities = quant.getComponentIntensities(key)
        if component_index is None:
            return None
        return intensities[component_index]


def _passes_ms1_quality(qMethod, match):
    """Check the method's MS1 quality thresholds. Returns False if the
    match should be excluded."""
    quality = qMethod.getQuality()
    cs_data = match.getChargeStateData()
    if quality.isIsolatedPrecursor():
        if cs_data.getMatchedFraction() < float(quality.getIsolatedPrecursorThreshold()):
            return False
    if quality.isTotalIntensity():
        if cs_data.getTotalIntensity() < float(quality.getTotalIntensityThreshold()):
            return False
    correlation = float(qMethod.getIntegration().getMatchedRho())
    if cs_data.getMatchedRho() < correlation:
        return False
    return True


def group_key(match_or_key, pepSum, selection_type, is_ms1):
    """Build the group-by key for a match, matching the three
    `unique_sequence`/`unique_mr`/`unique_mz` choices the standard wizard
    pages offer."""
    if is_ms1:
        m = match_or_key
        sequence = m.getPeptideString()
        mods     = m.getReadableLabelFreeVarMods()
        charge   = m.getChargeState()
    else:
        key = match_or_key
        ok, query, rank = key.getQueryAndRank()
        peptide = pepSum.getPeptide(query, rank)
        sequence = peptide.getPeptideStr()
        mods     = pepSum.getReadableVarMods(query, rank)
        charge   = peptide.getCharge()

    if selection_type == 'unique_sequence':
        return sequence
    if selection_type == 'unique_mr':
        return f"{sequence}_{mods}"
    if selection_type == 'unique_mz':
        return f"{sequence}_{mods}_{charge}"
    raise ValueError(f"Unknown selection_type: {selection_type}")
```

## How to use it

### Example 1 — top-N protein intensity across protocols

```python
from quant_protocol import (
    describe_protocol, component_names, iter_match_components,
    match_intensity, group_key,
)

def protein_intensity(quant, qMethod, pep_sum, protein, component_name,
                      component_index, selection_type, top_n):
    is_ms1, is_average, _ = describe_protocol(qMethod)

    # Average protocols have a dedicated API; don't walk matches manually.
    if is_average:
        include = msparser.ms_peptide_quant_key_vector()
        exclude = msparser.ms_peptide_quant_key_vector()
        ok, value = quant.getAveragePeptideIntensity(
            protein.getAccession(), protein.getDB(), include, exclude)
        return value if ok else None

    # Group matches by the user's selection type, sum within group, keep top N
    groups = {}
    for match_or_key in iter_match_components(quant, protein, is_ms1):
        intensity = match_intensity(
            quant, qMethod, match_or_key, component_name,
            is_ms1, component_index=component_index)
        if intensity is None:
            continue
        key = group_key(match_or_key, pep_sum, selection_type, is_ms1)
        groups[key] = groups.get(key, 0.0) + intensity

    if len(groups) < top_n:
        return None
    return sum(sorted(groups.values(), reverse=True)[:top_n]) / top_n
```

### Example 2 — enumerate every (match, component) pair for a protein

```python
is_ms1, _, _ = describe_protocol(qMethod)
names = component_names(qMethod)

for match_or_key in iter_match_components(quant, protein, is_ms1):
    for ci, comp_name in enumerate(names):
        intensity = match_intensity(
            quant, qMethod, match_or_key, comp_name,
            is_ms1, component_index=ci, apply_quality_thresholds=False)
        if intensity is None:
            continue
        # ...write a row...
```

## When NOT to use it

- **Average protocol's `getAveragePeptideIntensity`** is a one-shot API — don't walk matches yourself. The helper skips match iteration for average; you just call it directly (see Example 1).
- **MS2 reports that need both intensities AND ratios.** `getPeptideQuantKeys` covers intensities; `getProteinRatio` is separate. The helper covers the intensity path; add a parallel ratio path if you need both.
- **Reports that care about `isHitRatioOutlier`/`isHitRatioExcluded`** — those flags are per-match-per-ratio, not per-component-intensity. This helper deliberately stays out of ratio territory.

## Mental model

```
        describe_protocol()
        ┌──────────┬─────────────┐
        │          │             │
    Average      MS1          MS2
        │          │             │
    direct API    iter matches  iter keys
                  ┌─────┐       ┌─────┐
                  │ quality │   │ component │
                  │ threshold│  │ intensities[ci] │
                  └─────┘       └─────┘
                        │               │
                        ▼               ▼
                    group_key      group_key
                        │               │
                        ▼               ▼
                    sum + top-N
```

Keeping these three branches inside the helper lets the report's main loop be a single pass over `proteins × components` without the per-protocol special-casing.

## If/when to promote this into `reports/`

If two or more custom reports adopt this pattern, lift it into `<WORKSPACE>/reports/QuantProtocol.py` and import from there. Distiller picks up any new module in `reports/` at next launch — same deployment story as the existing helpers (`LoadQuantitation`, `WriteReports`, `CreateQuantDataFrames`).
