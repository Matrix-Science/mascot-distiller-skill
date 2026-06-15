# Visualization recipes

Patterns for producing graphs and plots from a Distiller report. Covers the existing `CreateGraphs.py` helpers plus ready-to-paste snippets for plots the standard helpers don't cover.

## What's already available

`<WORKSPACE>/reports/CreateGraphs.py` ships with Distiller. Import and use — don't reimplement.

| Function (selected) | Produces |
|---------------------|----------|
| `createBoxplotGraphs(...)` | Box-and-whisker for ratio distributions (Plotly or matplotlib) |
| `createAlignmentStatsGraph(...)` | RT alignment quality stats across samples |
| `createAlignmentGraphs(...)` | Per-sample time-shift traces |
| `createCountGraphs(...)` / `createRelativeCountGraphs(...)` | Identified-vs-non-identified peptide counts |
| `createVolcanoPlotlyGraphs(...)` / `createVolcanoPyplotGraphs(...)` | Volcano plots for t-test results |
| `createPCAGraph(...)` / `createPCAPlotlyGraph(...)` | PCA scatter plots |
| `createPCAGraphForKmeans(...)` | PCA coloured by k-means cluster |
| `createClusteringGraphs(...)` | Hierarchical cluster heatmaps |
| `createPeptideGraphs(...)` | Per-peptide distribution plots |
| `createQualityGraphs(...)` | Quality-metric plots |
| `createFrequencyGraphs(...)` | Intensity frequency histograms |

These take broadly uniform signatures: `(data_df, ..., usePlotly, useSVG, ...)`. Check the source for each function's exact arguments.

Standard companion modules:
- `StatisticsOperations.py` — PCA, k-means, ANOVA, t-test helpers (returns the frames the graph functions expect)
- `FormatDataFrames.py` — post-processing for display
- `Imputation.py` — handling missing values before plotting

## Plotly HTML embedding (CDN-loaded)

Pattern used across the standard reports. Writes a single HTML file with the Plotly div and a CDN script reference:

```python
import plotly.graph_objs as go
from plotly.offline import plot as plotly_plot

def render_plotly_html(figures, save_path, title="Report"):
    """Embed one or more Plotly figures into a single HTML file."""
    parts = [
        "<!DOCTYPE html><html><head>",
        "<meta charset='utf-8'>",
        f"<title>{title}</title>",
        "<style>body{font-family:Segoe UI,Arial,sans-serif;margin:1.2em}</style>",
        "</head><body>",
    ]
    for i, fig in enumerate(figures):
        parts.append(plotly_plot(
            fig, output_type='div',
            include_plotlyjs='cdn' if i == 0 else False,
        ))
    parts.append("</body></html>")
    with open(save_path, "w", encoding="utf-8") as f:
        f.write("\n".join(parts))
```

Use `include_plotlyjs='cdn'` only on the first figure — subsequent ones reuse the loaded library. Setting it to `True` embeds ~3 MB of Plotly source per figure, which bloats the file.

> **Wrap inline JS in a load listener.** See CLAUDE.md: "Inline JS in HTML reports must be wrapped in `window.addEventListener('load', ...)` to avoid CDN race conditions (e.g., Plotly)." If you hand-write `<script>` blocks that interact with Plotly divs, don't run them at parse time.

## matplotlib SVG pattern

```python
import matplotlib
matplotlib.use("Agg")   # No display — Distiller runs headless
import matplotlib.pyplot as plt
import io

def fig_to_svg_string(fig):
    buf = io.StringIO()
    fig.savefig(buf, format="svg", bbox_inches="tight")
    plt.close(fig)
    return buf.getvalue()

# Embed into HTML
svg = fig_to_svg_string(fig)
# svg already contains a complete <svg>...</svg> element — paste it directly
# into your HTML; no image tag required.
```

Choose matplotlib over Plotly when:
- The report output is strictly CSV/SVG/PNG (no HTML + CDN)
- The plot is going into a PDF workflow downstream
- Interactivity isn't needed

Plotly when:
- The report output is HTML
- You want hover tooltips, zoom, or toggleable legends
- You want the plot to be readable on a wide range of screen sizes

## Recipe: XIC overlay (multiple peptides, multiple charge states)

Given the XIC extraction pattern from [REPORT_EXAMPLES.md](REPORT_EXAMPLES.md) Example 6, overlay multiple peptide traces on one axis:

```python
import plotly.graph_objs as go

def xic_overlay_figure(xic_traces, title="XIC overlay"):
    """xic_traces: list of dicts with keys 'label', 'rts', 'intensities',
       'rt_peak_start', 'rt_peak_end' (optional)."""
    fig = go.Figure()
    for t in xic_traces:
        fig.add_trace(go.Scatter(
            x=t['rts'], y=t['intensities'],
            mode='lines', name=t['label'],
            hovertemplate=(
                "<b>%{fullData.name}</b><br>"
                "RT: %{x:.1f} s<br>Intensity: %{y:.2e}<extra></extra>"
            ),
        ))
    # Shade the integrated peak region of the first trace (all should overlap)
    first = xic_traces[0]
    if 'rt_peak_start' in first and 'rt_peak_end' in first:
        fig.add_vrect(
            x0=first['rt_peak_start'], x1=first['rt_peak_end'],
            fillcolor='LightSalmon', opacity=0.25, line_width=0,
            annotation_text='Integrated peak', annotation_position='top left',
        )
    fig.update_layout(
        title=title,
        xaxis_title='Retention time (s)',
        yaxis_title='Intensity',
        height=380, hovermode='x unified',
        margin=dict(l=60, r=20, t=50, b=50),
    )
    return fig
```

## Recipe: Annotated MS2 spectrum (fragment b/y ions)

Requires you already have the scan's peaks (pulled from the raw file via MDRO — see the `mascot-mdro` skill) and the matched peptide's fragment ion series (from msparser's `ms_fragmentationrules`/`ms_peptide`).

```python
def annotated_ms2_figure(peaks, fragments, peptide_seq, charge):
    """peaks: list of (mz, intensity) tuples.
       fragments: list of dicts {'mz': float, 'label': 'b3', 'type': 'b'}."""
    import plotly.graph_objs as go
    fig = go.Figure()
    # Base spectrum as sticks
    fig.add_trace(go.Bar(
        x=[mz for mz, _ in peaks],
        y=[intensity for _, intensity in peaks],
        width=0.3, marker_color='#888', name='MS2',
        hovertemplate='m/z %{x:.3f}<br>Intensity %{y:.2e}<extra></extra>',
    ))
    # Annotated fragment peaks on top in colour
    by_type = {'b': '#d62728', 'y': '#1f77b4', 'a': '#9467bd', 'c': '#2ca02c', 'z': '#ff7f0e'}
    for frag in fragments:
        color = by_type.get(frag['type'], '#000')
        # Find nearest peak in the spectrum
        nearest = min(peaks, key=lambda p: abs(p[0] - frag['mz']))
        fig.add_trace(go.Bar(
            x=[nearest[0]], y=[nearest[1]],
            marker_color=color, width=0.4,
            name=frag['label'], showlegend=False,
        ))
        fig.add_annotation(
            x=nearest[0], y=nearest[1],
            text=frag['label'], textangle=-90,
            font=dict(color=color, size=10),
            showarrow=False, yshift=12,
        )
    fig.update_layout(
        title=f"MS2: {peptide_seq} +{charge}",
        xaxis_title='m/z', yaxis_title='Intensity',
        bargap=0, showlegend=False, height=350,
    )
    return fig
```

## Recipe: Protein intensity heatmap (log-scale, clustered)

```python
import numpy as np
import plotly.graph_objs as go

def intensity_heatmap(df, value_col='intensity', row_col='accession',
                       col_col='sample', log=True):
    """Pivot a long-form DataFrame into a sample-by-protein heatmap."""
    pivot = df.pivot_table(
        index=row_col, columns=col_col, values=value_col, aggfunc='mean'
    )
    values = pivot.values.astype(float)
    if log:
        values = np.where(values > 0, np.log10(values), np.nan)

    fig = go.Figure(go.Heatmap(
        z=values,
        x=pivot.columns.tolist(),
        y=pivot.index.tolist(),
        colorscale='Viridis',
        colorbar=dict(title='log10(int)' if log else 'intensity'),
        hovertemplate=(
            '%{y}<br>%{x}<br>'
            + ('log10 %{z:.2f}' if log else '%{z:.2e}')
            + '<extra></extra>'
        ),
    ))
    fig.update_layout(
        title='Protein intensity heatmap',
        xaxis=dict(tickangle=-45), yaxis=dict(autorange='reversed'),
        height=min(1400, 25 * len(pivot.index) + 150),
    )
    return fig
```

For hierarchical clustering along rows/columns, use `scipy.cluster.hierarchy.linkage` to compute the order then reindex `pivot` before plotting — or delegate to `StatisticsOperations.createClusteringGraphs()` which already does this.

## Recipe: Rank-abundance plot (log-log)

Useful for showing dynamic range of a proteome sample:

```python
def rank_abundance_figure(intensities, label='sample'):
    import plotly.graph_objs as go
    sorted_ints = sorted(intensities, reverse=True)
    ranks = list(range(1, len(sorted_ints) + 1))
    fig = go.Figure(go.Scatter(
        x=ranks, y=sorted_ints, mode='markers+lines',
        marker=dict(size=3), name=label,
    ))
    fig.update_layout(
        title=f'Rank-abundance — {label}',
        xaxis=dict(title='Rank', type='log'),
        yaxis=dict(title='Intensity', type='log'),
        height=380,
    )
    return fig
```

## Recipe: RT–intensity scatter (peptide identification density)

```python
def rt_intensity_scatter(peptides, identified_col='identified'):
    """peptides: list of dicts with 'rt', 'log_intensity', 'identified' (bool)."""
    import plotly.graph_objs as go
    traces = []
    for flag, label, color in [
        (False, 'Unidentified', '#cccccc'),
        (True,  'Identified',   '#1f77b4'),
    ]:
        pts = [p for p in peptides if p[identified_col] is flag]
        traces.append(go.Scatter(
            x=[p['rt'] for p in pts],
            y=[p['log_intensity'] for p in pts],
            mode='markers', name=label,
            marker=dict(size=3, color=color, opacity=0.6),
        ))
    fig = go.Figure(traces)
    fig.update_layout(
        title='Peptide RT vs. log intensity',
        xaxis_title='Retention time (s)',
        yaxis_title='log10 intensity',
        height=380, legend=dict(itemsizing='constant'),
    )
    return fig
```

## Output format decision matrix

| Want | Use |
|------|-----|
| Static, embeddable in Word/PDF | matplotlib → PNG (`useSVG=False`) |
| Scalable, editable in Illustrator | matplotlib → SVG |
| Interactive, viewed in browser | Plotly → HTML (CDN-loaded) |
| Fully-offline HTML | Plotly → HTML (`include_plotlyjs=True`, one-time ~3 MB cost) |
| CSV-only (no graph) | pandas `df.to_csv()` — the simplest path, often the right choice |

## Common mistakes

- **Using the default matplotlib backend.** On headless Distiller it will fail. Always `matplotlib.use("Agg")` before `import pyplot`.
- **Embedding Plotly JS on every figure.** Pass `include_plotlyjs='cdn'` or `True` once; `False` for the rest.
- **Not sorting the x-axis.** Retention-time traces look nonsensical when points aren't sorted. Always `sorted(points, key=lambda p: p['rt'])` first.
- **Linear axis on dynamic-range data.** Protein intensities span 6-10 orders of magnitude; a linear-y plot shows you only the top two. Use `yaxis=dict(type='log')`.
- **Plotting every protein.** A figure with 5000 traces renders for minutes and browses for longer. Cap at top-50 or filter by statistical threshold first.
- **Forgetting `hovermode='x unified'`** for chromatograms — without it, you can't compare intensities at the same RT across traces.
