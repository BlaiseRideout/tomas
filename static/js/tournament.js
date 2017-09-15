$(function() {
	var playersTemplate;
	$.get("/static/mustache/players.mst", function(data) {
		playersTemplate = data;
		Mustache.parse(data);
		$.getJSON("/players", function(data) {
			$("#players").html(Mustache.render(playersTemplate, {players:data}));
		});
	});

	$("#tournament").tabs();
});
