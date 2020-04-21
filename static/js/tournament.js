$(function() {
	function updatePlayers(reload) {
		if (reload === undefined) {
			reload = true
		};
		renderTemplate("players.mst", "players", "#players", function() {
			fillSelect("/countries", "span.countryselect", "Code", "Id", function() {
				$(".countryselect").change(function() {
					updatePlayer.call(this, function() {
						$(this).parent().next(".flag").html($(this).data("selectData")[this.selectedIndex]["Flag_Image"]);
					});
				});
			});
			$("#uploadplayers").click(function() {
				var form = document.createElement("form");
				var picker = document.createElement("input");
				form.appendChild(picker);
				picker.type = "file";
				picker.name = "file";
				$(picker).click();
				$(picker).change(function() {
					var data = new FormData(form);
					$.ajax({
						'url': 'uploadplayers',
						'data': data,
						'type': 'POST',
						'contentType': false,
						'processData': false,
						success: function(data) {
							if (data["status"] === "success")
								updatePlayers();
							else
								console.log(data);
							if (data["message"])
								$.notify(data["message"], data["status"]);
						}
					})
				});
			});
			$(".playerfield").change(updatePlayer).keyup(updatePlayer);
			populateAssociationComplete(true);
			$(".addplayerbutton").click(addNewPlayer);
			$("#clearplayers").click(function() {
				$.post("deleteplayer", {
					'player': "all"
				}, function(data) {
					if (data['status'] === "success")
						updatePlayers();
					else
						console.log(data);
					if (data["message"])
						$.notify(data["message"], data["status"]);
				}, "json");
			});
			$(".deleteplayerbutton").click(function() {
				var player = $(this).parents(".player").data("id");
				$.post("deleteplayer", {
					'player': player
				}, function(data) {
					if (data['status'] === "success")
						updatePlayers();
					else
						console.log(data);
					if (data["message"])
						$.notify(data["message"], data["status"]);
				}, "json");
			});
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
			$(".playertype").each(function() {
				var ptype = $(this).parents(".player").data("status").toLowerCase();
				$(this).find("option").each(function() {
					$(this).prop(
						"selected",
						$(this).text().toLowerCase() == ptype ||
						($(this).text().toLowerCase() == 'regular' &&
							ptype == ''))
				});
			});
			$("#showinactive").click(showHideInactive);
		}, {
			'showinactive': showInactive
		}, reload);
	}

	var refresh = $('#tournament').tabs().find('li').first().data('refresh');

	if (typeof tab == 'string') {
		$('#tournament ul li a').each(function(i, elem) {
			if (typeof tab == 'string' && tab.match(/^\d+$/) ?
				tab - 0 == i :
				$(elem).attr('href') == tab) {
				tab = i;
				refresh = $(elem).parent('li').data('refresh');
			}
		})
	};
	$("#tournament").tabs({
		beforeLoad: function(event, ui) {
			ui.jqXHR.fail(function() {
				ui.panel.html(
					"Couldn't load this tab. We'll try to fix this as soon as possible.");
			});
		},
		active: (tab || 0) - 0
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
		$.post("users", {
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
				if (data["message"])
					$.notify(data["message"], data["status"]);
			}, "json")
	};

	var toggleUserAdminStatus = function() {
		var button = $(this),
			row = button.parents(".user"),
			user = row.data("id"),
			admin = row.attr("data-status") == '1',
			info = {};
		info['Admin'] = admin ? '0' : '1';
		$.post("users", {
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
			if (data["message"])
				$.notify(data["message"], data["status"]);
		}, "json");
	};

	$("#tournament").tabs().find('li').click(function(ev) {
		var tabs = $(ev.target).parents('li'),
			refresh = tabs.data('refresh');
		if (refresh) {
			$('#refreshcontrol').show();
			updateTournamentTab($("#tournament").tabs("option", "active"),
				refresh + 0);
		}
		else {
			$('#refreshcontrol').hide();
		};
	});

	function updateTournamentTab(tabindex, refresh_interval) {
		var refreshTimer,
			updater = function() {
				indexnow = $("#tournament").tabs("option", "active");
				if (indexnow == tabindex && $('#refreshcheckbox').prop('checked')) {
					/* console.log('Refresh tab index ' + tabindex); */
					$("#tournament").tabs('load', tabindex);
				}
				else {
					/* console.log('Clearing refresh for tab ' + tabindex); */
					clearInterval(refreshTimer);
				}
			};

		if ($('#refreshcheckbox').prop('checked')) {
			refreshTimer = setInterval(updater, refresh_interval)
		};
	};

	$('#refreshcheckbox').change(function(event) {
		var active = $("#tournament").tabs("option", "active");
		refresh = $("#tournament").tabs().find('li:eq(' + active + ')').data('refresh');
		updateTournamentTab(active, refresh);
	});

	window.updateTab = function(callback) {
		var current_index = $("#tournament").tabs("option", "active");
		$("#tournament").tabs('load', current_index);
		if (typeof callback === 'function')
			callback();
	}
	var associations = null;

	function getAssociations() {
		$.getJSON('associations', function(data) {
			associations = data;
			populateAssociationComplete();
		}).fail(window.xhrError);
	}
	populateAssociationComplete = function(force) {
		if (associations === null || force)
			return getAssociations();
		$("input[data-colname='Association']").autocomplete({
			source: associations,
			minLength: 1
		});
	}

	/* Start auto refresh for first tab if needed */
	if (refresh) {
		$('#refreshcontrol').show();
		updateTournamentTab(0, refresh + 0);
	}
	else {
		$('#refreshcontrol').hide();
	};
});
