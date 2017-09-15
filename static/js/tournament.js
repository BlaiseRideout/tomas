$(function() {
	var templates = {};
	function renderTemplate(template, endpoint, selector, callback) {
		if(templates[template] === undefined)
			$.get("/static/mustache/" + template, function(data) {
				Mustache.parse(data);
				templates[template] = data;
				renderTemplate(template, endpoint, selector, callback);
			});
		else
			$.getJSON(endpoint, function(data) {
				$(selector).html(Mustache.render(templates[template], data));
				if(typeof callback === "function")
					callback(data);
			});
	}
	function updatePlayers() {
		renderTemplate("players.mst", "/players", "#players");
	}
	function updateStandings() {
		renderTemplate("leaderboard.mst", "/leaderboard", "#standings");
	}
	function updateSettings() {
		renderTemplate("settings.mst", "/settings", "#settings", function() {
			$("#addround").click(function() {
				$.post("/addround", function(data) {
					if(data['status'] === "success")
						updateSettings();
				}, "json");
			});
			$(".deleteround").click(function() {
				$.post("/deleteround", {'round':$(this).parent().data("roundid")}, function(data) {
					if(data['status'] === "success")
						updateSettings();
					else
						console.log(data);
				}, "json");
			});
			var updateSetting = function() {
				var round = $(this).parent().data("roundid");
				var settings = {};
				console.log($(this).val());
				if($(this).attr('type') === "checkbox")
					settings[$(this).data("colname")] = $(this).prop('checked')?1:0;
				else
					settings[$(this).data("colname")] = $(this).val();
				console.log(settings);
				$.post("/settings", {'round':round, 'settings':JSON.stringify(settings)}, function(data) {
					if(data['status'] !== "success")
						console.log(data);
				}, "json");

			}
			$(".roundsetting").change(updateSetting).keyup(updateSetting);
		});
	}
	function update() {
		updatePlayers();
		updateSettings();
		updateStandings();
	}
	update();
	$("#tournament").tabs();
});
