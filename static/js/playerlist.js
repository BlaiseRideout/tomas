$(function() {
	withCountries(function() {
		$.getJSON("/authentication", function(auth) {

			var anyCountry = [{
					Code: "any",
					Id: NaN,
					Flag_Image: ""
				}],
				selectedPlayers = new Object(), // hash of selected Player Id's
				createMergeButton = function(item) {
					// icon idea: triple nested greater than ⫸ (u-2AF8)
					var selected = selectedPlayerIDs(),
						button = $("<input>").attr({
							type: "button",
							title: "Merge selected players",
						}).addClass(
							"player-merge-button jsgrid-button")
						.data("playerID", item.Id)
						.on("click",
							function(e) {
								mergeSelectedPlayers(selectedPlayers, e);
								e.stopPropagation();
							});
					if (selected.length > 1 && selectedPlayers[item.Id]) {
						button.show()
					}
					else {
						button.hide()
					}
					return button

				},
				createPlayerSelectButton = function(editable) {
					return function(value, item) {
						var box = this._createCheckbox().prop({
							checked: item.Id && selectedPlayers[item.Id],
							disabled: !editable
						});
						if (editable) {
							box.click(function(e) {
								selectedPlayers[item.Id] = $(this).prop("checked");
								players = selectedPlayerIDs();
								updatePlayerMergeButtons();
								e.stopPropagation();
							})
						};
						return box;
					}
				},
				fieldDescriptions = [{
						name: "Id",
						type: "number",
						width: 5,
						visible: false
					},
					{
						name: "Name",
						type: "text",
						width: null,
						css: "playernamefield",
						inserting: auth['user'],
						editing: auth['user'],
						validate: "required",
						itemTemplate: playerStatLinkTemplate,
					},
					{
						name: "Association",
						type: "text",
						width: null,
						css: "playerassociationfield",
						inserting: auth['user'],
						editing: auth['user']
					},
					{
						name: "Country",
						type: "select",
						width: null,
						css: "playercountryfield",
						items: anyCountry.concat(countryList),
						inserting: auth['user'],
						editing: auth['user'],
						valueField: "Id",
						valueType: "number",
						textField: "Code",
						itemTemplate: countryTemplate,
					},
					{
						name: "Tournaments",
						type: "number",
						width: null,
						css: "playertournamentsfield",
						editing: false,
						inserting: false
					},
					{
						name: "Latest",
						type: "text",
						width: null,
						css: "playerlatestfield",
						editing: false,
						inserting: false
					},
					{
						name: "",
						type: "checkbox",
						width: null,
						inserting: false,
						editing: false,
						css: "playerselectboxfield",
						itemTemplate: createPlayerSelectButton(true),
						editTemplate: createPlayerSelectButton(false),
						visible: auth['user'] ? true : false,
					},
					{
						type: "control",
						itemTemplate: function(value, item) {
							var $result = $([]);
							if (this.editButton && auth['user']) {
								$result = $result.add(
									this._createEditButton(item));
							}
							if (this.deleteButton && auth['admin'] &&
								!item.Tournaments && !item.Scores) {
								$result = $result.add(
									this._createDeleteButton(item));
							}
							if (auth['user']) {
								$result = $result.add(createMergeButton(item));
							}
							return $result;
						},
						css: "playercontrolfield",
					}
				],
				gridController = makeController(base + 'playerlist',
					fieldDescriptions);

			function selectedPlayerIDs() {
				var playerlist = [];
				for (p in selectedPlayers) {
					if (selectedPlayers[p]) {
						playerlist.push(p)
					}
				};
				return playerlist;
			};

			function clearSelectedPlayers() {
				selectedPlayers = new Object();
				$("#playersGrid .PlayerSelectBox input").prop("checked", false);
			};

			function updatePlayerMergeButtons() {
				$("#playersGrid .player-merge-button").each(
					function(i, elem) {
						var id = $(elem).data("playerID");
						if (players.length > 1 && selectedPlayers[id]) {
							$(elem).show()
						}
						else {
							$(elem).hide()
						}
					});
			};

			function mergeSelectedPlayers(selectedPlayers, e) {
				players = selectedPlayerIDs();
				if (players.length < 2) {
					$.notify('Merge requires 2 or more players')
					return;
				}
				$.post(
					"/mergePlayers/",
					JSON.stringify({
						playerIDs: players,
						performMerge: false
					}),
					function(resp) {
						if (resp.status != 0) {
							$.notify(resp.message);
							return
						};
						$.getJSON(
							"/playerlist?players=" +
							players.join("%20"),
							function(currentPlayers) {
								if (currentPlayers.status != 0) {
									$.notify(currentPlayers.message);
									return
								};
								confirmMerge(
									resp.merged, currentPlayers.data).done(
									function(val) {
										if (!val) {
											$.notify('Internal Error')
										}
										$.post("/mergePlayers/",
											JSON.stringify({
												playerIDs: players,
												performMerge: true
											}),
											function(realmerge) {
												if (realmerge.status != 0) {
													$.notify(
														realmerge.message);
													return
												};
												clearSelectedPlayers();
												$("#playersGrid")
													.jsGrid("loadData");
											});
									});
							});
					});
			};

			function confirmMerge(merged, players) {
				var table = '<table class="confirm-merge-table">',
					columns = [],
					defer = $.Deferred();
				table += '<thead><tr>';
				for (key in merged) {
					table += '<th>' + key + '</th>';
					columns.push(key)
				};
				table += '</tr></thead>  <tbody>' +
					players.map(function(o) {
						return copyObj(o, merged)
					})
					.map(makePlayerRow(columns)).join(' ');
				table += '<tr><td colspan=' + columns.length + '>' +
					'will be merged into the player</td></tr>';
				table += '<tr>' + makePlayerRow(columns)(merged) + '</tr>';
				table += '<tr><td colspan=' + columns.length + '>' +
					'The operation cannot be undone. </td><tr>';
				$.confirm({
					title: 'Confirm merge of ' + players.length +
						' player records',
					useBootstrap: false,
					boxWidth: '80%',
					closeIcon: true,
					theme: 'dark',
					content: table,
					buttons: {
						confirm: function() {
							defer.resolve(true)
						},
						cancel: {
							text: 'Do not merge',
							btnClass: 'btn-blue',
							keys: ['enter', 'space'],
							action: function() {
								defer.reject(false)
							},
						}
					},
				});
				return defer.promise();
			};

			function makePlayerRow(columns) {
				return function(player) {
					return '<tr>' +
						columns.map(function(col) {
							return '<td>' + (col == 'Country' ?
								countries[player[col]].Code :
								player[col] ? player[col] : '') + '</td>';
						}).join(' ') + '</tr>';
				}
			};

			function countryTemplate(value, item) {
				var flag = $('<span class="flagimage">').html(countries[value].Flag_Image);
				return $('<span class="countrypair">').text(countries[value].Code).append(flag);
			}

			function verifySpreadsheet() {
				var data = new FormData($('#add-players-dialog #spreadsheet-picker')[0]);
				$.ajax({
					'url': 'findPlayersInSpreadsheet',
					'data': data,
					'type': 'POST',
					'contentType': false,
					'processData': false,
					success: function(data) {
						if (data["status"] == 0)
							showPlayerUploadChoices(data);
						else
							console.log(data);
						if (data["message"])
							$.notify(data["message"], data["status"]);
					},
					fail: function(jqXHR, textStatus, errorThrown) {
						$.notify('File upload failed. ' + textStatus + ' ' + errorThrown)
					}
				})
			};

			function showPlayerUploadChoices(data) {
				var table = $('<table class="playerLists">'),
					columnHeaders = $('<tr "playerList header">');
				columnHeaders.append($('<th>').text('Sheet'));
				columnHeaders.append($('<th>').text('Top Cell'));
				columnHeaders.append($('<th>').text('Count'));
				columnHeaders.append($('<th>'));
				table.append(columnHeaders);
				data.playerLists.map(function(pList) {
					var row = $('<tr class="playerList">');
					row.append($('<td>').text(pList.sheet));
					row.append($('<td>').text(pList.top));
					row.append($('<td>').text(pList.players.length));
					row.append($('<td>').append($('<input type="radio" class="playerListSelector">')));
					table.append(row);
				});
				$('#add-players-dialog .possible-ranges').text(
					'Players found'
				).append(table);
			};

			function uploadSelectedPlayers() {
				console.log('Uploading selected players')
			};

			$("#playersGrid").text('').jsGrid({
				width: "100%",
				height: "auto",

				inserting: auth['user'] ? true : false,
				editing: auth['user'] ? true : false,
				sorting: true,
				filtering: true,
				autoload: true,
				paging: false,
				pageLoading: false,
				controller: gridController,
				fields: fieldDescriptions,
				noDataContent: 'None found',
			});

			$("#uploadPlayerSpreadsheetButton").click(function(event) {
				$('#add-players-dialog input[type="file"]').change(verifySpreadsheet);
				$('#add-players-dialog > div').show();
				$('#add-players-dialog').dialog({
					height: "auto",
					minWidth: 600,
					modal: true,
					dialogClass: "no-close",
					buttons: {
						"Upload players": function() {
							$(this).dialog("close");
							uploadSelectedPlayers();
						},
						Cancel: function() {
							$(this).dialog("close");
						}
					}
				});
				event.stopPropagation();
			});
		});
	});
});
