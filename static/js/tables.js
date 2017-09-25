$(function() {
	if(window.currentTab !== undefined)
		$("#seating").tabs({
			active:currentTab
		});
	else
		$("#seating").tabs();
	function scoreChange() {
		var score = $(this).val();
		var player = $(this).parents(".player");
		var table = player.parents(".table");
		var scores = table.find(".playerscore");
		var total = 0;
		scores.each(function(i, elem) {
			total += parseInt($(elem).val());
		});
		table.prev("thead").find(".tabletotal").text("TOTAL " + total);
	}
	$(".playerscore").change(scoreChange).keyup(scoreChange);
	$(".genround").click(function() {
		var round = $(this).parents(".round").data("round");
		$.post("/seating", {
			"round": round
		}, function(data) {
			window.currentTab = $("#seating").tabs().tabs("option", "active");
			window.updateTab();
		}, "json");
	});
});
