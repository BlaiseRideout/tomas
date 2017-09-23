$(function() {
	var templates = {};
	var templatedata = {};
	var selects = {};
	var showInactive = true;
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
				inner = compareFunc(keyspecs.slice(1)),
				fld = spec[0];
			return function(a, b) {
				if (spec[2] == 'str') {
					if (a[fld] < b[fld]) {
						return -1 * spec[1]
					}
					else if (a[fld] > b[fld]) {
						return spec[1]
					}
					else {
						return (inner && inner(a, b)) || 0
					}
				}
				else {
					if (a[fld] - b[fld] == 0) {
						return (inner && inner(a, b)) || 0
					}
					else {
						return (a[fld] - b[fld]) * spec[1]
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

	function renderTemplate(template, endpoint, selector, callback, extra, reload) {
		if (templates[template] === undefined)
			$.get("/static/mustache/" + template, function(data) {
				Mustache.parse(data);
				templates[template] = data;
				renderTemplate(template, endpoint, selector, callback, extra, reload);
			})
		else if (templatedata[template] === undefined || reload)
			$.getJSON(endpoint, function(data) {
				templatedata[template] = data;
				renderTemplate(template, endpoint, selector, callback, extra, false);
			});
		else {
			for (k in extra) {
				templatedata[template][k] = extra[k]
			}
			if (sortkeys[template]) {
				var toSort = templatedata[template][sortkeys[template]['table']];
				toSort.sort(compareFunc(sortkeys[template]['keys']));
				templatedata[template][sortkeys[template]['table']] = toSort
			}
			$(selector).html(Mustache.render(
				templates[template], templatedata[template]));
			if (typeof callback === "function")
				callback(templatedata[template]);
		};
	}

	window.fillSelect = function(endpoint, selector, displayrow, valuerow, callback) {
		if (selects[endpoint] === undefined)
			$.getJSON(endpoint, function(data) {
				selects[endpoint] = document.createElement("select");
				for (var i = 0; i < data.length; ++i) {
					var option = document.createElement("option");
					$(option).text(data[i][displayrow]);
					$(option).val(data[i][valuerow]);
					$(option).data("selectData", data[i]);
					selects[endpoint].appendChild(option);
				}
				fillSelect(endpoint, selector, displayrow, valuerow, callback);
			});
		else {
			$(selector).each(function(i, elem) {
				var select = selects[endpoint].cloneNode(true);
				select.className = this.className;
				/* console.log($(elem).data("value")); */
				$(select).val($(elem).data("value"));
				$(select).data("colname", $(elem).data("colname"));
				$(elem).replaceWith(select);
			});
			if (typeof callback === 'function')
				callback();
		}
	}

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
			},
			function(data) {
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
		showInactive = $('#showinactive').prop('checked');
		if (showInactive) {
			$(".player[data-status='1']").show();
		}
		else {
			$(".player[data-status='1']").hide()
		};
	};
	var togglePlayerActiveStatus = function() {
		var button = $(this),
			row = button.parents(".player"),
			player = row.data("id"),
			colname = button.data("colname"),
			inactive = row.attr("data-status") == '1',
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

	function updatePlayers(reload) {
		if (reload === undefined) {
			reload = true
		};
		renderTemplate("players.mst", "/players", "#players", function() {
			fillSelect("/countries", "span.countryselect", "Code", "Id", function() {
				$(".countryselect").change(function() {
					updatePlayer();
					$(this).parent().next(".flag").html($(this).data("selectData")["Flag_Image"]);
				});
			});
			$(".playerfield").change(updatePlayer).keyup(updatePlayer);
			$(".addplayerbutton").click(addNewPlayer);
			$(".playerfield[data-colname='Inactive']").click(
				togglePlayerActiveStatus);
			$(".colheader").click(function(ev) {
				if ($(ev.target).attr('class') == 'colheader') {
					updateSortKeys("players.mst",
						$(this).data("fieldname"),
						$(this).data("type"),
						"players",
						function() {
							updatePlayers(false)
						});
				}
			});
			$("#showinactive").click(showHideInactive);
		}, {
			'showinactive': showInactive
		}, reload);
	}

	$("#tournament").tabs({
		beforeLoad: function( event, ui ) {
			ui.jqXHR.fail(function() {
				ui.panel.html(
					"Couldn't load this tab. We'll try to fix this as soon as possible.");
			});
		}
	}).find('li').click(function(ev) {
		var id = $(ev.target).parents('li').data('id');
		if (id == 'players') {
			return updatePlayers()
		}
		else {
			console.log('Unexpected click event for data-id = ' + id)
		}
	});
	updatePlayers();
	window.updateTab = function(callback) {
		var current_index = $("#tournament").tabs("option","active");
		$("#tournament").tabs('load', current_index);
		if(typeof callback === 'function')
			callback();
	}
});
