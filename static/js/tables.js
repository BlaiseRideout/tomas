$(function() {
	if (window.currentTab !== undefined)
		$("#seating").tabs({
			active: currentTab
		});
	else
		$("#seating").tabs();
	$("#seating").find('li').click(function() {
		window.currentTab = $("#seating").tabs().tabs("option", "active");
	});

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
			partial = false,
			umas = [15, 5, -5, -15];
		scores.each(function(i, elem) {
			var val = parseInt($(elem).val());
			total += val;
			partial = partial || (val % 100 != 0);
		});
		tabletotal.text("TOTAL " + total);
		partial = partial || !(total == 100000 || total == 0);
		newstate = partial ? "bad" : "good";
		delstate = partial ? "good" : "bad";
		table.find(".playerscore, .playerchombos").removeClass(delstate);
		table.find(".playerscore, .playerchombos").addClass(newstate);
		tabletotal.removeClass(delstate);
		tabletotal.addClass(newstate);
		if (total == 100000 && !partial) {
			var tablescore = [];
			table.find(".player").each(function() {
				tablescore = tablescore.concat({
					'gameid': table.data("tableid"),
					'roundid': table.data("roundid"),
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
			$.post("/scores", {
					'tablescores': JSON.stringify(tablescore)
				},
				function(data) {
					if (data['status'] != 'success') {
						var msg = '';
						for (k in data) {
							if (k != 'status') {
								msg += k + ': ' + data[k] + '\n';
							}
						};
						alert('Error saving game\n' + msg);
					}
					else {
						$(".genround").remove();
					}
				}, "json");
		}
	}
	$(".playerscore, .playerchombos").change(scoreChange).keyup(scoreChange);
	$(".genscores").click(function() {
		$(this).parent(".round").find(".table").each(function(i, table) {
			var totalScore = 100000;
			$(table).find(".player").each(function(j, player) {
				if(j < 3)
					var playerScore = Math.floor(Math.random() * totalScore / 100) * 100;
				else
					var playerScore = totalScore;
				totalScore -= playerScore;
				$(player).find(".playerscore").val(playerScore).change();
			});
		});
	});
	$(".genround").click(function() {
		var round = $(this).parents(".round").data("round");
		$.post("/seating", {
			"round": round
		}, function(data) {
			if(data["message"])
				$.notify(data["message"], data["status"]);
			window.updateTab();
		}, "json");
	});
});
