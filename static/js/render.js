/* Renders VisualizationSpec using Chart.js and D3.js */

const CHART_COLORS = [
  "#0d6e6e",
  "#2a9d8f",
  "#e9c46a",
  "#f4a261",
  "#e76f51",
  "#457b9d",
  "#6d597a",
  "#8ecae6",
];

let activeChart = null;

function fieldName(encoding, role, fallback) {
  const value = encoding?.[role];
  if (value === undefined || value === null || value === "") return fallback;
  return value;
}

function rowValue(row, key) {
  const value = row?.[key];
  return value === undefined || value === null ? "" : value;
}

function numericValue(row, key) {
  const value = Number(row?.[key]);
  return Number.isFinite(value) ? value : 0;
}

function inferLabelField(data, encoding) {
  return (
    fieldName(encoding, "x", null) ||
    fieldName(encoding, "label", null) ||
    Object.keys(data[0] || {}).find((k) => typeof data[0][k] === "string") ||
    "label"
  );
}

function inferValueField(data, encoding) {
  return (
    fieldName(encoding, "y", null) ||
    fieldName(encoding, "value", null) ||
    Object.keys(data[0] || {}).find((k) => typeof data[0][k] === "number") ||
    "value"
  );
}

function destroyActiveChart() {
  if (activeChart) {
    activeChart.destroy();
    activeChart = null;
  }
}

function clearChartRoot() {
  const root = document.getElementById("chart-root");
  const canvas = document.getElementById("chart-canvas");
  if (root) root.innerHTML = "";
  if (canvas) canvas.hidden = true;
  destroyActiveChart();
  document.querySelectorAll(".d3-tooltip").forEach((el) => el.remove());
}

function renderMetricCards(viz, root) {
  const labelField = inferLabelField(viz.data, viz.encoding);
  const valueField = inferValueField(viz.data, viz.encoding);
  const grid = document.createElement("div");
  grid.className = "metric-grid";

  viz.data.forEach((row) => {
    const card = document.createElement("div");
    card.className = "metric-card";
    card.innerHTML = `
      <div class="label">${rowValue(row, labelField)}</div>
      <div class="value">${rowValue(row, valueField)}</div>
    `;
    grid.appendChild(card);
  });

  root.appendChild(grid);
}

function renderTable(viz, root) {
  const table = document.createElement("table");
  table.className = "data-table";

  const columns = Array.from(
    viz.data.reduce((set, row) => {
      Object.keys(row).forEach((key) => set.add(key));
      return set;
    }, new Set())
  );

  const thead = document.createElement("thead");
  const headRow = document.createElement("tr");
  columns.forEach((col) => {
    const th = document.createElement("th");
    th.textContent = col.replace(/_/g, " ");
    headRow.appendChild(th);
  });
  thead.appendChild(headRow);
  table.appendChild(thead);

  const tbody = document.createElement("tbody");
  viz.data.forEach((row) => {
    const tr = document.createElement("tr");
    columns.forEach((col) => {
      const td = document.createElement("td");
      const value = rowValue(row, col);
      if (col.toLowerCase().includes("nct")) {
        const link = document.createElement("a");
        link.href = `https://clinicaltrials.gov/study/${value}`;
        link.target = "_blank";
        link.rel = "noopener";
        link.textContent = value;
        td.appendChild(link);
      } else {
        td.textContent = value;
      }
      tr.appendChild(td);
    });
    tbody.appendChild(tr);
  });
  table.appendChild(tbody);

  const wrap = document.createElement("div");
  wrap.className = "table-wrap";
  wrap.appendChild(table);
  root.appendChild(wrap);
}

function renderChartJs(viz, type) {
  const canvas = document.getElementById("chart-canvas");
  if (!canvas || !window.Chart) return;

  const labelField = inferLabelField(viz.data, viz.encoding);
  const valueField = inferValueField(viz.data, viz.encoding);
  const labels = viz.data.map((row) => rowValue(row, labelField));
  const values = viz.data.map((row) => numericValue(row, valueField));

  canvas.hidden = false;
  destroyActiveChart();

  const isCircular = type === "pie" || type === "doughnut";

  activeChart = new Chart(canvas, {
    type,
    data: {
      labels,
      datasets: [
        {
          label: viz.y_axis?.label || valueField,
          data: values,
          backgroundColor: type === "line" ? "rgba(13, 110, 110, 0.15)" : CHART_COLORS,
          borderColor: "#0d6e6e",
          borderWidth: type === "line" ? 2 : 1,
          tension: 0.25,
          fill: type === "line",
        },
      ],
    },
    options: {
      responsive: true,
      maintainAspectRatio: true,
      cutout: type === "doughnut" ? "55%" : undefined,
      plugins: {
        legend: { display: isCircular, position: "right" },
        title: { display: false },
      },
      scales: isCircular
          ? {}
          : {
              x: {
                title: {
                  display: Boolean(viz.x_axis?.label),
                  text: viz.x_axis?.label || labelField,
                },
              },
              y: {
                beginAtZero: true,
                title: {
                  display: Boolean(viz.y_axis?.label),
                  text: viz.y_axis?.label || valueField,
                },
              },
            },
    },
  });
}

function renderGroupedBarD3(viz, root) {
  if (!window.d3) return;

  const xField = fieldName(viz.encoding, "x", inferLabelField(viz.data, viz.encoding));
  const yField = fieldName(viz.encoding, "y", inferValueField(viz.data, viz.encoding));
  const groupField =
    fieldName(viz.encoding, "color", null) ||
    fieldName(viz.encoding, "group", null) ||
    Object.keys(viz.data[0] || {}).find(
      (k) => k !== xField && k !== yField && typeof viz.data[0][k] === "string"
    );

  const width = root.clientWidth || 720;
  const height = 380;
  const margin = { top: 20, right: 20, bottom: 56, left: 52 };

  const svg = d3
    .select(root)
    .append("svg")
    .attr("viewBox", `0 0 ${width} ${height}`)
    .attr("width", "100%")
    .attr("height", height);

  const innerWidth = width - margin.left - margin.right;
  const innerHeight = height - margin.top - margin.bottom;
  const g = svg.append("g").attr("transform", `translate(${margin.left},${margin.top})`);

  const categories = [...new Set(viz.data.map((d) => rowValue(d, xField)))];
  const groups = groupField
    ? [...new Set(viz.data.map((d) => rowValue(d, groupField)))]
    : ["value"];

  const x0 = d3.scaleBand().domain(categories).range([0, innerWidth]).padding(0.2);
  const x1 = d3.scaleBand().domain(groups).range([0, x0.bandwidth()]).padding(0.08);
  const y = d3
    .scaleLinear()
    .domain([0, d3.max(viz.data, (d) => numericValue(d, yField)) || 1])
    .nice()
    .range([innerHeight, 0]);

  const color = d3.scaleOrdinal(CHART_COLORS).domain(groups);

  const tooltip = d3
    .select("body")
    .append("div")
    .attr("class", "d3-tooltip");

  g.append("g")
    .attr("transform", `translate(0,${innerHeight})`)
    .attr("class", "d3-axis")
    .call(d3.axisBottom(x0));

  g.append("g").attr("class", "d3-axis").call(d3.axisLeft(y).ticks(6));

  const categoryGroups = g
    .selectAll("g.category")
    .data(categories)
    .join("g")
    .attr("class", "category")
    .attr("transform", (d) => `translate(${x0(d)},0)`);

  categoryGroups
    .selectAll("rect")
    .data((category) =>
      groups.map((group) => ({
        category,
        group,
        value: groupField
          ? numericValue(
              viz.data.find(
                (row) =>
                  rowValue(row, xField) === category && rowValue(row, groupField) === group
              ) || {},
              yField
            )
          : numericValue(
              viz.data.find((row) => rowValue(row, xField) === category) || {},
              yField
            ),
      }))
    )
    .join("rect")
    .attr("x", (d) => x1(d.group))
    .attr("y", (d) => y(d.value))
    .attr("width", x1.bandwidth())
    .attr("height", (d) => innerHeight - y(d.value))
    .attr("fill", (d) => color(d.group))
    .attr("rx", 4)
    .on("mousemove", (event, d) => {
      tooltip
        .style("opacity", 1)
        .html(`<strong>${d.category}</strong><br>${d.group}: ${d.value}`)
        .style("left", `${event.pageX + 12}px`)
        .style("top", `${event.pageY - 18}px`);
    })
    .on("mouseleave", () => tooltip.style("opacity", 0));
}

function renderVisualization(viz) {
  clearChartRoot();
  const root = document.getElementById("chart-root");
  if (!root || !viz) return;

  switch (viz.chart_type) {
    case "metric_cards":
      renderMetricCards(viz, root);
      break;
    case "table":
      renderTable(viz, root);
      break;
    case "pie":
      renderChartJs(viz, "pie");
      break;
    case "donut":
      renderChartJs(viz, "doughnut");
      break;
    case "line":
      renderChartJs(viz, "line");
      break;
    case "grouped_bar":
      renderGroupedBarD3(viz, root);
      break;
    case "bar":
    default:
      renderChartJs(viz, "bar");
      break;
  }
}

function renderTrials(trials) {
  const table = document.getElementById("trials-table");
  if (!table) return;

  const tbody = table.querySelector("tbody");
  if (!tbody) return;

  tbody.innerHTML = "";
  if (!trials?.length) return;

  trials.forEach((trial) => {
    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td><a href="https://clinicaltrials.gov/study/${trial.nct_id}" target="_blank" rel="noopener">${trial.nct_id}</a></td>
      <td>${trial.title}</td>
      <td>${trial.status || "—"}</td>
      <td>${(trial.phases || []).join(", ") || "—"}</td>
      <td>${trial.sponsor || "—"}</td>
    `;
    tbody.appendChild(tr);
  });
}

window.VisualizationRenderer = {
  renderVisualization,
  renderTrials,
};
