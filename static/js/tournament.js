$(function() {
	var playersTemplate;
	$.get("/static/mustache/players.mst", function(data) {
		playersTemplate = data;
		Mustache.parse(data);
	});

	$("#tournament").tabs();
	$.getJSON()
});
