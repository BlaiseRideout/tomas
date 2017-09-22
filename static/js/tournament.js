$(function() {
	var templates = {};
	var countries, countriesSelect;
	var algorithms, algorithmsSelect;
	var showInactive = false;
	var sortkeys = {}; /* Most recent sorting for each template */
	/* Structure sortkeys[templatename] =
	    {'table': list of rows (table) in data to be sorted,
	     'keys': list of keyspecs: ['field', +1 or -1, 'str' or 'num']
	    }  */
	var sortkeys = {
		'players.mst': {
			'table': 'players',
			'keys': [
				['inactive', 1, 'num'],
				['name', 1, 'str'],
				['country', 1, 'str']
			]
		},
		'leaderboard.mst': {
			'table': 'leaderboard',
			'keys': [
				['inactive', 1, 'num'],
				['games_played', -1, 'num'],
				['score', -1, 'num']
			]
		}
	};

	/* Build a comparison function that compares keys in order specified */
	function compareFunc(keyspecs) {
		if (keyspecs.length > 0) {
			var spec = keyspecs[0],
				inner = compareFunc(keyspecs.slice(1));
			return function(a, b) {
				if (spec[2] == 'str') {
					if (a[spec[0]] < b[spec[0]]) {
						return -1 * spec[1]
					}
					else if (a[spec[0]] > b[spec[0]]) {
						return spec[1]
					}
					else {
						return (inner && inner(a, b)) || 0
					}
				}
				else {
					if (a[spec[0]] - b[spec[0]] == 0) {
						return (inner && inner(a, b)) || 0
					}
					else {
						return (a[spec[0]] - b[spec[0]]) * spec[1]
					}
				}
			}
		}
	}

	function updateSortKeys(template, fieldname, fieldtype, table, callback) {
		var newkey = [fieldname, 1, fieldtype];
		if (!table && template.indexOf('.mst') > 0) {
			table = template.slice(0, -4);
		}
		if (sortkeys[template] && sortkeys[template]['keys'] &&
			sortkeys[template]['keys'][0][0] == fieldname) {
			sortkeys[template]['keys'][0][1] *= -1
		}
		else if (sortkeys[template]) {
			var keys = sortkeys[template]['keys'] || [];
			for (var j = 1; j < keys.length; j++) {
				if (keys[j][0] == fieldname) break;
			}
			if (j < keys.length) {
				newkey = keys[j];
				keys = keys.slice(0, j).concat(keys.slice(j + 1));
			}
			sortkeys[template]['keys'] = [newkey].concat(keys);
		}
		else {
			sortkeys[template] = {
				'table': table,
				'keys': [newkey]
			};
		};
		if (typeof callback === "function") callback();
	}

	function renderTemplate(template, endpoint, selector, callback, extra) {
		if (templates[template] === undefined)
			$.get("/static/mustache/" + template, function(data) {
				Mustache.parse(data);
				templates[template] = data;
				renderTemplate(template, endpoint, selector, callback, extra);
			});
		else
			$.getJSON(endpoint, function(data) {
				for (k in extra) {
					data[k] = extra[k]
				};
				if (sortkeys[template]) {
					var toSort = data[sortkeys[template]['table']];
					toSort.sort(compareFunc(sortkeys[template]['keys']));
					data[sortkeys[template]['table']] = toSort
				}
				$(selector).html(Mustache.render(
					templates[template], data));
				if (typeof callback === "function")
					callback(data);
			});
	}

	function updatePlayers() {
		renderTemplate("players.mst", "/players", "#players", function() {
			var updatePlayer = function() {
				var player = $(this).parents(".player").data("id");
				var colname = $(this).data("colname");
				var newVal = $(this).val();
				var info = {};
				var input = $(this);
				info[colname] = newVal;
				console.log('Player ' + player + ' update');
				console.log(info);
				$.post("/players", {
					'player': player,
					'info': JSON.stringify(info)
				}, function(data) {
					if (data['status'] == "success") {
						input.removeClass("bad");
						input.addClass("good");
					}
					else {
						console.log(data);
						input.removeClass("good");
						input.addClass("bad");
					}
				}, "json")
			};
			var addNewPlayer = function() {
				$.post("/players", {
						'player': '-1',
						'info': JSON.stringify({
							'name': '?'
						})
					},
					function(data) {
						if (data['status'] == "success") {
							$("#showinactive").prop("checked", true);
							showInactive = true;
							updatePlayers();
						}
						else {
							console.log(data);
						}
					}, "json")
			};
			var showHideInactive = function() {
				if ($('#showinactive').prop('checked')) {
					showInactive = true;
					$(".player[data-status='1']").show();
				}
				else {
					showInactive = false;
					$(".player[data-status='1']").hide()
				};
			};
			var togglePlayerActiveStatus = function() {
				var button = $(this),
					row = button.parents(".player")
				player = row.data("id"),
					colname = button.data("colname"),
					current = row.attr("data-status"),
					inactive = current == '1';
				info = {};
				info[colname] = inactive ? '0' : '1';
				$.post("/players", {
					'player': player,
					'info': JSON.stringify(info)
				}, function(data) {
					if (data['status'] == "success") {
						button.attr('value',
							inactive ? "Make inactive" : "Reactivate");
						row.attr("data-status", info[colname]);
						showHideInactive();
					}
					else {
						console.log(data);
					}
				}, "json");
			};
			countrySelect(function() {
				$(".countryselect").change(updatePlayer);
			});
			$(".playerfield").change(updatePlayer).keyup(updatePlayer);
			$(".addplayerbutton").click(addNewPlayer);
			$(".playerfield[data-colname='Inactive']").click(
				togglePlayerActiveStatus);
			$(".colheader").click(function() {
				updateSortKeys("players.mst",
					$(this).data("fieldname"),
					$(this).data("type"),
					"players",
					updatePlayers);
			});
			$("#showinactive").click(showHideInactive);
		}, {
			'showinactive': showInactive
		});
	}

	function countrySelect(callback) {
		if (countries === undefined)
			$.getJSON("/countries", function(data) {
				countries = data;
				countriesSelect = document.createElement("select");
				for (var i = 0; i < countries.length; ++i) {
					var country = document.createElement("option");
					$(country).text(data[i]['Code']);
					$(country).val(data[i]['Id']);
					$(country).data("flag", data[i]['Flag_Image'])
					countriesSelect.appendChild(country);
				}
				countrySelect(callback);
			});
		else {
			$("span.countryselect").each(function(i, elem) {
				var country = $(elem).data("countryid");
				select = countriesSelect.cloneNode(true);
				select.className = this.className;
				$(elem).replaceWith(select);
				$(select).val(country);
				$(select).data("colname", "Country");
				$(select).change(function() {
					$(this).parent().next(".flag").html(countries[this.selectedIndex]["Flag_Image"]);
				});
			});
			if (typeof callback === 'function')
				callback();
		}
	}

	function algorithmSelect(callback) {
		if (algorithms === undefined)
			$.getJSON("/algorithms", function(data) {
				algorithms = data;
				algorithmsSelect = document.createElement("select");
				for (var i = 0; i < algorithms.length; ++i) {
					var algorithm = document.createElement("option");
					$(algorithm).text(algorithms[i]['Name']);
					$(algorithm).val(algorithms[i]['Id']);
					algorithmsSelect.appendChild(algorithm);
				}
				algorithmSelect(callback);
			});
		else {
			$("span.algorithmselect").each(function(i, elem) {
				var algorithm = $(elem).data("algorithm");
				var select = algorithmsSelect.cloneNode(true);
				select.className = this.className;
				$(elem).replaceWith(select);
				$(select).val(algorithm);
				$(select).data("colname", "Algorithm");
			});
			if (typeof callback === 'function')
				callback();
		}
	}

	function updateStandings() {
		renderTemplate("leaderboard.mst", "/leaderboard", "#standings");
	}

	function updateSettings() {
		renderTemplate("settings.mst", "/settings", "#settings", function() {
			$("#addround").click(function() {
				$.post("/addround", function(data) {
					if (data['status'] === "success")
						updateSettings();
				}, "json");
			});
			$(".deleteround").click(function() {
				$.post("/deleteround", {
					'round': $(this).parent().data("roundid")
				}, function(data) {
					if (data['status'] === "success")
						updateSettings();
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
			algorithmSelect(function() {
				$(".roundsetting").change(updateSetting).keyup(updateSetting);
			});
		});
	}

	function updateSeating() {
		renderTemplate("tables.mst", "/seating", "#seating", function() {
			var currentTab;
			if ($("#seating").hasClass("ui-tabs")) {
				currentTab = $("#seating").tabs().tabs("option", "active");
				console.log(currentTab);
				$("#seating").tabs("destroy");
			}
			$("#seating").tabs();
			if (currentTab !== undefined)
				$("#seating").tabs("option", "active", currentTab);
			$(".genround").click(function() {
				var round = $(this).parents(".round").data("round");
				$.post("/seating", {
					"round": round
				}, function(data) {
					updateSeating();
				}, "json");
			});
		});
	}

	function update() {
		updateSettings();
		updatePlayers();
		updateStandings();
		updateSeating();
	}
	update();
	$("#tournament").tabs();
});
