$(function() {
	var templates = {};
	var templatedata = {};
	var selects = {},
		selectData = {};
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
		},
		'users.mst': {
			'table': 'users',
			'keys': [
				['email', 1, 'str'],
				['admin', 1, 'num'],
			]
		},
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
				selectData[endpoint] = data;
				for (var i = 0; i < data.length; ++i) {
					var option = document.createElement("option");
					$(option).text(data[i][displayrow]);
					$(option).val(data[i][valuerow]);
					selects[endpoint].appendChild(option);
				}
				fillSelect(endpoint, selector, displayrow, valuerow, callback);
			});
		else {
			$(selector).each(function(i, elem) {
				var select = selects[endpoint].cloneNode(true);
				select.className = this.className;
				$(select).val($(elem).data("value"));
				$(select).data("colname", $(elem).data("colname"));
				$(select).data("selectData", selectData[endpoint]);
				$(elem).replaceWith(select);
			});
			if (typeof callback === 'function')
				callback();
		}
	}

	var updatePlayer = function(callback) {
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
					if (typeof callback === 'function')
						callback.call(this);
				}
				else {
					console.log(data);
					input.removeClass("good");
					input.addClass("bad");
				}
			}.bind(this), "json")
	};
	var addNewPlayer = function() {
		$.post("/players", {
				'player': '-1',
				'info': JSON.stringify({
					'name': '?'
				})
			},
			function(data) {
				if (data['status'] === "success") {
					$("#showinactive").prop("checked", true);
					showInactive = true;
					updatePlayers();
				}
				else {
					console.log(data);
				}
			}, "json");
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
					updatePlayer.call(this, function() {
						$(this).parent().next(".flag").html($(this).data("selectData")[this.selectedIndex]["Flag_Image"]);
					});
				});
			});
			$(".playerfield").change(updatePlayer).keyup(updatePlayer);
			$(".addplayerbutton").click(addNewPlayer);
			$(".deleteplayerbutton").click(function() {
				var player = $(this).parents(".player").data("id");
				$.post("/deleteplayer", {
					'player': player
				}, function(data) {
					if (data['status'] === "success")
						updatePlayers();
					else
						console.log(data);
				}, "json");
			});
			$(".playerfield[data-colname='Inactive']").click(
				togglePlayerActiveStatus);
			$("#players .colheader").click(function(ev) {
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
		beforeLoad: function(event, ui) {
			ui.jqXHR.fail(function() {
				ui.panel.html(
					"Couldn't load this tab. We'll try to fix this as soon as possible.");
			});
		}
	});

	var updateUser = function(usercmd, callback) {
		var user = $(this).parents(".user").data("id");
		var colname = $(this).data("colname");
		var newVal = colname && $(this).val();
		if (usercmd == "new") {
			user = "-1";
			colname = "email";
			newVal = "new@mail.com";
			console.log('Create new user');
		}
		else if (usercmd == "del") {
			console.log('Delete user ' + user);
			colname = "del";
			newVal = user;
		}
		else if (usercmd == "reset") {
			console.log('Reset user ' + user + ' password');
			colname = "reset";
			newVal = user;
		}
		else {
			console.log('User ' + user + ' update');
		}
		var info = {};
		var input = $(this);
		info[colname] = newVal;
		console.log(info);
		$.post("/users", {
				'user': user,
				'info': JSON.stringify(info)
			},
			function(data) {
				if (data['status'] == "success") {
					input.removeClass("bad");
					input.addClass("good");
					if (typeof callback === 'function')
						callback.call(this, data);
				}
				else {
					console.log(data);
					input.removeClass("good");
					input.addClass("bad");
				}
			}, "json")
	};

	var toggleUserAdminStatus = function() {
		var button = $(this),
			row = button.parents(".user"),
			user = row.data("id"),
			admin = row.attr("data-status") == '1',
			info = {};
		info['Admin'] = admin ? '0' : '1';
		$.post("/users", {
			'user': user,
			'info': JSON.stringify(info)
		}, function(data) {
			if (data['status'] == "success") {
				button.attr('value',
					admin ? "Make admin" : "Drop admin");
				row.attr("data-status", info['Admin']);
				row.find(".admin").text(admin ? 'No' : 'Yes');
				console.log('Made user ' + user + ' admin = ' +
					info['Admin']);
			}
			else {
				console.log(data);
			}
		}, "json");
	};

	function updateUsers(reload) {
		if (reload === undefined) {
			reload = true
		};
		renderTemplate("users.mst", "/users", "#users", function() {
				$(".userfield").change(updateUser).keyup(updateUser);
				$(".adduserbutton").click(function() {
					updateUser.call(this, "new", updateUsers);
				});
				$(".resetpwdbutton").click(function() {
					updateUser.call(this, "reset",
						function(data) {
							if (data['status'] == 'success') {
								open(data['redirect'], '_self')
							}
						});
				});
				$(".deluserbutton").click(function() {
					updateUser.call(this, "del", updateUsers);
				});
				$(".toggleadmin").click(toggleUserAdminStatus);
				$("#users .colheader").click(function(ev) {
					if ($(ev.target).attr('class') == 'colheader') {
						updateSortKeys("users.mst",
							$(this).data("fieldname"),
							$(this).data("type"),
							"users", updateUsers);
					}
				});
			},
			null, reload);
	}

	$("#tournament").tabs().find('li').click(function(ev) {
		var id = $(ev.target).parents('li').data('id');
		if (id == 'players') {
			return updatePlayers()
		}
		else if (id == 'users') {
			return updateUsers()
		}
		else if (id) {
			console.log('Unexpected click event for data-id = ' + id)
		}
	});
	updatePlayers();
	window.updateTab = function(callback) {
		var current_index = $("#tournament").tabs("option", "active");
		$("#tournament").tabs('load', current_index);
		if (typeof callback === 'function')
			callback();
	}
});
