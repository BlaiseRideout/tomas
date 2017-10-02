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
					}
				}, "json");
		}
	};

	function updatePenaltyField(ev) {
		var penalty = $(this).parents(".penaltyrecord"),
			penaltyid = penalty.data("penaltyid"),
			colname = $(this).data("colname");
		if (ev && 'type' in ev && ev.type == 'keyup' &&
			$(this).attr('type') == 'number' &&
			!valueChangingKeys[ev.key]) {
			console.log('Ignoring ' + ev.type + ' event: ' + ev.key)
			return;
		};
		console.log('Penalty ' + penaltyid + ' update of ' + colname + ' to ' + $(this).val());
		updatePenaltyRecords();
	};

	function updatePenaltyRecords(deleteID) {
		/* deleteID can be penalty record ID to delete it,
		   or '-1' to add a new record */

		var player = $(this).parents(".player"),
			penaltyeditor = player.next(),
			penalties = [],
			totalpenalty = 0,
			scoreID = penaltyeditor.data('scoreid');
		penaltyeditor.find(".penaltyrecord").each(function() {
			if ($(this).data('penaltyid') != deleteID) {
				var penalty = parseInt($(this).find("input.penaltyamout").val());
				penalties = penalties.concat({
					'foo': scoreID,
					'scoreID': scoreID,
					'penalty': penalty,
					'description': $(this).find("input.penaltydescription").val(),
					'referee': $(this).find("input.penaltyreferee").val(),
				});
				totalpenalty += penalty;
			}
		});
		if (deleteID == '-1') {
			penalties = penalties.concat({
				'foo': scoreID,
				'scoreID': scoreID,
				'penalty': -1,
				'description': ' ',
				'referee': ''
			});
			totalpenalty -= 1;
		};
		$.post('/penalties', {
				'foo': scoreID,
				'scoreID': scoreID,
				'penalties': JSON.stringify(penalties)
			},
			function(data) {
				if (data["message"]) {
					$.notify(data["message"], data["status"]);
					console.log(message);
				}
				if (data['status'] === 'success') {
					populatePenaltyEditor.call(penaltyeditor.get());
					penaltyeditor.find(".penaltyinput").removeClass('bad');
					penaltyeditor.find(".penaltyinput").addClass('good');
					player.find(".playerpenalty").text(totalpenalty);
				}
				else {
					penaltyeditor.find(".penaltyinput").removeClass('good');
					penaltyeditor.find(".penaltyinput").addClass('bad');
				}
			},
			"json");
	};

	function populatePenaltyEditor() {
		var penaltyeditor = $(this),
			scoreid = penaltyeditor.data('scoreid');
		$.get('/penalties/' + scoreid, function(data) {
			console.log('After fetching /penalties/' + scoreid +
				' the returned data is:');
			console.log(data);
			if (penaltyeditor.find(".penaltyrecord").length > 0) {
				penaltyeditor.find(".penaltyrecord").replaceWith(data);
			}
			else {
				penaltyeditor.find(".penaltyEditorBody").prepend(data);
			}
			penaltyeditor.find(".deletepenalty").click(function() {
				updatePenaltyRecords($(this).data('penaltyid'));
			});
			penaltyeditor.find(".addPenalty").click(function() {
				updatePenaltyRecords('-1');
			});
			penaltyeditor.find(".penaltyfield").change(updatePenaltyField)
				.keyup(updatePenaltyField);
		});
	}

	function togglePenaltyEditor() {
		var images = ['/static/images/closed-section-pointer.png',
			'/static/images/open-section-pointer.png'
		]
		var player = $(this).parents(".player"),
			penaltyeditor = player.next(),
			scoreid = penaltyeditor.data('scoreid'),
			img = player.find(".sectionControl"),
			image = img.attr('src');
		if (image == images[0]) {
			populatePenaltyEditor.call(penaltyeditor.get());
			img.attr('src', images[1]);
			penaltyeditor.show();
		}
		else {
			img.attr('src', images[0]);
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
