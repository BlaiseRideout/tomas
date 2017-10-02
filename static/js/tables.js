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
	var totalPoints = 120000;

	function histogram(default_increment) {
		var hist = {},
			incr = default_increment || 1,
			prefix = 'h';

		function increment(val, inc) {
			var index = prefix + val;
			if (index in hist) {
				hist[index] += (inc || incr)
			}
			else {
				hist[index] = (inc || incr)
			}
		}

		function get(val) {
			var index = prefix + val;
			return hist[index]
		}

		function keys() {
			var keys = Object.keys(hist);
			for (var j = 0; j < keys.length; j++) {
				keys[j] = keys[j].substring(prefix.length)
			};
			return keys;
		}
		return {
			'increment': increment,
			'get': get,
			'keys': keys
		}
	}

	function round(num, digits) {
		var d10 = Math.pow(10, digits),
			shift = Math.round(num * d10),
			sig = '' + shift,
			n = sig.length;
		return (shift % d10 == 0) ? '' + num :
			sig.substring(0, n - digits) + '.' + sig.substring(n - digits);
	};

	var valueChangingKeys = {
		'Backspace': 1,
		'Delete': 1,
		'+': 1,
		'-': 1,
		'0': 1,
		'1': 1,
		'2': 1,
		'3': 1,
		'4': 1,
		'5': 1,
		'6': 1,
		'7': 1,
		'8': 1,
		'9': 1,
		'.': 1,
	};

	function scoreChange(ev) {
		if (ev && 'type' in ev && ev.type == 'keyup' &&
			!valueChangingKeys[ev.key]) {
			console.log('Ignoring ' + ev.type + ' event: ' + ev.key)
			return;
		};
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
		partial = partial || !(total == totalPoints || total == 0);
		newstate = partial ? "bad" : "good";
		delstate = partial ? "good" : "bad";
		table.find(".playerscore, .playerpenalty").removeClass(delstate);
		table.find(".playerscore, .playerpenalty").addClass(newstate);
		tabletotal.removeClass(delstate);
		tabletotal.addClass(newstate);
		if (total == totalPoints && !partial) {
			var tablescore = [];
			table.find(".player").each(function() {
				tablescore = tablescore.concat({
					'gameid': table.data("tableid"),
					'roundid': table.data("roundid"),
					'playerid': $(this).data("playerid"),
					'rawscore': parseInt($(this).find(".playerscore").val()),
					'penalty': parseInt($(this).find(".playerpenalty").text()),
					'rank': $(this).find(".rank"),
					'score': $(this).find(".score")
				});
			});
			tablescore.sort(function(ra, rb) {
				/* Sort by raw score; ignore penalties for rank */
				return rb['rawscore'] - ra['rawscore'];
			});
			var lastscore = NaN,
				lastrank = 0,
				rankhist = histogram();
			for (var j = 0; j < tablescore.length; j++) {
				var rank = tablescore[j]['rawscore'] != lastscore ?
					j + 1 : lastrank;
				rankhist.increment(rank);
				lastscore = tablescore[j]['rawscore'];
				lastrank = rank;
				tablescore[j]['rank'].text(rank);
				tablescore[j]['rank'] = rank;
			};
			for (var j = 0; j < tablescore.length; j++) {
				var rank = tablescore[j]['rank'],
					raw = tablescore[j]['rawscore'];
				for (var umasum = 0, i = 0; i < rankhist.get(rank); i++) {
					umasum += umas[rank - 1 + i];
				}
				var score = (raw - totalPoints / 4) / 1000.0 +
					umasum / rankhist.get(rank);
				tablescore[j]['score'].text(round(score, 1));
				tablescore[j]['score'] = score;
			}
			$.post("/scores", {
					'tablescores': JSON.stringify(tablescore)
				},
				function(data) {
					if (data["message"])
						$.notify(data["message"], data["status"]);
					if (data['status'] === 'success') {
						$(table).parents(".round").find(".genround").remove();
						$(table).parents(".round").find(".swapper").remove();
						/* TODO: Populate score IDs and
						   enable penalty editor for new
						   score entries */
					}
				}, "json");
		}
	};

	function updatePenaltyField(ev) {
		var penalty = $(this).parents(".penaltyrecord"),
			penaltyid = penalty.data("penaltyid"),
			scoreID = penalty.parents(".penaltyEditor").data("scoreid"),
			colname = $(this).data("colname");
		if (ev && 'type' in ev && ev.type == 'keyup' &&
			$(this).attr('type') == 'number' &&
			!valueChangingKeys[ev.key]) {
			console.log('Ignoring ' + ev.type + ' event: ' + ev.key)
			return;
		};
		updatePenaltyRecords(null, scoreID, false);
	};

	function updatePenaltyRecords(deleteID, scoreID, reload) {
		/* deleteID can be a penalty record ID to delete it,
		   or '-1' to add a new record */

		if (reload === undefined) {
			reload = true
		};
		var attribute = "[data-scoreid='" + scoreID + "']",
			player = $(".player" + attribute),
			penaltyeditor = $(".penaltyEditor" + attribute),
			penalties = [],
			totalpenalty = 0;
		penaltyeditor.find(".penaltyrecord").each(function() {
			if ($(this).data('penaltyid') != deleteID) {
				var rec = {
					'scoreID': scoreID
				};
				$(this).find(".penaltyfield").each(function() {
					rec[$(this).data('colname')] = $(this).val();
					if ($(this).attr('type') == 'number') {
						rec[$(this).data('colname')] = parseInt($(this).val());
					}
				});
				penalties = penalties.concat(rec);
				totalpenalty += rec['penalty'];
			}
		});
		if (deleteID == '-1') {
			penalties = penalties.concat({
				'scoreID': scoreID,
				'penalty': -1,
				'description': '',
				'referee': ''
			});
			totalpenalty -= 1;
			reload = true;
		};
		$.post('/penalties', {
				'scoreID': scoreID,
				'penalties': JSON.stringify(penalties)
			},
			function(data) {
				if (data["message"]) {
					$.notify(data["message"], data["status"]);
					console.log(data["message"]);
				}
				if (data['status'] === 'success') {
					if (reload) {
						populatePenaltyEditor(penaltyeditor, scoreID);
						penaltyeditor = $(".penaltyEditor" + attribute)
					}
					penaltyeditor.find(".penaltyfield").removeClass('bad');
					penaltyeditor.find(".penaltyfield").addClass('good');
					player.find(".playerpenalty").text(totalpenalty);
				}
				else {
					penaltyeditor.find(".penaltyfield").removeClass('good');
					penaltyeditor.find(".penaltyfield").addClass('bad');
				}
			},
			"json");
	};

	function populatePenaltyEditor(penaltyeditor, scoreID) {
		$.get('/penalties/' + scoreID, function(data) {
			/* Create a row below the player row if one is not supplied */
			if (penaltyeditor.length == 0) {
				var attribute = "[data-scoreid='" + scoreID + "']";
				penaltyeditor = $(".player" + attribute).after(
					"<div id='NPE451' data-scoreid='" + scoreID + "'></div>");
				penaltyeditor = $("#NPE451" + attribute);
			}
			penaltyeditor.replaceWith(data);

			$(".deletepenalty").click(function() {
				updatePenaltyRecords($(this).data('penaltyid'),
					scoreID);
			});
			$(".addPenalty").click(function() {
				updatePenaltyRecords('-1', scoreID);
			});
			$(".penaltyfield").change(updatePenaltyField)
				.keyup(updatePenaltyField);
		});
	}

	var glyphs = ['▶', '▼', '&#9654;', '&#9660;'];

	function togglePenaltyEditor() {
		var player = $(this).parents(".player"),
			scoreid = $(this).data('scoreid'),
			penaltyeditor = $(".penaltyEditor[data-scoreid='" +
				scoreid + "']"),
			control = player.find(".sectionControl"),
			glyph = control.html().trim(),
			index = $.inArray(glyph, glyphs);
		if (index < 0) {
			$.notify("Unexpected character in section control",
				"Internal Error");
		}
		else if (index % 2 == 0) {
			populatePenaltyEditor(penaltyeditor, scoreid);
			control.html(glyphs[1]);
			penaltyeditor.show();
		}
		else {
			control.html(glyphs[0]);
			penaltyeditor.hide();
		}
	};

	$(".playerscore").change(scoreChange).keyup(scoreChange);
	$(".sectionControl").click(togglePenaltyEditor);
	$("input.swapper").change(function() {
		var round = $(this).parents(".round");
		var roundid = $(round).data("round");
		var left = round.find("input.swapper[name=round" + roundid + "-left]:checked").val();
		var right = round.find("input.swapper[name=round" + roundid + "-right]:checked").val();
		if (left && right)
			$.post("/swapseating", {
				"round": roundid,
				"left": left,
				"right": right
			}, function(data) {
				if (data["message"])
					$.notify(data["message"], data["status"]);
				if (data["status"] === "success")
					window.updateTab();
			}, "json");
	});
	$(".genscores").click(function() {
		$(this).parent(".round").find(".table").each(function(i, table) {
			var totalScore = totalPoints;
			$(table).find(".player").each(function(j, player) {
				if (j < 3)
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
			if (data["message"])
				$.notify(data["message"], data["status"]);
			window.updateTab();
		}, "json");
	});
});
