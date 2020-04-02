$(function() {
	var ranks = ["1st", "2nd", "3rd", "4th", "5th"];

	function drawRankData(svg_selection, legend_selection, rankhist) {
		var rect = svg_selection.nodes()[0].getBoundingClientRect(),
			width = rect.width || 800,
			height = rect.height || 500,
			outerRadius = Math.min(height, width) / 2 - 10,
			innerRadius = outerRadius / 3,
			labelInnerRadius = outerRadius * 0.5,
			path = d3.arc().innerRadius(innerRadius).outerRadius(outerRadius),
			label = d3.arc().innerRadius(labelInnerRadius).outerRadius(
				outerRadius),
			nonzero = rankhist.filter(function(d) {
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
		for (prop in rankhist[0]) {
			columns.push(prop)
		}

		// Build a table for the legend that shows all the ranks and counts
		var rows = legend_selection.selectAll("tr").data(rankhist).enter().
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
			return d.column == 'rank' ? ranks[d.value - 1] : d.value
		});
	}

	function redrawRankDataInTab(ev, ui) {
		var statsummarytable = $(ui.newPanel).find(".statsummarytable"),
			tourneyID = statsummarytable.data('tourneyid');
		drawRankData(d3.select(statsummarytable.get(0)).select('svg'),
			d3.select(statsummarytable.get(0)).select('.rankpielegend'),
			rank_histograms[tourneyID]);
	};

	$("#playerstats").tabs({
		active: activeTab,
		activate: redrawRankDataInTab,
	});

	d3.selectAll(".statsummarytable").each(function(d, i) {
		var tourneyID = $(this).data('tourneyid');
		drawRankData(d3.select(this).select('svg'),
			d3.select(this).select('.rankpielegend'),
			rank_histograms[tourneyID]);
	});

});
