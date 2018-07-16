$(function() {
	$("#addround").click(function() {
		$.post("addstage", function(data) {
			if (data['status'] === "success")
				updateTab();
			if (data["message"])
				$.notify(data["message"], data["status"]);
		}, "json");
	});
	$(".deletestage").click(function() {
		$.post("deletestage", {
			'stage': $(this).parent().data("stageid")
		}, function(data) {
			if (data['status'] === "success")
				updateTab();
			else {
				console.log(data);
			}
			if (data["message"])
				$.notify(data["message"], data["status"]);
		}, "json");
	});
	var updateTourneySetting = function() {
		var stage = $(this).parent().data("stageid");
		var settings = {};
		var colname = $(this).data("colname");
		var updatefield = $(this).data("updatefield");
		if ($(this).attr('type') === "checkbox")
			settings[colname] = $(this).prop('checked') ? ($(this).data("checkvalue") || 1) : 0;
		else
			settings[colname] = $(this).val();
		console.log(settings);
		$.post("tourney", {
			'stage': stage,
			'settings': JSON.stringify(settings)
		}, function(data) {
			if (data["message"])
				$.notify(data["message"], data["status"]);
			if (data['status'] !== "success") {
				console.log(data);
			}
			else if (updatefield) {
				var defval = $("#" + updatefield).data("default");
				if (settings[colname] == 0 && defval) {
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

	$(".tourneyinput").change(updateTourneySetting).keyup(updateTourneySetting);
});
