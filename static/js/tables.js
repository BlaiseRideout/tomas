$(function() {
	if (window.currentTab !== undefined)
		$("#seating").tabs({
			active: currentTab
		});
	else
		$("#seating").tabs();

	function round(num, digits) {
		var d10 = Math.pow(10, digits),
			shift = Math.round(num * d10),
			sig = '' + shift,
			n = sig.length;
		return (shift % d10 == 0) ? '' + num :
			sig.substring(0, n - digits) + '.' + sig.substring(n - digits);
	};

	function scoreChange() {
		var score = $(this).val();
		var player = $(this).parents(".player");
		var table = player.parents(".table");
		var tabletotal = table.prev("thead").find(".tabletotal");
		var scores = table.find(".playerscore");
		var total = 0,
			umas = [15, 5, -5, -15];
		scores.each(function(i, elem) {
			var val = parseInt($(elem).val());
			total += val;
		});
		tabletotal.text("TOTAL " + total);
		newstate = (total == 100000 || total == 0) ? "good" : "bad";
		delstate = (total == 100000 || total == 0) ? "bad" : "good";
		table.find(".playerscore, .playerchombos").removeClass(delstate);
		table.find(".playerscore, .playerchombos").addClass(newstate);
		tabletotal.removeClass(delstate);
		tabletotal.addClass(newstate);
		if (total == 100000) {
			var tablescore = [],
				gameid = table.data("roundid") * 1000 + table.data("tableid");
			table.find(".player").each(function() {
				tablescore = tablescore.concat({
					'gameid': gameid,
					'playerid': $(this).data("playerid"),
					'rawscore': parseInt($(this).find(".playerscore").val()),
					'chombos': parseInt($(this).find(".playerchombos").val()),
					'rank': $(this).find(".rank"),
					'score': $(this).find(".score")
				});
			});
			tablescore.sort(function(ra, rb) {
				/* Sort by raw score descending, and chombos ascending */
				return rb['rawscore'] == ra['rawscore'] ?
					ra['chombos'] - rb['chombos'] :
					rb['rawscore'] - ra['rawscore'];
			});
			for (var j = 0; j < tablescore.length; j++) {
				tablescore[j]['rank'].text(j + 1);
				tablescore[j]['rank'] = j + 1;
				var score = tablescore[j]['rawscore'] / 1000.0 - 25 +
					tablescore[j]['chombos'] * -8 + umas[j];
				tablescore[j]['score'].text(round(score, 1));
				tablescore[j]['score'] = score;
			}
		}
	}
	$(".playerscore, .playerchombos").change(scoreChange).keyup(scoreChange);
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
