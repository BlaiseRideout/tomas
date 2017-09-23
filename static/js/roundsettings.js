$(function() {
	$("#addround").click(function() {
		$.post("/addround", function(data) {
			if (data['status'] === "success")
				updateTab();
		}, "json");
	});
	$(".deleteround").click(function() {
		$.post("/deleteround", {
			'round': $(this).parent().data("roundid")
		}, function(data) {
			if (data['status'] === "success")
				updateTab();
			else
				console.log(data);
		}, "json");
	});
	var updateSetting = function() {
		var round = $(this).parent().data("roundid");
		var settings = {};
		console.log($(this).val());
		if ($(this).attr('type') === "checkbox")
			settings[$(this).data("colname")] = $(this).prop('checked') ? 1 : 0;
		else
			settings[$(this).data("colname")] = $(this).val();
		console.log(settings);
		$.post("/settings", {
			'round': round,
			'settings': JSON.stringify(settings)
		}, function(data) {
			if (data['status'] !== "success")
				console.log(data);
		}, "json");

	}
	fillSelect("/algorithms", "span.algorithmselect", "Name", "Id", function() {
		$(".roundsetting").change(updateSetting).keyup(updateSetting);
	});
	fillSelect("/orderings", "span.orderingselect", "Name", "Id", function() {
		$(".roundsetting").change(updateSetting).keyup(updateSetting);
	});
});
