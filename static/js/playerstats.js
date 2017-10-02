$(function() {
	var playerstats;
	$.get("/static/mustache/playerstats.mst", function(data) {
		playerstats = data;
		Mustache.parse(playerstats);
		var parts = document.URL.split('/');
		player = parts[parts.length - 1];
		getData(player);
	});

	function getData(player) {
		$.getJSON("/playerstatsdata/" + player, function(data) {
			$("#playerstats").html(Mustache.render(playerstats, data));
			d3.selectAll(".playerstatperiod").each(function(d, i) {
				drawData(d3.select(this).select('svg'),
					d3.select(this).select('.rankpielegend'),
					data['playerstats'][i]['rank_histogram']);
			})
		});
	}

	function drawData(svg_selection, legend_selection, data) {
		var rect = svg_selection.nodes()[0].getBoundingClientRect(),
			width = rect.width || 800,
			height = rect.height || 500,
			outerRadius = Math.min(height, width) / 2 - 10,
			innerRadius = outerRadius / 3,
			labelInnerRadius = outerRadius * 0.5,
			path = d3.arc().innerRadius(innerRadius).outerRadius(outerRadius),
			label = d3.arc().innerRadius(labelInnerRadius).outerRadius(
				outerRadius),
			nonzero = data.filter(function(d) {
				return d.count > 0
			}),
			arcs = d3.pie().sort(null).value(function(d) {
				return d.count
			})(
				nonzero),
			g = svg_selection.html(""). // Remove any error message
		append("g"). // Make group node in svg
		attr("class", "rankpiechart"). // for pie chart
		attr("transform", // w/ transform
			"translate(" + width / 2 + "," + height / 2 + ")");
		// Create pie slices for each rank with a non-zero count
		g.selectAll(".arc").data(arcs).enter().
		append("g").classed("arc", true).append("path").attr("d", path).
		attr("class", function(d) {
			return "rank_" + d.data.rank + "_path rank_path"
		});
		// Label each slice near the outer edge with that rank's count
		g.selectAll("text").data(arcs).enter().
		append("text").attr("transform", function(d) {
			return "translate(" + label.centroid(d) + ")";
		}).
		attr("dy", "0.35em").attr("dx", function(d) {
			return ((d.data.count + "").length / -2.0 + 0.2) + 'em';
		}).
		text(function(d) {
			return d.data.count
		}).
		attr("class", function(d) {
			return "rank_" + d.data.rank + "_count rank_count"
		});
		var columns = []
		for (prop in data[0]) {
			columns.push(prop)
		}

		// Build a table for the legend that shows all the ranks and counts
		var rows = legend_selection.selectAll("tr").data(data).enter().
		append("tr"),
			cells = rows.selectAll("td").
		data(function(row) {
			return columns.map(function(col) {
				return {
					column: col,
					value: row[col]
				};
			})
		}).
		enter().append("td").
		attr("class", function(d) {
			return d.column + "_" + d.value + "_label " +
				d.column + "_label"
		}).text(function(d) {
			return d.value
		});
	}
});
