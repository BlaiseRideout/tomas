$(function() {
	$("#addround").click(function() {
		$.post("/addround", function(data) {
			if (data['status'] === "success")
				updateTab();
			if(data["message"])
				$.notify(data["message"], data["status"]);
		}, "json");
	});
	$(".deleteround").click(function() {
		$.post("/deleteround", {
			'round': $(this).parent().data("roundid")
		}, function(data) {
			if (data['status'] === "success")
				updateTab();
			else {
				console.log(data);
			}
			if(data["message"])
				$.notify(data["message"], data["status"]);
		}, "json");
	});
	var updateSetting = function() {
		var round = $(this).parent().data("roundid");
		var settings = {};
		var colname = $(this).data("colname");
		var updatefield = $(this).data("updatefield");
		if ($(this).attr('type') === "checkbox")
			settings[colname] = $(this).prop('checked') ? ($(this).data("checkvalue") || 1) : 0;
		else
			settings[colname] = $(this).val();
		console.log(settings);
		$.post("/settings", {
			'round': round,
			'settings': JSON.stringify(settings)
		}, function(data) {
			if(data["message"])
				$.notify(data["message"], data["status"]);
			if (data['status'] !== "success") {
				console.log(data);
			}
			else if(updatefield) {
				var defval = $("#" + updatefield).data("default");
				if(settings[colname] == 0 && defval) {
					$("#" + updatefield).val(defval);
					$("#" + updatefield).attr("disabled", true);
				}
				else {
					$("#" + updatefield).val(settings[colname]);
					$("#" + updatefield).attr("disabled", false);
				}
			}
		}, "json");

	}
	fillSelect("/algorithms", "span.algorithmselect", "Name", "Id", function() {
		$(".roundsetting").change(updateSetting).keyup(updateSetting);
	});
	fillSelect("/orderings", "span.orderingselect", "Name", "Id", function() {
		$(".roundsetting").change(updateSetting).keyup(updateSetting);
	});
});
