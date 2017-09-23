$(function() {
	if(window.currentTab !== undefined)
		$("#seating").tabs({
			active:currentTab
		});
	else
		$("#seating").tabs();
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
